# processing_controller.py (v5.9 - 断点续传优化，跨进程FFmpeg限流，日志落盘)
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
import psutil
import gc
import time
import json
import threading
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from qt_compat import QObject, pyqtSignal, QTimer
from pipeline_workers import pre_processing_worker, recognition_worker, post_processing_worker

class ResourceMonitor:
    """系统资源监控器"""
    def __init__(self, memory_threshold: float = 85.0):
        self.memory_threshold = memory_threshold
        self.monitoring = False
        self.monitor_thread = None
        self.callbacks = []

    def add_callback(self, callback):
        """添加监控回调"""
        self.callbacks.append(callback)

    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            return
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                memory_percent = psutil.virtual_memory().percent
                process_count = len(psutil.pids())
                for callback in self.callbacks:
                    try:
                        callback({
                            'memory_percent': memory_percent,
                            'process_count': process_count,
                            'memory_warning': memory_percent > self.memory_threshold
                        })
                    except Exception:
                        pass
                time.sleep(2)
            except Exception:
                break

class ProgressManager:
    """进度管理器，支持断点续传"""
    def __init__(self, project_dir: str = "."):
        self.progress_file = Path(project_dir) / "processing_progress.json"
        self.completed_files = set()
        self.failed_files = set()
        self.session_id = int(time.time())

    def load_progress(self):
        """加载之前的进度"""
        if not self.progress_file.exists():
            return {}
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.completed_files = set(data.get('completed_files', []))
                self.failed_files = set(data.get('failed_files', []))
                return data
        except Exception:
            return {}

    def save_progress(self, total_files: int, completed: int, failed: int):
        """保存当前进度"""
        progress_data = {
            'session_id': self.session_id,
            'timestamp': time.time(),
            'total_files': total_files,
            'completed_count': completed,
            'failed_count': failed,
            'completed_files': list(self.completed_files),
            'failed_files': list(self.failed_files)
        }
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def mark_completed(self, file_path: str):
        """标记文件为已完成"""
        self.completed_files.add(file_path)

    def is_completed(self, file_path: str) -> bool:
        """检查文件是否已完成"""
        return file_path in self.completed_files

    def clear_progress(self):
        """清除进度记录"""
        if self.progress_file.exists():
            self.progress_file.unlink()
        self.completed_files.clear()
        self.failed_files.clear()

class ProcessingState(Enum):
    IDLE = "就绪"
    ENGINE_STARTING = "识别引擎启动中"
    PROCESSING = "处理中"
    COMPLETED = "已完成"
    ERROR = "错误"
    CANCELLED = "已取消"

