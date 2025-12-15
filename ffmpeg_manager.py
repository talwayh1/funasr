# ffmpeg_manager.py
# -*- coding: utf-8 -*-
"""
统一的FFmpeg管理器 (重构版)
功能：
1. 自动检测本地FFmpeg环境。
2. 如果检测失败，能根据操作系统自动下载并配置FFmpeg。
3. 为项目其他模块提供获取FFmpeg/FFprobe可执行文件路径的功能。
4. 作为验证脚本，检查所有相关设置。
"""

import os
import sys
import platform
import urllib.request
import zipfile
import tarfile
import subprocess
from pathlib import Path
from utils import run_silent

# --- 路径和常量定义 ---
PROJECT_DIR = Path(__file__).parent.resolve()
FFMPEG_DIR = PROJECT_DIR / "tools" / "ffmpeg"

# --- 路径获取 ---
def get_ffmpeg_path() -> str:
    """获取ffmpeg可执行文件路径，优先使用本地版本"""
    os_name = platform.system().lower()
    exe_name = "ffmpeg.exe" if os_name == "windows" else "ffmpeg"
    local_ffmpeg = FFMPEG_DIR / exe_name
    return str(local_ffmpeg) if local_ffmpeg.exists() else "ffmpeg"

def get_ffprobe_path() -> str:
    """获取ffprobe可执行文件路径，优先使用本地版本"""
    os_name = platform.system().lower()
    exe_name = "ffprobe.exe" if os_name == "windows" else "ffprobe"
    local_ffprobe = FFMPEG_DIR / exe_name
    return str(local_ffprobe) if local_ffprobe.exists() else "ffprobe"

# --- 下载功能 ---
def _download_file(url, save_path):
    print(f"从 {url} 下载...")
    try:
        urllib.request.urlretrieve(url, save_path)
        print("[OK] 下载完成")
        return True
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")
        return False

def _download_ffmpeg_windows():
    print("📥 正在下载Windows版FFmpeg (来自 gyan.dev)...")
    url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    zip_path = PROJECT_DIR / "tools" / "ffmpeg.zip"
    zip_path.parent.mkdir(exist_ok=True)
    if not _download_file(url, zip_path): return False
    
    print("📂 正在解压...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.infolist():
                if member.filename.endswith(('ffmpeg.exe', 'ffprobe.exe')):
                    zf.extract(member, FFMPEG_DIR)
                    # 移动到根目录
                    extracted_file = FFMPEG_DIR / member.filename
                    target_file = FFMPEG_DIR / Path(member.filename).name
                    extracted_file.rename(target_file)
                    print(f"  -> 已提取: {target_file.name}")
        # 清理空文件夹
        for item in FFMPEG_DIR.iterdir():
            if item.is_dir():
                try:
                    item.rmdir()
                except OSError:
                    pass # 非空文件夹不管
        return True
    except Exception as e:
        print(f"[ERROR] 解压失败: {e}")
        return False
    finally:
        if zip_path.exists(): zip_path.unlink()

# Linux下载功能可以类似地重构，此处省略以保持简洁

# --- 测试功能 ---
def _test_executable(path: str) -> bool:
    """测试可执行文件是否可用（使用 run_silent 避免黑窗）"""
    try:
        result = run_silent([path, "-version"], timeout=10, check=True)
        return result.returncode == 0
    except Exception:
        return False

# --- 主接口 ---
def ensure_ffmpeg_is_ready() -> bool:
    print("--- 正在检查FFmpeg环境 ---")
    if _test_executable(get_ffmpeg_path()) and _test_executable(get_ffprobe_path()):
        print(f"[OK] FFmpeg已就绪! 使用路径: {get_ffmpeg_path()}")
        return True
    
    print("[WARNING] 未检测到可用的FFmpeg，开始自动下载...")
    system = platform.system().lower()
    download_success = False
    if system == "windows":
        download_success = _download_ffmpeg_windows()
    elif system == "linux":
        print("[INFO] 检测到 Linux 系统")
        print("请使用包管理器安装 FFmpeg:")
        print("  Ubuntu/Debian: sudo apt update && sudo apt install ffmpeg")
        print("  Fedora/RHEL:   sudo dnf install ffmpeg")
        print("  Arch Linux:    sudo pacman -S ffmpeg")
        return False
    elif system == "darwin":  # macOS
        print("[INFO] 检测到 macOS 系统")
        print("请使用 Homebrew 安装 FFmpeg:")
        print("  brew install ffmpeg")
        return False
    else:
        print(f"[ERROR] 不支持的系统: {system}。请手动安装FFmpeg。")
        return False
        
    if not download_success:
        print("[ERROR] FFmpeg自动下载失败。")
        return False
        
    print("\n--- 下载完成，重新检查FFmpeg环境 ---")
    if _test_executable(get_ffmpeg_path()) and _test_executable(get_ffprobe_path()):
        print(f"[SUCCESS] FFmpeg成功安装并就绪!")
        return True
    else:
        print("[ERROR] 下载后FFmpeg依然不可用。")
        return False

# --- 验证脚本功能 (来自 verify_cfr_setup.py) ---
def _run_verification_checks():
    """执行所有验证检查"""
    print("\n\n=== FFmpeg & CFR 设置完整性验证 ===")
    checks_passed = True
    
    # 1. 文件检查
    print("\n--- 1. 文件检查 ---")
    ffmpeg_exe = FFMPEG_DIR / "ffmpeg.exe" if platform.system().lower() == 'windows' else FFMPEG_DIR / "ffmpeg"
    ffprobe_exe = FFMPEG_DIR / "ffprobe.exe" if platform.system().lower() == 'windows' else FFMPEG_DIR / "ffprobe"
    
    if ffmpeg_exe.exists(): print(f"[OK] ffmpeg.exe: 已找到")
    else: print(f"[ERROR] ffmpeg.exe: 未找到于 {ffmpeg_exe}"); checks_passed = False
    
    if ffprobe_exe.exists(): print(f"[OK] ffprobe.exe: 已找到")
    else: print(f"[ERROR] ffprobe.exe: 未找到于 {ffprobe_exe}"); checks_passed = False

    # 2. 配置检查
    print("\n--- 2. 路径配置检查 ---")
    ffmpeg_path = get_ffmpeg_path()
    ffprobe_path = get_ffprobe_path()
    print(f"📋 FFmpeg路径: {ffmpeg_path}")
    print(f"📋 FFprobe路径: {ffprobe_path}")
    if "tools" in ffmpeg_path: print("[OK] FFmpeg路径配置正确")
    else: print("[WARNING] FFmpeg路径未指向本地 'tools' 目录，将使用系统版本");
    
    # 3. 执行测试
    print("\n--- 3. 可执行文件测试 ---")
    if _test_executable(ffmpeg_path): print("[OK] FFmpeg可执行")
    else: print("[ERROR] FFmpeg不可执行"); checks_passed = False
    
    if _test_executable(ffprobe_path): print("[OK] FFprobe可执行")
    else: print("[ERROR] FFprobe不可执行"); checks_passed = False
        
    print("\n--- 验证结果 ---")
    if checks_passed:
        print("[SUCCESS] 所有检查通过! FFmpeg环境已正确配置。")
    else:
        print("[WARNING] 存在配置问题，请根据上面的提示进行修复。")
    return checks_passed

if __name__ == "__main__":
    ensure_ffmpeg_is_ready()
    _run_verification_checks()
