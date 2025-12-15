# utils.py - 文件清理工具和子进程封装
import os
import time
import shutil
import traceback
import subprocess
from pathlib import Path
from typing import List, Optional, Callable
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# 子进程统一封装（消灭黑窗口）
# =============================================================================

# Windows 上隐藏子进程窗口的标志
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def run_silent(cmd, **kw):
    """
    统一的外部命令调用：隐藏黑窗、禁用stdin、收集stdout/stderr

    Args:
        cmd: 命令列表
        **kw: 传递给 subprocess.run 的其他参数

    Returns:
        subprocess.CompletedProcess: 执行结果
    """
    kw.setdefault("stdout", subprocess.PIPE)
    kw.setdefault("stderr", subprocess.PIPE)
    kw.setdefault("stdin", subprocess.DEVNULL)
    kw.setdefault("text", True)
    kw.setdefault("encoding", "utf-8")  # 【修复】明确指定UTF-8编码
    kw.setdefault("errors", "ignore")   # 【修复】忽略无法解码的字符
    kw.setdefault("shell", False)

    if os.name == "nt":
        kw["creationflags"] = kw.get("creationflags", 0) | CREATE_NO_WINDOW

    return subprocess.run(cmd, **kw)


def run_ffmpeg_with_progress(base_cmd: list, total_ms: int, emit, ffmpeg_path: str = "ffmpeg"):
    """
    执行 FFmpeg 命令并实时报告进度

    Args:
        base_cmd: FFmpeg 参数列表（从 -i 开始，不包含 ffmpeg 本体）
        total_ms: 文件总时长（毫秒）
        emit: 回调函数，接收进度事件字典
        ffmpeg_path: FFmpeg 可执行文件路径

    Returns:
        int: 进程返回码
    """
    full_cmd = [
        ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error",
        "-progress", "pipe:1", *base_cmd
    ]

    creationflags = CREATE_NO_WINDOW if os.name == "nt" else 0

    p = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",  # 【修复】明确指定UTF-8编码
        errors="ignore",   # 【修复】忽略无法解码的字符
        shell=False,
        creationflags=creationflags
    )

    last_ms = 0
    last_t = time.time()

    for line in p.stdout:
        if line.startswith("out_time_ms="):
            try:
                cur_ms = int(line.split("=", 1)[1].strip())
                done = min(1.0, cur_ms / max(1, total_ms))
                now = time.time()
                dt = max(1e-3, now - last_t)
                v = max(1, cur_ms - last_ms) / dt  # ms/s
                eta = max(0, (total_ms - cur_ms) / v)
                emit({"kind": "ffmpeg", "done": done, "eta_s": eta})
                last_ms, last_t = cur_ms, now
            except (ValueError, IndexError):
                pass
        elif line.startswith("speed="):
            try:
                speed = line.split("=", 1)[1].strip()
                emit({"kind": "ffmpeg", "speed": speed})
            except IndexError:
                pass

    rc = p.wait()
    return rc

