"""
预先下载 Silero VAD 模型
运行此脚本可以手动下载silero模型到缓存
"""
import torch
import sys
import io

# 修复 Windows CMD 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

print("开始下载 Silero VAD 模型...")
print("模型大小: ~1.5-2MB")
print("下载地址: GitHub/PyTorch Hub")
print("-" * 50)

try:
    # 下载silero模型
    model, utils = torch.hub.load(
        repo_or_dir='snakers4/silero-vad',
        model='silero_vad',
        force_reload=False,  # 如果已存在则不重新下载
        trust_repo=True
    )
    
    print("\n✅ Silero VAD 模型下载成功！")
    print(f"模型类型: {type(model)}")
    print(f"缓存位置: {torch.hub.get_dir()}")
    
    # 测试模型是否可用
    (get_speech_timestamps,
     save_audio,
     read_audio,
     VADIterator,
     collect_chunks) = utils
    
    print("✅ 模型工具函数加载成功")
    print("\n现在可以在 ffsubsync 中使用 silero VAD 了！")
    
except Exception as e:
    print(f"\n❌ 下载失败: {e}")
    print("\n可能的原因:")
    print("- 网络连接问题")
    print("- GitHub访问受限")
    print("- 防火墙拦截")
    print("\n建议: 使用 webrtc 或 auditok 代替")
    sys.exit(1)
