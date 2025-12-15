"""
Silero VAD 模型管理器
支持本地模型加载和 PyTorch Hub 回退
"""
import os
import sys
import torch
from pathlib import Path


class SileroManager:
    """Silero VAD 模型管理器"""

    def __init__(self, project_root=None):
        """
        初始化 Silero 管理器

        Args:
            project_root: 项目根目录路径，默认为当前脚本所在目录
        """
        if project_root is None:
            project_root = Path(__file__).parent
        else:
            project_root = Path(project_root)

        self.project_root = project_root
        self.local_model_dir = project_root / "model_cache" / "silero-vad"
        self.model = None
        self.utils = None

    def is_local_model_available(self):
        """检查本地模型是否可用"""
        required_files = [
            self.local_model_dir / "hubconf.py",
            self.local_model_dir / "src" / "silero_vad" / "data" / "silero_vad.jit",
            self.local_model_dir / "src" / "silero_vad" / "utils_vad.py"
        ]
        return all(f.exists() for f in required_files)

    def load_model(self, force_local=False):
        """
        加载 Silero VAD 模型

        Args:
            force_local: 强制使用本地模型（不回退到 PyTorch Hub）

        Returns:
            tuple: (model, utils) - 模型对象和工具函数

        Raises:
            RuntimeError: 当 force_local=True 但本地模型不可用时
        """
        # 优先尝试本地模型
        if self.is_local_model_available():
            try:
                print(f"[Silero] 从本地加载模型: {self.local_model_dir}")

                # 将本地模型目录添加到 sys.path（临时）
                local_dir_str = str(self.local_model_dir.resolve())
                if local_dir_str not in sys.path:
                    sys.path.insert(0, local_dir_str)

                # 使用 torch.hub.load 加载本地模型
                self.model, self.utils = torch.hub.load(
                    repo_or_dir=str(self.local_model_dir),
                    model='silero_vad',
                    source='local',
                    force_reload=False,
                    trust_repo=True
                )

                print("[Silero] ✅ 本地模型加载成功")
                return self.model, self.utils

            except Exception as e:
                print(f"[Silero] ⚠️ 本地模型加载失败: {e}")
                if force_local:
                    raise RuntimeError(f"本地模型加载失败且禁用了在线回退: {e}")

        # 回退到 PyTorch Hub 在线下载
        if not force_local:
            try:
                print("[Silero] 从 PyTorch Hub 加载模型...")
                self.model, self.utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    trust_repo=True
                )
                print("[Silero] ✅ PyTorch Hub 模型加载成功")
                return self.model, self.utils

            except Exception as e:
                raise RuntimeError(f"本地和在线模型均加载失败: {e}")

        raise RuntimeError("本地模型不可用且禁用了在线回退")

    def get_utils(self):
        """获取 Silero 工具函数（需要先调用 load_model）"""
        if self.utils is None:
            raise RuntimeError("请先调用 load_model() 加载模型")
        return self.utils

    def setup_for_ffsubsync(self):
        """
        为 FFSubSync 设置 Silero 模型环境

        FFSubSync 内部会调用 torch.hub.load('snakers4/silero-vad', ...)
        我们需要确保本地模型可以被 PyTorch Hub 发现

        Returns:
            bool: 设置是否成功
        """
        if not self.is_local_model_available():
            print("[Silero] 本地模型不可用，FFSubSync 将使用 PyTorch Hub")
            return False

        try:
            # 方法1: 设置 TORCH_HOME 环境变量（推荐）
            torch_hub_dir = Path.home() / ".cache" / "torch" / "hub"
            target_dir = torch_hub_dir / "snakers4_silero-vad_master"

            # 如果目标目录不存在或为空，创建符号链接
            if not target_dir.exists() or not any(target_dir.iterdir()):
                print(f"[Silero] 创建符号链接: {target_dir} -> {self.local_model_dir}")

                # Windows 需要管理员权限创建符号链接，改用复制
                if sys.platform == 'win32':
                    import shutil
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    shutil.copytree(self.local_model_dir, target_dir)
                    print("[Silero] ✅ 已复制本地模型到 PyTorch Hub 缓存")
                else:
                    if target_dir.is_symlink():
                        target_dir.unlink()
                    target_dir.symlink_to(self.local_model_dir)
                    print("[Silero] ✅ 已创建符号链接")
            else:
                print("[Silero] PyTorch Hub 缓存已存在，跳过设置")

            return True

        except Exception as e:
            print(f"[Silero] ⚠️ 设置 FFSubSync 环境失败: {e}")
            return False


# 全局单例实例
_silero_manager = None

def get_silero_manager():
    """获取全局 Silero 管理器实例"""
    global _silero_manager
    if _silero_manager is None:
        _silero_manager = SileroManager()
    return _silero_manager


def ensure_silero_for_ffsubsync():
    """
    确保 Silero 模型可用于 FFSubSync

    在调用 ffsubsync 命令之前调用此函数
    """
    manager = get_silero_manager()

    # 1. 检查本地模型
    if manager.is_local_model_available():
        print("[Silero] 检测到本地模型")
        manager.setup_for_ffsubsync()
    else:
        print("[Silero] 本地模型不可用，将依赖 PyTorch Hub")

    # 2. 验证模型是否可加载
    try:
        model, utils = manager.load_model()
        print("[Silero] ✅ 模型验证成功，FFSubSync 可以使用 Silero VAD")
        return True
    except Exception as e:
        print(f"[Silero] ❌ 模型验证失败: {e}")
        return False


if __name__ == "__main__":
    """测试 Silero 管理器"""
    import io

    # 修复 Windows CMD 编码问题
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    print("=" * 60)
    print("Silero VAD 模型管理器测试")
    print("=" * 60)

    manager = SileroManager()

    print(f"\n项目根目录: {manager.project_root}")
    print(f"本地模型目录: {manager.local_model_dir}")
    print(f"本地模型可用: {manager.is_local_model_available()}")

    print("\n" + "=" * 60)
    print("测试模型加载...")
    print("=" * 60)

    try:
        model, utils = manager.load_model()
        print(f"\n✅ 模型加载成功")
        print(f"模型类型: {type(model)}")
        print(f"工具函数: {len(utils)} 个")

        # 测试工具函数
        (get_speech_timestamps,
         save_audio,
         read_audio,
         VADIterator,
         collect_chunks) = utils

        print("\n工具函数列表:")
        print(f"  - get_speech_timestamps: {type(get_speech_timestamps)}")
        print(f"  - save_audio: {type(save_audio)}")
        print(f"  - read_audio: {type(read_audio)}")
        print(f"  - VADIterator: {type(VADIterator)}")
        print(f"  - collect_chunks: {type(collect_chunks)}")

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试 FFSubSync 环境设置...")
    print("=" * 60)

    success = ensure_silero_for_ffsubsync()
    print(f"\nFFSubSync 环境设置: {'成功 ✅' if success else '失败 ❌'}")