class FileCleaner:
    """优化的文件清理工具，解决文件占用和清理失败问题"""
    
    def __init__(self, max_retries: int = 5, retry_delay: float = 1.0):
        """
        初始化文件清理器
        
        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.cleaned_files = []
        self.failed_files = []
    
    def safe_remove_file(self, file_path: str, log_callback: Optional[Callable] = None) -> bool:
        """
        安全删除文件，带重试机制
        
        Args:
            file_path: 文件路径
            log_callback: 日志回调函数
            
        Returns:
            bool: 是否删除成功
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return True
        
        for attempt in range(self.max_retries):
            try:
                file_path.unlink()
                self.cleaned_files.append(str(file_path))
                if log_callback:
                    log_callback(f"✅ 已清理文件: {file_path.name}")
                return True
                
            except PermissionError as e:
                if attempt < self.max_retries - 1:
                    if log_callback:
                        log_callback(f"⚠️ 文件被占用，等待重试 ({attempt + 1}/{self.max_retries}): {file_path.name}")
                    time.sleep(self.retry_delay)
                else:
                    self.failed_files.append(str(file_path))
                    if log_callback:
                        log_callback(f"❌ 清理文件失败: {file_path.name} - {e}")
                    return False
                    
            except OSError as e:
                self.failed_files.append(str(file_path))
                if log_callback:
                    log_callback(f"❌ 清理文件失败: {file_path.name} - {e}")
                return False
        
        return False
    
    def safe_remove_directory(self, dir_path: str, log_callback: Optional[Callable] = None) -> bool:
        """
        安全删除目录，带重试机制
        
        Args:
            dir_path: 目录路径
            log_callback: 日志回调函数
            
        Returns:
            bool: 是否删除成功
        """
        dir_path = Path(dir_path)
        
        if not dir_path.exists():
            return True
        
        for attempt in range(self.max_retries):
            try:
                shutil.rmtree(dir_path)
                self.cleaned_files.append(str(dir_path))
                if log_callback:
                    log_callback(f"✅ 已清理目录: {dir_path.name}")
                return True
                
            except PermissionError as e:
                if attempt < self.max_retries - 1:
                    if log_callback:
                        log_callback(f"⚠️ 目录被占用，等待重试 ({attempt + 1}/{self.max_retries}): {dir_path.name}")
                    time.sleep(self.retry_delay)
                else:
                    self.failed_files.append(str(dir_path))
                    if log_callback:
                        log_callback(f"❌ 清理目录失败: {dir_path.name} - {e}")
                    return False
                    
            except OSError as e:
                self.failed_files.append(str(dir_path))
                if log_callback:
                    log_callback(f"❌ 清理目录失败: {dir_path.name} - {e}")
                return False
        
        return False
    
    def cleanup_temp_files(self, temp_files: List[str], log_callback: Optional[Callable] = None) -> dict:
        """
        批量清理临时文件
        
        Args:
            temp_files: 临时文件列表
            log_callback: 日志回调函数
            
        Returns:
            dict: 清理结果统计
        """
        success_count = 0
        failed_count = 0
        
        for file_path in temp_files:
            if self.safe_remove_file(file_path, log_callback):
                success_count += 1
            else:
                failed_count += 1
        
        result = {
            "success_count": success_count,
            "failed_count": failed_count,
            "total_count": len(temp_files),
            "cleaned_files": self.cleaned_files.copy(),
            "failed_files": self.failed_files.copy()
        }
        
        if log_callback:
            log_callback(f"📊 清理统计: 成功 {success_count}/{len(temp_files)}, 失败 {failed_count}")
        
        return result
    
    def cleanup_word_documents(self, docx_files: List[str], log_callback: Optional[Callable] = None) -> dict:
        """
        专门清理Word文档文件（解决Word进程占用问题）
        
        Args:
            docx_files: DOCX文件列表
            log_callback: 日志回调函数
            
        Returns:
            dict: 清理结果统计
        """
        # Word文档通常需要更长的等待时间
        original_delay = self.retry_delay
        self.retry_delay = 2.0  # 增加等待时间
        
        result = self.cleanup_temp_files(docx_files, log_callback)
        
        # 恢复原始延迟
        self.retry_delay = original_delay
        
        return result
    
    def force_cleanup_on_exit(self, files_to_clean: List[str], log_callback: Optional[Callable] = None):
        """
        程序退出时强制清理文件
        
        Args:
            files_to_clean: 需要清理的文件列表
            log_callback: 日志回调函数
        """
        if log_callback:
            log_callback("🧹 程序退出，执行强制清理...")
        
        for file_path in files_to_clean:
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
                    if log_callback:
                        log_callback(f"✅ 强制清理: {Path(file_path).name}")
            except Exception as e:
                if log_callback:
                    log_callback(f"⚠️ 强制清理失败: {Path(file_path).name} - {e}")

def create_file_cleaner(max_retries: int = 5, retry_delay: float = 1.0) -> FileCleaner:
    """
    创建文件清理器实例
    
    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        
    Returns:
        FileCleaner: 文件清理器实例
    """
    return FileCleaner(max_retries=max_retries, retry_delay=retry_delay)

# 全局文件清理器实例
file_cleaner = create_file_cleaner() 