#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FFSubSync 修复工具
解决 FFSubSync 无法启动的问题 (错误代码 0xc0000142)
"""

import subprocess
import sys
import os
from pathlib import Path

def check_ffsubsync_status():
    """检查FFSubSync的当前状态"""
    print("=== FFSubSync 状态检查 ===")
    
    try:
        result = subprocess.run(
            ['ffsubsync', '--version'], 
            capture_output=True, 
            text=True, 
            timeout=10,
            encoding='utf-8',
            errors='ignore'
        )
        print("✅ FFSubSync 工作正常")
        print(f"版本信息: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ FFSubSync 未安装")
        return False
    except subprocess.TimeoutExpired:
        print("❌ FFSubSync 响应超时")
        return False
    except Exception as e:
        print(f"❌ FFSubSync 错误: {e}")
        return False

def reinstall_ffsubsync():
    """重新安装FFSubSync"""
    print("\n=== 重新安装 FFSubSync ===")
    
    # 1. 卸载现有版本
    print("1. 卸载现有版本...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'uninstall', 'ffsubsync', '-y'], 
                      check=True, capture_output=True)
        print("   ✅ 卸载完成")
    except subprocess.CalledProcessError:
        print("   ⚠️ 卸载失败或未安装")
    
    # 2. 清理缓存
    print("2. 清理pip缓存...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'cache', 'purge'], 
                      check=True, capture_output=True)
        print("   ✅ 缓存清理完成")
    except subprocess.CalledProcessError:
        print("   ⚠️ 缓存清理失败")
    
    # 3. 重新安装
    print("3. 重新安装FFSubSync...")
    try:
        # 使用完整安装，包含所有依赖
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'ffsubsync[all]', '--upgrade'], 
                      check=True)
        print("   ✅ 安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ 安装失败: {e}")
        return False

def install_visual_cpp_redistributable():
    """提示安装Visual C++运行时库"""
    print("\n=== Visual C++ 运行时库检查 ===")
    print("错误代码 0xc0000142 通常表示缺少 Visual C++ 运行时库")
    print("\n请手动下载并安装以下运行时库:")
    print("1. Microsoft Visual C++ 2015-2022 Redistributable (x64)")
    print("   下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe")
    print("\n2. Microsoft Visual C++ 2015-2022 Redistributable (x86)")
    print("   下载地址: https://aka.ms/vs/17/release/vc_redist.x86.exe")
    print("\n安装完成后请重启计算机，然后重新运行此脚本。")

def try_alternative_installation():
    """尝试替代安装方法"""
    print("\n=== 尝试替代安装方法 ===")
    
    # 方法1: 使用conda安装
    print("1. 尝试使用conda安装...")
    try:
        subprocess.run(['conda', 'install', '-c', 'conda-forge', 'ffsubsync', '-y'], 
                      check=True, capture_output=True)
        print("   ✅ conda安装成功")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("   ❌ conda安装失败")
    
    # 方法2: 从源码安装
    print("2. 尝试从源码安装...")
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 
                       'git+https://github.com/smacke/ffsubsync.git'], 
                      check=True)
        print("   ✅ 源码安装成功")
        return True
    except subprocess.CalledProcessError:
        print("   ❌ 源码安装失败")
    
    return False

def disable_ffsubsync_in_config():
    """在配置中禁用FFSubSync功能"""
    print("\n=== 禁用FFSubSync功能 ===")
    
    # 修改主程序，默认禁用FFSubSync
    main_py_path = Path("main.py")
    if main_py_path.exists():
        try:
            content = main_py_path.read_text(encoding='utf-8')
            
            # 查找并修改FFSubSync检查
            if "FFSUBSYNC_AVAILABLE = check_ffsubsync_availability()" in content:
                new_content = content.replace(
                    "FFSUBSYNC_AVAILABLE = check_ffsubsync_availability()",
                    "FFSUBSYNC_AVAILABLE = False  # 强制禁用FFSubSync"
                )
                main_py_path.write_text(new_content, encoding='utf-8')
                print("   ✅ 已在main.py中禁用FFSubSync")
                return True
        except Exception as e:
            print(f"   ❌ 修改main.py失败: {e}")
    
    return False

def main():
    """主函数"""
    print("FFSubSync 修复工具")
    print("=" * 50)
    
    # 1. 检查当前状态
    if check_ffsubsync_status():
        print("\n✅ FFSubSync 工作正常，无需修复")
        return
    
    # 2. 尝试重新安装
    print("\n🔧 开始修复...")
    if reinstall_ffsubsync():
        if check_ffsubsync_status():
            print("\n🎉 修复成功！FFSubSync 现在可以正常工作")
            return
    
    # 3. 尝试替代安装方法
    if try_alternative_installation():
        if check_ffsubsync_status():
            print("\n🎉 修复成功！FFSubSync 现在可以正常工作")
            return
    
    # 4. 提示安装运行时库
    install_visual_cpp_redistributable()
    
    # 5. 询问是否禁用FFSubSync
    print("\n" + "=" * 50)
    choice = input("是否要在程序中禁用FFSubSync功能？(y/n): ").lower().strip()
    if choice in ['y', 'yes', '是']:
        if disable_ffsubsync_in_config():
            print("\n✅ FFSubSync功能已禁用，程序可以正常运行")
            print("   注意: 字幕精校功能将不可用")
        else:
            print("\n❌ 禁用失败，请手动修改配置")
    
    print("\n修复完成。如果问题仍然存在，请:")
    print("1. 重启计算机")
    print("2. 安装Visual C++运行时库")
    print("3. 或者禁用FFSubSync功能继续使用程序")

if __name__ == "__main__":
    main()