@dataclass
class ProcessingConfig:
    input_files: List[str] = field(default_factory=list)
    generate_srt: bool = True
    generate_srt_txt: bool = False
    generate_txt: bool = False
    generate_json: bool = False
    generate_txt_md: bool = False
    generate_docx: bool = False
    generate_pdf: bool = False
    cfr_enabled: bool = False
    ffsubsync_enabled: bool = False
    ffsubsync_vad: str = "silero"  # 新增：VAD算法选择 (webrtc/auditok/silero) - 默认使用最准确的silero
    ffsubsync_max_offset: int = 60  # 新增：最大偏移量（秒），限制搜索范围以提高速度
    device: str = "cpu"
    enable_resume: bool = True  # 新增：启用断点续传
    batch_size: int = 4  # 新增：批处理大小
    max_memory_percent: float = 85.0  # 新增：内存使用阈值
    supported_video_ext: List[str] = field(default_factory=lambda: ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'])

class ProcessingController(QObject):
    state_changed = pyqtSignal(ProcessingState)
    progress_updated = pyqtSignal(int, str)
    error_occurred = pyqtSignal(str, str)
    processing_completed = pyqtSignal(dict)
    log_message = pyqtSignal(str)
    stats_updated = pyqtSignal(dict)  # 新增：统计信息更新信号
    memory_warning = pyqtSignal(float)  # 新增：内存警告信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config: Optional[ProcessingConfig] = None
        self._engine_ready = False
        self.recognition_processes: list = []  # 【性能优化】支持多个识别进程
        self.current_state = ProcessingState.IDLE

        self.manager = multiprocessing.Manager()
        self.pause_event = self.manager.Event()
        self.pause_event.set()

        # 设置队列maxsize实现背压控制，让上游在队列满时阻塞等待
        # 注意：将在 _start_pipeline_workers 中根据进程数动态设置
        self.task_queue = None  # 将在启动时创建
        self.audio_queue = None
        self.result_queue = None

        self.progress_queue = self.manager.Queue()  # 进度队列不限制
        self.log_queue = self.manager.Queue()  # 日志队列不限制
        self.engine_status_queue = self.manager.Queue()  # 状态队列不限制

        # 【性能优化】FFmpeg全局并发限流：根据CPU核心数动态调整
        cpu_cores = multiprocessing.cpu_count() or 1
        if cpu_cores >= 16:
            ffmpeg_concurrent = 6
        elif cpu_cores >= 8:
            ffmpeg_concurrent = 4
        else:
            ffmpeg_concurrent = 2
        self.ffmpeg_semaphore = self.manager.Semaphore(ffmpeg_concurrent)
        print(f"⚙️ 性能优化：FFmpeg并发限制 = {ffmpeg_concurrent} (基于{cpu_cores}核心)")

        self.pre_process_pool: Optional[ProcessPoolExecutor] = None
        self.post_process_pool: Optional[ProcessPoolExecutor] = None

        self.is_cleaning_up = False
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0

        # 新增组件
        self.resource_monitor = ResourceMonitor()
        self.progress_manager = ProgressManager()
        self.is_paused = False
        self.peak_memory_percent = 0.0
        self._is_shutting_down = False

        # 设置资源监控回调
        self.resource_monitor.add_callback(self._on_resource_update)
        self.resource_monitor.start_monitoring()

        self.queue_check_timer = QTimer(self)
        self.queue_check_timer.timeout.connect(self._check_queues)
        self.queue_check_timer.start(500)  # 改为每500ms检查，减少CPU占用

        # 添加内存监控
        self.memory_monitor_timer = QTimer(self)
        self.memory_monitor_timer.timeout.connect(self._monitor_memory)
        self.memory_monitor_timer.start(3000)  # 每3秒检查一次
        self.memory_warning_shown = False

        # 初始化文件日志系统（轮转日志）
        self._setup_file_logging()

    def _setup_file_logging(self):
        """设置文件日志系统（滚动轮转，10MB per file，保留10个备份）"""
        try:
            self._logger = logging.getLogger("FunASR")
            self._logger.setLevel(logging.INFO)

            # 创建日志目录
            log_dir = Path(".") / "logs"
            log_dir.mkdir(exist_ok=True)

            # 设置轮转文件处理器
            fh = RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=10,
                encoding="utf-8",
                delay=True
            )
            fh.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                "%Y-%m-%d %H:%M:%S"
            ))
            self._logger.addHandler(fh)

            self._logger.info("=" * 60)
            self._logger.info("FunASR 应用启动")
            self._logger.info("=" * 60)
        except Exception as e:
            # 日志系统初始化失败不应影响主流程
            print(f"警告：日志系统初始化失败: {e}")

    def _on_resource_update(self, resource_info):
        """处理资源监控更新"""
        memory_percent = resource_info['memory_percent']
        
        # 更新峰值内存
        if memory_percent > self.peak_memory_percent:
            self.peak_memory_percent = memory_percent
        
        # 内存警告
        if resource_info['memory_warning'] and self.current_state == ProcessingState.PROCESSING:
            self.log_message.emit(f"⚠️ 内存使用率达到 {memory_percent:.1f}%")
            self.memory_warning.emit(memory_percent)
            # 自动垃圾回收
            gc.collect()
        
        # 发送统计信息更新
        if self.total_files > 0:
            success_rate = (self.completed_files / self.total_files) * 100 if self.total_files > 0 else 0
            stats = {
                'completed': self.completed_files,
                'total': self.total_files,
                'success_rate': success_rate,
                'peak_memory': self.peak_memory_percent
            }
            self.stats_updated.emit(stats)

    def pause_processing(self):
        """暂停处理"""
        if self.current_state == ProcessingState.PROCESSING and not self.is_paused:
            self.is_paused = True
            self.pause_event.clear()
            self.log_message.emit("⏸️ 处理已暂停")

    def resume_processing(self):
        """恢复处理"""
        if self.is_paused:
            self.is_paused = False
            self.pause_event.set()
            self.log_message.emit("▶️ 处理已恢复")

    def _monitor_memory(self):
        """内存监控"""
        try:
            memory_percent = psutil.virtual_memory().percent

            # 更新峰值
            if memory_percent > self.peak_memory_percent:
                self.peak_memory_percent = memory_percent

            # 发送统计信息
            if self.total_files > 0:
                success_rate = (self.completed_files / self.total_files) * 100
                stats = {
                    'completed': self.completed_files,
                    'total': self.total_files,
                    'success_rate': success_rate,
                    'peak_memory': self.peak_memory_percent
                }
                self.stats_updated.emit(stats)

            # 内存警告
            if memory_percent > 85 and not self.memory_warning_shown:
                self.memory_warning.emit(memory_percent)
                self.memory_warning_shown = True
                self.log_message.emit(f"⚠️ 内存使用率达到 {memory_percent:.1f}%")
            elif memory_percent < 75:
                self.memory_warning_shown = False

        except Exception:
            pass

    def _handle_progress_event(self, event: dict):
        """
        处理实时进度事件（FFmpeg/ASR）

        事件格式:
        - FFmpeg: {"kind": "ffmpeg", "file": "...", "stage": "extract", "done": 0.XX, "eta_s": XX, "speed": "1.9x"}
        - ASR: {"kind": "asr", "file": "...", "done": 1.0, "speed": "2.5xRT"}
        """
        kind = event.get("kind")
        file_path = event.get("file", "")

        if not file_path:
            return

        # 初始化文件进度跟踪
        if not hasattr(self, '_per_file_progress'):
            self._per_file_progress = {}

        file_info = self._per_file_progress.setdefault(file_path, {
            "ffmpeg_done": 0.0,
            "asr_done": 0.0,
            "speed": "-",
            "eta_s": None
        })

        # 更新进度信息
        if kind == "ffmpeg":
            file_info["ffmpeg_done"] = event.get("done", 0.0)
            if "speed" in event:
                file_info["speed"] = event["speed"]
            if "eta_s" in event:
                file_info["eta_s"] = event["eta_s"]
        elif kind == "asr":
            file_info["asr_done"] = event.get("done", 0.0)
            if "speed" in event:
                file_info["speed"] = event["speed"]

        # 计算总体进度
        self._update_overall_progress()

    def _update_overall_progress(self):
        """根据各文件的实时进度更新总体进度"""
        if not hasattr(self, '_per_file_progress'):
            return

        if self.total_files == 0:
            return

        # 已完成的文件数
        completed = self.completed_files + self.failed_files

        # 正在处理的文件的平均进度
        working_progress = 0.0
        if self._per_file_progress:
            total_progress = 0.0
            for file_path, info in self._per_file_progress.items():
                # FFmpeg 占 70%，ASR 占 30%
                file_progress = info["ffmpeg_done"] * 0.7 + info["asr_done"] * 0.3
                total_progress += file_progress
            working_progress = total_progress / len(self._per_file_progress)

        # 总体进度 = 已完成数 + 当前处理进度
        overall = min(100, int((completed + working_progress) / self.total_files * 100))

        # 构建状态消息
        current_files = list(self._per_file_progress.keys())
        if current_files:
            # 取第一个正在处理的文件
            first_file = current_files[0]
            info = self._per_file_progress[first_file]

            # 格式化 ETA
            eta_s = info.get("eta_s")
            if eta_s is not None and eta_s > 0:
                import time
                eta_txt = time.strftime("%H:%M:%S", time.gmtime(int(eta_s)))
            else:
                eta_txt = "-"

            from pathlib import Path
            filename = Path(first_file).name
            speed = info.get("speed", "-")

            status_msg = f"{filename}: {int(info['ffmpeg_done']*100)}% | 速度: {speed} | ETA: {eta_txt} | 总体: {overall}%"
        else:
            status_msg = f"已完成: {completed} / 总计: {self.total_files}"

        self.progress_updated.emit(overall, status_msg)

    def _reset_task_state(self):
        """重置所有与单个任务相关的状态计数器"""
        self.total_files = 0
        self.completed_files = 0
        self.failed_files = 0
        self.is_cleaning_up = False
        self.is_paused = False
        self.pause_event.set()
        
        while not self.progress_queue.empty():
            try: self.progress_queue.get_nowait()
            except Exception: break

    def is_engine_ready(self) -> bool:
        return self._engine_ready

    def _check_queues(self):
        # 添加状态检查，避免在清理过程中继续访问队列
        if self.is_cleaning_up or self.current_state in [ProcessingState.CANCELLED, ProcessingState.ERROR]:
            return
            
        try:
            # 1. 修改日志队列检查 - 添加数量限制，同时写入文件
            log_count = 0
            while not self.log_queue.empty() and log_count < 50:  # 限制每次最多处理50条
                try:
                    message = self.log_queue.get_nowait()
                    # 同时写入文件日志和GUI
                    if hasattr(self, '_logger'):
                        self._logger.info(message)
                    self.log_message.emit(message)
                    log_count += 1
                except:
                    break
            
            # 2. 引擎状态检查 - 只在引擎启动阶段检查
            if self.current_state == ProcessingState.ENGINE_STARTING:
                try:
                    status = self.engine_status_queue.get_nowait()
                    if status == "ready":
                        self.log_message.emit("✅ 识别引擎已就绪！开始处理文件...")
                        self._engine_ready = True
                        self._start_pipeline_workers()
                    elif status == "error":
                        self.log_message.emit("❌ 识别引擎加载失败！请检查日志。")
                        self.error_occurred.emit("引擎加载失败", "无法加载FunASR模型，可能是显存不足或模型文件损坏。")
                        self._change_state(ProcessingState.ERROR)
                        self._cleanup_task_resources()
                except:
                    pass  # 队列为空是正常的

            # 3. 进度检查 - 只在处理阶段检查
            if self.current_state == ProcessingState.PROCESSING:
                progress_count = 0
                while not self.progress_queue.empty() and progress_count < 20:
                    try:
                        item = self.progress_queue.get_nowait()

                        # 处理字典格式的进度事件（FFmpeg/ASR实时进度）
                        if isinstance(item, dict):
                            self._handle_progress_event(item)
                            progress_count += 1
                            continue

                        # 处理传统的 (status_code, message) 格式
                        status_code, message = item
                        if status_code == 1:
                            self.completed_files += 1
                        elif status_code == -1:
                            self.failed_files += 1

                        if hasattr(self, '_logger'):
                            self._logger.info(message)
                        self.log_message.emit(message)
                        progress_count += 1

                        if self.total_files > 0:
                            progress = int(((self.completed_files + self.failed_files) / self.total_files) * 100)
                            status_msg = f"已完成: {self.completed_files}, 失败: {self.failed_files} / 总计: {self.total_files}"
                            self.progress_updated.emit(progress, status_msg)

                        # 检查是否完成
                        if (self.completed_files + self.failed_files) >= self.total_files:
                            self._complete_processing()
                            break
                    except:
                        break

        except Exception as e:
            # 静默处理通信错误，避免大量警告
            pass

    def start_processing(self, config: ProcessingConfig) -> bool:
        if self.current_state not in [ProcessingState.IDLE, ProcessingState.COMPLETED, ProcessingState.ERROR, ProcessingState.CANCELLED]:
            self.log_message.emit(f"警告：当前状态为 {self.current_state.value}，无法开始新任务。")
            return False

        self._reset_task_state()
        self.pause_event.set()
        self.is_paused = False

        self.config = config
        self.total_files = len(config.input_files)
        if self.total_files == 0: return False

        # 在启动识别进程之前创建必要的队列
        # audio_queue 和 result_queue 必须在 recognition_worker 启动前就存在
        if self.audio_queue is None:
            # 【性能优化】动态设置audio_queue容量，基于CPU核心数
            cpu_cores = multiprocessing.cpu_count() or 1
            physical_cores = cpu_cores // 2 if cpu_cores > 4 else cpu_cores
            memory_gb = psutil.virtual_memory().total / (1024**3)

            # 估算预处理进程数（与_start_pipeline_workers保持一致）
            if memory_gb >= 32 and cpu_cores >= 16:
                estimated_pre_proc = min(16, physical_cores)  # 优化：从12增加到16
            elif memory_gb >= 16 and cpu_cores >= 8:
                estimated_pre_proc = min(10, physical_cores)  # 优化：从8增加到10
            else:
                estimated_pre_proc = min(4, max(2, physical_cores // 2))

            audio_queue_size = estimated_pre_proc * 2  # 优化：从固定4改为动态
            self.audio_queue = self.manager.Queue(maxsize=audio_queue_size)
            self.log_message.emit(f"⚙️ 性能优化：audio_queue容量 = {audio_queue_size} (基于{cpu_cores}核心)")

        if self.result_queue is None:
            self.result_queue = self.manager.Queue(maxsize=64)  # 【修复】设置合理容量避免内存溢出

        self._change_state(ProcessingState.ENGINE_STARTING)
        self.log_message.emit(f"🚀 任务开始，正在启动识别引擎... (设备: {self.config.device.upper()})")

        engine_config = {'device': self.config.device}
        while not self.engine_status_queue.empty():
            try: self.engine_status_queue.get_nowait()
            except Exception: break

        # 【性能优化】多进程识别：根据设备和显存决定进程数
        num_recognition_workers = 1  # 默认1个

        if self.config.device == 'cuda':
            try:
                import torch
                if torch.cuda.is_available():
                    gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    # 只有显存>=12GB才启用多进程识别
                    if gpu_memory_gb >= 12:
                        num_recognition_workers = 2
                        self.log_message.emit(f"⚙️ 性能优化：GPU显存{gpu_memory_gb:.1f}GB，启用{num_recognition_workers}个识别进程")
                    else:
                        self.log_message.emit(f"⚙️ GPU显存{gpu_memory_gb:.1f}GB，保持1个识别进程")
            except Exception as e:
                self.log_message.emit(f"⚠️ 无法检测GPU显存，保持1个识别进程: {e}")

        # 启动多个识别进程
        self.recognition_processes = []
        for i in range(num_recognition_workers):
            process = multiprocessing.Process(
                target=recognition_worker,
                args=(self.audio_queue, self.result_queue, self.log_queue, engine_config, self.engine_status_queue, self.progress_queue, self.pause_event),
                daemon=True,
                name=f"RecognitionWorker-{i}"
            )
            process.start()
            self.recognition_processes.append(process)

        self.log_message.emit(f"✅ 已启动 {num_recognition_workers} 个识别进程")

        return True
    
    def _start_pipeline_workers(self):
        """启动流水线工作进程 - 优化版（修复重复队列创建bug）"""
        self._change_state(ProcessingState.PROCESSING)

        # 断点续传：过滤已完成的文件
        files = self.config.input_files
        skipped_count = 0
        if self.config.enable_resume:
            def is_file_completed(file_path_str: str) -> bool:
                """检查文件的所有输出产物是否都已存在"""
                p = Path(file_path_str)
                stem = p.stem
                out_dir = p.parent
                targets = []

                # 根据配置检查各类输出文件
                if self.config.generate_srt:     targets.append(out_dir / f"{stem}.srt")
                if self.config.generate_srt_txt:  targets.append(out_dir / f"{stem}.srt.txt")
                if self.config.generate_txt:     targets.append(out_dir / f"{stem}.txt")
                if self.config.generate_json:    targets.append(out_dir / f"{stem}.json")
                if self.config.generate_txt_md:      targets.append(out_dir / f"{stem}.md.txt")
                if self.config.generate_docx:    targets.append(out_dir / f"{stem}.docx")
                if self.config.generate_pdf:     targets.append(out_dir / f"{stem}.pdf")

                # 所有目标文件都存在，且至少有一个目标文件
                return all(t.exists() for t in targets) and len(targets) > 0

            original_count = len(files)
            files = [f for f in files if not is_file_completed(f)]
            skipped_count = original_count - len(files)

            if skipped_count > 0:
                self.log_message.emit(f"⏭️ 断点续传：跳过 {skipped_count} 个已完成文件")

        # 设置总文件数
        file_count = len(files)
        self.total_files = file_count

        if file_count == 0:
            # 所有文件都已完成，直接结束流程
            self.completed_files = skipped_count
            self.progress_updated.emit(100, "所有输入文件均已完成，跳过处理")
            self._complete_processing()
            return

        # 智能计算工作进程数
        cpu_cores = multiprocessing.cpu_count() or 1
        physical_cores = cpu_cores // 2 if cpu_cores > 4 else cpu_cores
        memory_gb = psutil.virtual_memory().total / (1024**3)

        # 【性能优化】根据系统配置动态调整，更激进的并发配置
        if memory_gb >= 32 and cpu_cores >= 16:
            # 高性能系统
            pre_proc_workers = min(16, physical_cores)  # 优化：从12增加到16
            post_proc_workers = min(20, cpu_cores)      # 优化：从16增加到20
        elif memory_gb >= 16 and cpu_cores >= 8:
            # 中端系统
            pre_proc_workers = min(10, physical_cores)  # 优化：从8增加到10
            post_proc_workers = min(12, cpu_cores)      # 优化：从10增加到12
        else:
            # 入门系统
            pre_proc_workers = min(4, max(2, physical_cores // 2))
            post_proc_workers = min(6, max(2, cpu_cores // 2))

        # 考虑文件数量调整 - 使用过滤后的文件数
        if file_count < 5:
            pre_proc_workers = min(pre_proc_workers, file_count)
            post_proc_workers = min(post_proc_workers, file_count)

        # 创建带背压控制的队列（基于进程数设置maxsize）
        # 让上游在队列满时阻塞等待，实现自然限速
        # 注意：audio_queue 和 result_queue 已经在 start_processing() 中创建
        self.task_queue = self.manager.Queue(maxsize=pre_proc_workers * 2)
        # 【关键修复】不再重新创建 result_queue，避免识别进程和后处理进程使用不同的队列
        # result_queue 已在 start_processing() 中创建并传递给识别进程，此处复用即可

        # 【性能优化】文件优先级排序：小文件优先处理
        # 优势：1) 快速看到处理结果  2) 减少内存峰值  3) 提高用户体验
        try:
            files_with_size = []
            for file_path in files:
                try:
                    size = Path(file_path).stat().st_size
                    files_with_size.append((file_path, size))
                except Exception:
                    # 如果无法获取文件大小，放在最后处理
                    files_with_size.append((file_path, float('inf')))

            # 按文件大小排序（小文件优先）
            files_with_size.sort(key=lambda x: x[1])
            files = [f[0] for f in files_with_size]

            total_size_mb = sum(s for _, s in files_with_size if s != float('inf')) / (1024 * 1024)
            self.log_message.emit(f"⚙️ 文件优先级排序：小文件优先（总大小: {total_size_mb:.1f}MB）")
        except Exception as e:
            self.log_message.emit(f"⚠️ 文件排序失败，使用原始顺序: {e}")

        # 【修复】只添加一次任务到队列
        for file_path in files:
            self.task_queue.put(file_path)

        self.log_message.emit(f"⚙️ 系统配置: {cpu_cores}核心, {memory_gb:.1f}GB内存")
        self.log_message.emit(f"⚙️ 分配 {pre_proc_workers} 个预处理进程和 {post_proc_workers} 个后处理进程")
        self.log_message.emit(f"⚙️ 队列容量: task={pre_proc_workers*2}, audio=4, result={post_proc_workers*4}")
        self.log_message.emit(f"⚙️ 待处理文件数: {len(files)}")

        try:
            # 使用spawn方法确保进程隔离
            ctx = multiprocessing.get_context('spawn')
            self.pre_process_pool = ProcessPoolExecutor(max_workers=pre_proc_workers, mp_context=ctx)
            
            # 启动预处理工作进程 - 传递FFmpeg信号量
            for i in range(pre_proc_workers):
                self.pre_process_pool.submit(
                    pre_processing_worker,
                    self.task_queue,
                    self.audio_queue,
                    self.log_queue,
                    self.progress_queue,
                    self.config.__dict__,
                    self.ffmpeg_semaphore,
                    self.pause_event
                )
            
            self.post_process_pool = ProcessPoolExecutor(max_workers=post_proc_workers, mp_context=ctx)
            
            # 启动后处理工作进程
            for i in range(post_proc_workers):
                self.post_process_pool.submit(
                    post_processing_worker,
                    self.result_queue,
                    self.log_queue,
                    self.progress_queue,
                    self.config.__dict__,
                    self.pause_event
                )

        except Exception as e:
            self.error_occurred.emit("流水线启动失败", f"无法创建工作进程池: {e}")
            self._cleanup_task_resources()

    def cancel_processing(self):
        if self.current_state not in [ProcessingState.ENGINE_STARTING, ProcessingState.PROCESSING]: return
        self.log_message.emit("🛑 用户请求取消处理...")
        self._change_state(ProcessingState.CANCELLED)
        self._cleanup_task_resources()

    def _complete_processing(self):
        if self.is_cleaning_up: return
        self.log_message.emit("🎉 所有文件处理任务已完成！")
        self._change_state(ProcessingState.COMPLETED)
        summary = {"summary": {"success": self.completed_files, "failed": self.failed_files}}
        self.processing_completed.emit(summary)
        self._cleanup_task_resources()

    def _change_state(self, new_state: ProcessingState):
        self.current_state = new_state
        self.state_changed.emit(new_state)

    def _cleanup_task_resources(self):
        """清理当前任务的所有资源"""
        if self.is_cleaning_up: 
            return
        self.is_cleaning_up = True
        self.pause_event.set()
        
        # 停止队列检查，避免清理过程中的管道错误
        if hasattr(self, 'queue_check_timer'):
            self.queue_check_timer.stop()
        self.log_message.emit("🧹 正在清理当前任务资源...")

        # 1. 优雅关闭进程池
        if self.pre_process_pool:
            try:
                self.pre_process_pool.shutdown(wait=False, cancel_futures=True)
                self.log_message.emit("   - 预处理池已关闭")
            except Exception as e:
                self.log_message.emit(f"   - 预处理池关闭异常: {e}")

        if self.post_process_pool:
            try:
                # 发送结束信号
                max_workers = getattr(self.post_process_pool, '_max_workers', 8)
                for _ in range(max_workers):
                    try: 
                        self.result_queue.put(None, timeout=0.1)
                    except: 
                        pass
                self.post_process_pool.shutdown(wait=False, cancel_futures=True)
                self.log_message.emit("   - 后处理池已关闭")
            except Exception as e:
                self.log_message.emit(f"   - 后处理池关闭异常: {e}")

        # 2. 关闭识别进程（支持多进程）
        if self.recognition_processes:
            try:
                # 向每个识别进程发送停止信号
                for _ in self.recognition_processes:
                    try:
                        self.audio_queue.put(None, timeout=0.1)
                    except:
                        pass

                # 等待所有识别进程结束
                for i, process in enumerate(self.recognition_processes):
                    if process.is_alive():
                        process.join(timeout=2)
                        if process.is_alive():
                            process.terminate()
                            self.log_message.emit(f"   - 识别进程 {i} 已强制终止")
            except Exception as e:
                self.log_message.emit(f"   - 识别进程关闭异常: {e}")

        # 3. 清空所有队列 - 静默处理
        for q in [self.task_queue, self.audio_queue, self.result_queue, self.progress_queue, self.log_queue, self.engine_status_queue]:
            try:
                while not q.empty():
                    q.get_nowait()
            except:
                pass

        # 4. 强制关闭残留进程
        try:
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            for child in children:
                try:
                    if 'ffmpeg' in child.name().lower() or 'python' in child.name().lower():
                        child.terminate()
                except:
                    pass
            
            # 等待进程结束
            time.sleep(1)
            for child in children:
                try:
                    if child.is_running():
                        child.kill()
                except:
                    pass
        except Exception as e:
            self.log_message.emit(f"   - 进程清理异常: {e}")
        
        # 5. 强制垃圾回收
        gc.collect()

        # 6. 重置状态
        self.recognition_processes = []  # 清空识别进程列表
        self._engine_ready = False
        self.pre_process_pool = None
        self.post_process_pool = None

        # 7. 恢复队列检查定时器
        if hasattr(self, 'queue_check_timer') and not self._is_shutting_down:
            self.queue_check_timer.start(500)

        if self.current_state not in [ProcessingState.COMPLETED, ProcessingState.CANCELLED, ProcessingState.ERROR]:
            self._change_state(ProcessingState.IDLE)
        elif not self._is_shutting_down:
            QTimer.singleShot(100, lambda: self._change_state(ProcessingState.IDLE))
        
        self.log_message.emit("✨ 任务资源清理完毕")
        self._reset_task_state()
        
    def shutdown(self):
        """当主程序关闭时调用，执行最终清理。"""
        self._is_shutting_down = True
        self.pause_event.set()
        self.log_message.emit("应用正在关闭，执行最后清理...")
        if hasattr(self, 'queue_check_timer'):
            self.queue_check_timer.stop()
        if hasattr(self, 'memory_monitor_timer'):
            self.memory_monitor_timer.stop()
        self.resource_monitor.stop_monitoring()

        if self.current_state in [ProcessingState.ENGINE_STARTING, ProcessingState.PROCESSING]:
            self.cancel_processing()
        else:
            self._cleanup_task_resources()
        
        try:
            self.manager.shutdown()
        except Exception as e:
            self.log_message.emit(f"关闭进程管理器时出错: {e}")
        
        self.log_message.emit("所有后台服务已关闭。")
