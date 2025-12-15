# -*- coding: utf-8 -*-
"""
性能配置文件 - 批量处理优化参数
用户可以根据自己的系统配置调整这些参数以获得最佳性能
"""
import multiprocessing
import psutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerformanceConfig:
    """性能配置数据类"""

    # ========== 系统检测 ==========
    cpu_cores: int = 0
    physical_cores: int = 0
    memory_gb: float = 0.0
    gpu_memory_gb: float = 0.0

    # ========== 队列容量配置 ==========
    audio_queue_multiplier: int = 2  # audio_queue容量 = pre_proc_workers * multiplier
    task_queue_multiplier: int = 2   # task_queue容量 = pre_proc_workers * multiplier
    result_queue_size: int = 64      # result_queue固定容量

    # ========== FFmpeg并发配置 ==========
    ffmpeg_concurrent: int = 2       # FFmpeg并发进程数

    # ========== 工作进程数配置 ==========
    pre_proc_workers: int = 4        # 预处理进程数
    post_proc_workers: int = 6       # 后处理进程数
    recognition_workers: int = 1     # 识别进程数

    # ========== FFSubSync配置 ==========
    ffsubsync_fast_mode: bool = False      # 快速模式（跳过帧率分析）
    ffsubsync_max_offset: int = 60         # 最大偏移量（秒）
    ffsubsync_vad: str = 'silero'          # VAD算法：silero/webrtc/auditok

    # ========== 文件处理配置 ==========
    enable_file_sorting: bool = True       # 启用文件优先级排序（小文件优先）

    @classmethod
    def auto_detect(cls) -> 'PerformanceConfig':
        """自动检测系统配置并生成推荐配置"""
        config = cls()

        # 检测CPU
        config.cpu_cores = multiprocessing.cpu_count() or 1
        config.physical_cores = config.cpu_cores // 2 if config.cpu_cores > 4 else config.cpu_cores

        # 检测内存
        config.memory_gb = psutil.virtual_memory().total / (1024**3)

        # 检测GPU显存
        try:
            import torch
            if torch.cuda.is_available():
                config.gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        except Exception:
            config.gpu_memory_gb = 0.0

        # 根据系统配置自动调整参数
        config._apply_auto_tuning()

        return config

    def _apply_auto_tuning(self):
        """根据系统配置自动调整性能参数"""
        # FFmpeg并发配置
        if self.cpu_cores >= 16:
            self.ffmpeg_concurrent = 6
        elif self.cpu_cores >= 8:
            self.ffmpeg_concurrent = 4
        else:
            self.ffmpeg_concurrent = 2

        # 工作进程数配置
        if self.memory_gb >= 32 and self.cpu_cores >= 16:
            # 高性能系统
            self.pre_proc_workers = min(16, self.physical_cores)
            self.post_proc_workers = min(20, self.cpu_cores)
        elif self.memory_gb >= 16 and self.cpu_cores >= 8:
            # 中端系统
            self.pre_proc_workers = min(10, self.physical_cores)
            self.post_proc_workers = min(12, self.cpu_cores)
        else:
            # 入门系统
            self.pre_proc_workers = min(4, max(2, self.physical_cores // 2))
            self.post_proc_workers = min(6, max(2, self.cpu_cores // 2))

        # 识别进程数配置（仅GPU模式）
        if self.gpu_memory_gb >= 12:
            self.recognition_workers = 2
        else:
            self.recognition_workers = 1

    def get_summary(self) -> str:
        """获取配置摘要"""
        lines = [
            "=" * 60,
            "性能配置摘要",
            "=" * 60,
            "",
            "系统信息:",
            f"  - CPU核心数: {self.cpu_cores} (物理核心: {self.physical_cores})",
            f"  - 内存: {self.memory_gb:.1f} GB",
            f"  - GPU显存: {self.gpu_memory_gb:.1f} GB" if self.gpu_memory_gb > 0 else "  - GPU: 未检测到",
            "",
            "队列容量:",
            f"  - audio_queue: pre_proc_workers × {self.audio_queue_multiplier}",
            f"  - task_queue: pre_proc_workers × {self.task_queue_multiplier}",
            f"  - result_queue: {self.result_queue_size}",
            "",
            "并发配置:",
            f"  - FFmpeg并发: {self.ffmpeg_concurrent}",
            f"  - 预处理进程: {self.pre_proc_workers}",
            f"  - 识别进程: {self.recognition_workers}",
            f"  - 后处理进程: {self.post_proc_workers}",
            "",
            "FFSubSync配置:",
            f"  - 快速模式: {'启用' if self.ffsubsync_fast_mode else '禁用'}",
            f"  - 最大偏移: {self.ffsubsync_max_offset}秒",
            f"  - VAD算法: {self.ffsubsync_vad}",
            "",
            "文件处理:",
            f"  - 文件排序: {'启用（小文件优先）' if self.enable_file_sorting else '禁用'}",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)

    @classmethod
    def get_preset(cls, preset_name: str) -> 'PerformanceConfig':
        """获取预设配置"""
        config = cls.auto_detect()

        if preset_name == "conservative":
            # 保守配置：稳定优先
            config.ffmpeg_concurrent = max(2, config.ffmpeg_concurrent // 2)
            config.pre_proc_workers = max(2, config.pre_proc_workers // 2)
            config.post_proc_workers = max(2, config.post_proc_workers // 2)
            config.recognition_workers = 1
            config.ffsubsync_fast_mode = False

        elif preset_name == "balanced":
            # 平衡配置：使用自动检测的值
            pass

        elif preset_name == "aggressive":
            # 激进配置：性能优先
            config.ffmpeg_concurrent = min(8, config.cpu_cores // 2)
            config.pre_proc_workers = min(20, config.physical_cores)
            config.post_proc_workers = min(24, config.cpu_cores)
            if config.gpu_memory_gb >= 12:
                config.recognition_workers = 2
            config.ffsubsync_fast_mode = True

        return config


# 全局默认配置实例
DEFAULT_CONFIG = PerformanceConfig.auto_detect()


def print_system_info():
    """打印系统信息和推荐配置"""
    config = PerformanceConfig.auto_detect()
    print(config.get_summary())


if __name__ == "__main__":
    print_system_info()
