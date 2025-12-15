# -*- coding: utf-8 -*-
"""
FunASR 启动包装器 - 增强版（修复 PyTorch DLL 加载问题 + multiprocessing spawn 支持）
根据 PyTorch 打包最佳实践优化
"""
import sys
import os
import traceback
from datetime import datetime

# 创建日志文件
log_path = "funasr_startup.log"

def write_log(msg):
    """写入日志并打印 - 强制立即刷新"""
    try:
        print(msg, flush=True)
    except:
        pass

    try:
        with open(log_path, 'a', encoding='utf-8', buffering=1) as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        try:
            print(f"[LOG ERROR] {e}", flush=True)
        except:
            pass

def main_launcher():
    """主启动函数 - 必须在 if __name__ == '__main__' 中调用以支持 spawn 模式"""
    write_log("="*70)
    write_log("FunASR 启动 - CPU+GPU 智能自适应版本")
    write_log("="*70)

    try:
        # ========== 步骤 1: 系统信息 ==========
        write_log("\n【步骤 1/7】系统信息收集")
        write_log(f"  Python 版本: {sys.version}")
        write_log(f"  可执行文件: {sys.executable}")
        write_log(f"  打包模式: {getattr(sys, 'frozen', False)}")
        write_log(f"  当前目录: {os.getcwd()}")

        if getattr(sys, 'frozen', False):
            write_log(f"  临时目录: {sys._MEIPASS}")
            write_log(f"  工作目录: {os.getcwd()}")

        # ========== 步骤 2: 多进程初始化（关键！）==========
        write_log("\n【步骤 2/7】多进程环境初始化")
        write_log("  配置 multiprocessing 以支持打包环境...")

        import multiprocessing
        multiprocessing.freeze_support()
        write_log("  [OK] freeze_support() 已调用")

        # 设置 spawn 模式（Windows 打包必需）
        if multiprocessing.current_process().name == 'MainProcess':
            try:
                multiprocessing.set_start_method('spawn', force=True)
                write_log("  [OK] 多进程启动方法设置为 'spawn'")
            except (RuntimeError, ValueError) as e:
                write_log(f"  [WARNING]  启动方法已设置: {e}")

        # ========== 步骤 3: 环境变量配置 ==========
        write_log("\n【步骤 3/7】环境变量配置")

        # 策略：先尝试 CPU 模式，如果成功再尝试 GPU
        write_log("  初始配置：强制 CPU 模式（避免 CUDA DLL 初始化问题）")
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
        os.environ['OMP_NUM_THREADS'] = '4'
        os.environ['MKL_NUM_THREADS'] = '4'
        write_log(f"    CUDA_VISIBLE_DEVICES = '{os.environ.get('CUDA_VISIBLE_DEVICES')}'")
        write_log(f"    OMP_NUM_THREADS = {os.environ['OMP_NUM_THREADS']}")

        # ========== 步骤 4: 基础模块导入 ==========
        write_log("\n【步骤 4/7】导入基础模块")

        write_log("  4.1 导入 PySide6...")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QCoreApplication
        write_log("      [OK] 成功")

        write_log("  4.2 导入 numpy...")
        import numpy
        write_log(f"      [OK] 版本 {numpy.__version__}")

        # ========== 步骤 5: PyTorch DLL 路径配置（关键！）==========
        write_log("\n【步骤 5/7】配置 PyTorch DLL 搜索路径")

        if getattr(sys, 'frozen', False):
            write_log("  检测到打包环境，配置 DLL 搜索路径...")

            # 1. 添加主 _internal 目录
            internal_path = sys._MEIPASS
            if os.path.exists(internal_path):
                try:
                    os.add_dll_directory(internal_path)
                    write_log(f"    [OK] 添加 _internal: {internal_path}")
                except Exception as e:
                    write_log(f"    [WARNING]  无法添加 _internal: {e}")

            # 2. 添加 torch/lib 目录（最重要！）
            torch_lib_path = os.path.join(internal_path, 'torch', 'lib')
            if os.path.exists(torch_lib_path):
                try:
                    os.add_dll_directory(torch_lib_path)
                    write_log(f"    [OK] 添加 torch/lib: {torch_lib_path}")

                    # 列出关键 DLL 文件以便调试
                    dll_files = [f for f in os.listdir(torch_lib_path) if f.endswith('.dll')][:10]
                    write_log(f"       发现 {len(dll_files)} 个 DLL 文件")
                    for dll in dll_files[:5]:
                        write_log(f"         - {dll}")
                except Exception as e:
                    write_log(f"    [WARNING]  无法添加 torch/lib: {e}")
            else:
                write_log(f"    [ERROR] torch/lib 不存在: {torch_lib_path}")

            # 3. 添加 Library/bin 目录（conda 环境）
            lib_bin_path = os.path.join(internal_path, 'Library', 'bin')
            if os.path.exists(lib_bin_path):
                try:
                    os.add_dll_directory(lib_bin_path)
                    write_log(f"    [OK] 添加 Library/bin: {lib_bin_path}")
                except Exception as e:
                    write_log(f"    [WARNING]  无法添加 Library/bin: {e}")

            # 4. 将 torch/lib 添加到 PATH（备用方案）
            if os.path.exists(torch_lib_path):
                os.environ['PATH'] = torch_lib_path + os.pathsep + os.environ['PATH']
                write_log(f"    [OK] torch/lib 已添加到 PATH")

        # ========== 步骤 6: PyTorch 安全导入 ==========
        write_log("\n【步骤 6/7】PyTorch 安全导入")

        write_log("  6.1 尝试导入 torch（CPU 模式）...")
        torch_imported = False
        torch = None

        try:
            write_log("      正在执行 import torch...")
            import torch
            torch_imported = True
            write_log(f"      [OK] torch 导入成功，版本 {torch.__version__}")
        except Exception as e:
            write_log(f"      [ERROR] torch 导入失败: {e}")
            write_log(f"      错误类型: {type(e).__name__}")
            write_log("      详细错误:")
            for line in traceback.format_exc().split('\n'):
                write_log(f"        {line}")
            write_log("      [WARNING]  程序将无法继续运行")
            raise

        # ========== GPU 检测（如果支持）==========
        write_log("\n  6.2 检测 GPU 支持...")

        try:
            # 检查 torch 是否编译时包含 CUDA
            has_cuda_build = hasattr(torch.cuda, 'is_available')
            write_log(f"      CUDA 编译支持: {has_cuda_build}")

            if has_cuda_build:
                # 尝试启用 GPU（移除 CUDA_VISIBLE_DEVICES 限制）
                write_log("      尝试启用 GPU 检测...")
                try:
                    # 临时允许 CUDA
                    del os.environ['CUDA_VISIBLE_DEVICES']

                    # 检测 CUDA 可用性
                    cuda_available = torch.cuda.is_available()
                    write_log(f"      torch.cuda.is_available() = {cuda_available}")

                    if cuda_available:
                        try:
                            gpu_count = torch.cuda.device_count()
                            gpu_name = torch.cuda.get_device_name(0)
                            cuda_version = torch.version.cuda if hasattr(torch.version, 'cuda') else 'Unknown'

                            write_log(f"      [OK] GPU 检测成功！")
                            write_log(f"         GPU 数量: {gpu_count}")
                            write_log(f"         GPU 设备: {gpu_name}")
                            write_log(f"         CUDA 版本: {cuda_version}")
                            write_log(f"      [FAST] 运行模式: GPU 加速")
                        except Exception as e:
                            write_log(f"      [WARNING]  GPU 信息获取失败: {e}")
                            write_log(f"      [CPU] 运行模式: CPU")
                            # 重新禁用 CUDA
                            os.environ['CUDA_VISIBLE_DEVICES'] = ''
                    else:
                        write_log(f"      未检测到可用的 CUDA GPU")
                        write_log(f"      [CPU] 运行模式: CPU")
                        # 重新禁用 CUDA
                        os.environ['CUDA_VISIBLE_DEVICES'] = ''

                except Exception as e:
                    write_log(f"      [WARNING]  GPU 检测过程出错: {e}")
                    write_log(f"      [CPU] 运行模式: CPU（已回退）")
                    # 确保禁用 CUDA
                    os.environ['CUDA_VISIBLE_DEVICES'] = ''
            else:
                write_log(f"      此 PyTorch 版本未编译 CUDA 支持")
                write_log(f"      [CPU] 运行模式: CPU")

        except Exception as e:
            write_log(f"      [WARNING]  GPU 检测异常: {e}")
            write_log(f"      [CPU] 运行模式: CPU")
            # 确保禁用 CUDA
            os.environ['CUDA_VISIBLE_DEVICES'] = ''

        # ========== 步骤 7: 导入主程序模块 ==========
        write_log("\n【步骤 7/7】导入主程序模块")
        write_log("  7.1 导入 main 模块...")
        try:
            import main
            write_log("      [OK] main 模块导入成功")
        except Exception as e:
            write_log(f"      [ERROR] main 模块导入失败: {e}")
            write_log(traceback.format_exc())
            raise

        # ========== 启动应用 ==========
        write_log("\n【启动应用】")
        write_log("="*70)
        write_log("调用 main.start_app()")
        write_log("="*70)

        try:
            main.start_app()
            write_log("\n[OK] 应用正常退出")
        except Exception as e:
            write_log(f"\n[ERROR] 应用运行失败: {e}")
            write_log(traceback.format_exc())
            raise

    except Exception as e:
        write_log(f"\n{'='*70}")
        write_log("[FAIL] 启动失败！")
        write_log(f"{'='*70}")
        write_log(f"错误类型: {type(e).__name__}")
        write_log(f"错误信息: {str(e)}")
        write_log("\n完整堆栈:")
        write_log(traceback.format_exc())
        write_log(f"\n[NOTE] 完整日志已保存: {os.path.abspath(log_path)}")

        # TTY检查：仅在交互式终端中等待用户输入
        if sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
            try:
                input("\n按回车键退出...")
            except Exception:
                pass
        sys.exit(1)

# ========== 【关键】主入口点 - 支持 Windows spawn 模式 ==========
if __name__ == '__main__':
    # 必须在主入口点调用 freeze_support，确保 spawn 模式正常工作
    import multiprocessing
    multiprocessing.freeze_support()

    # 调用主启动函数
    main_launcher()
