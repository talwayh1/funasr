#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FunASR模型预下载脚本
解决ModelScope依赖问题并预下载模型
"""

import os
import sys
from pathlib import Path

def setup_environment():
    """设置环境变量"""
    cache_dir = Path("./model_cache/modelscope").absolute()
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 设置所有相关的缓存环境变量
    env_vars = {
        'MODELSCOPE_CACHE': str(cache_dir),
        'HF_HOME': str(cache_dir),
        'TRANSFORMERS_CACHE': str(cache_dir),
        'HF_DATASETS_CACHE': str(cache_dir),
        'TORCH_HOME': str(cache_dir),
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"✅ 设置环境变量 {key} = {value}")

def check_dependencies():
    """检查必要的依赖"""
    required_packages = [
        'transformers',
        'peft', 
        'diffusers',
        'modelscope',
        'funasr'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package} - 已安装")
        except ImportError:
            print(f"❌ {package} - 缺失")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️ 缺失依赖包: {', '.join(missing_packages)}")
        print("请运行: uv add " + " ".join(missing_packages))
        return False
    
    return True

def download_models():
    """下载FunASR模型"""
    print("\n🚀 开始下载FunASR模型...")
    
    try:
        from funasr import AutoModel
        
        # 模型配置列表
        model_configs = [
            {
                'name': 'FunASR完整模型（Seaco Paraformer Large + VAD + 标点）',
                'model': 'iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch',
                'vad_model': 'iic/speech_fsmn_vad_zh-cn-16k-common-pytorch',
                'punc_model': 'iic/punc_ct-transformer_cn-en-common-vocab471067-large'
            },
            # 可以添加更多模型配置
        ]
        
        for config in model_configs:
            print(f"\n📦 下载模型: {config['name']}")
            try:
                model = AutoModel(
                    model=config['model'],
                    vad_model=config['vad_model'],
                    punc_model=config['punc_model'],
                    device='cpu',
                    disable_update=True,
                    model_hub='ms'  # 使用ModelScope
                )
                print(f"✅ {config['name']} 下载成功")
                
                # 释放内存
                del model
                
            except Exception as e:
                print(f"❌ {config['name']} 下载失败: {e}")
                
                # 尝试使用HuggingFace Hub
                print(f"🔄 尝试从HuggingFace下载 {config['name']}...")
                try:
                    model = AutoModel(
                        model=config['model'],
                        vad_model=config['vad_model'],
                        punc_model=config['punc_model'],
                        device='cpu',
                        disable_update=True,
                        model_hub='hf'  # 使用HuggingFace Hub
                    )
                    print(f"✅ {config['name']} 从HuggingFace下载成功")
                    del model
                except Exception as e2:
                    print(f"❌ {config['name']} 从HuggingFace也下载失败: {e2}")
        
        print("\n🎉 模型下载完成!")
        return True
        
    except Exception as e:
        print(f"❌ 模型下载过程出错: {e}")
        return False

def test_model_loading():
    """测试模型加载"""
    print("\n🧪 测试模型加载...")

    try:
        from funasr import AutoModel

        model = AutoModel(
            model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
            punc_model="iic/punc_ct-transformer_cn-en-common-vocab471067-large",
            device='cpu',
            disable_update=True
        )

        print("✅ 模型加载测试成功!")

        # 简单的识别测试
        # 这里可以添加音频文件测试

        return True

    except Exception as e:
        print(f"❌ 模型加载测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 FunASR模型预下载工具")
    print("=" * 50)
    
    # 1. 设置环境
    print("1️⃣ 设置环境变量...")
    setup_environment()
    
    # 2. 检查依赖
    print("\n2️⃣ 检查依赖包...")
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请先安装缺失的包")
        return 1
    
    # 3. 下载模型
    print("\n3️⃣ 下载模型...")
    if not download_models():
        print("\n❌ 模型下载失败")
        return 1
    
    # 4. 测试加载
    print("\n4️⃣ 测试模型加载...")
    if not test_model_loading():
        print("\n⚠️ 模型加载测试失败，但模型可能已下载")
    
    print("\n🎉 所有步骤完成!")
    print("现在可以运行主程序了")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())