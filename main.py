# main.py (v5.10 - 界面优化版：增强文件列表、输出管理、配置持久化)
import sys
import os
import torch
import multiprocessing
import subprocess
from pathlib import Path
from datetime import datetime

# 统一从qt_compat导入，确保兼容性
from qt_compat import *
# 导入重构后的核心控制器和配置类
from processing_controller import ProcessingController, ProcessingConfig, ProcessingState
# 导入ffmpeg检查工具
from ffmpeg_manager import ensure_ffmpeg_is_ready
# 导入新的优化组件
from enhanced_file_list import EnhancedFileListWidget, FileStatus, FileScannerWorker
from output_manager import OutputManagerDialog, QuickOutputPanel, find_output_files
from config_manager import ConfigManager, ConfigPresets, UserConfig

# 尝试导入moviepy，用于启动检查
try:
    from moviepy.editor import VideoFileClip
except ImportError:
    VideoFileClip = None

# --- ffsubsync 的可用性检查 ---
def check_ffsubsync_availability():
    """检查ffsubsync命令是否在系统路径中可用"""
    try:
        # 【已修复】增加 encoding 和 errors 参数，增强在Windows下的兼容性
        subprocess.run(
            ['ffsubsync', '--version'],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='ignore'
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False

# 通过环境变量控制FFSubSync功能的启用/禁用
FFSUBSYNC_AVAILABLE = (os.getenv("APP_DISABLE_FFSUBSYNC", "0") not in ["1", "true", "True"]) \
                      and check_ffsubsync_availability()

def setup_model_cache():
    """设置模型缓存目录和性能优化环境变量"""
    # 修复打包后的路径问题
    if getattr(sys, 'frozen', False):
        # 打包后的环境
        project_root = Path(sys.executable).parent
    else:
        # 开发环境
        project_root = Path(__file__).parent

    cache_dir = project_root / "model_cache" / "modelscope"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # 设置所有相关的缓存环境变量，与download_models.py保持一致
    env_vars = {
        'MODELSCOPE_CACHE': str(cache_dir),
        'HF_HOME': str(cache_dir),
        'TRANSFORMERS_CACHE': str(cache_dir),
        'HF_DATASETS_CACHE': str(cache_dir),
        'TORCH_HOME': str(cache_dir),
    }

    for key, value in env_vars.items():
        os.environ[key] = value

    # 性能优化：控制PyTorch/BLAS线程数，防止与FFmpeg争抢CPU
    # 每个ASR进程内部使用单线程，避免过度并发
    threading_vars = {
        'OMP_NUM_THREADS': '1',
        'OPENBLAS_NUM_THREADS': '1',
        'MKL_NUM_THREADS': '1',
        'VECLIB_MAXIMUM_THREADS': '1',
        'NUMEXPR_NUM_THREADS': '1',
    }

    for key, value in threading_vars.items():
        os.environ.setdefault(key, value)

    # 仅在主进程中打印一次
    if multiprocessing.current_process().name == 'MainProcess':
        print(f"[FOLDER] 模型缓存路径已设置为: {cache_dir}")

setup_model_cache()

# FileScannerWorker 已移至 enhanced_file_list.py

class GPUDetector:
    """检测GPU"""
    def __init__(self):
        self.cuda_available = torch.cuda.is_available()
        self.recommended_device = "cuda" if self.cuda_available else "cpu"

# DropAreaListWidget 已被 EnhancedFileListWidget 替代

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FunASR 高效处理工具 v5.10 - 界面优化版")

        # 配置管理器（优先级3）
        self.config_manager = ConfigManager()
        self.user_config = self.config_manager.load_config()

        # 恢复窗口位置和大小
        self.setGeometry(
            self.user_config.window_x,
            self.user_config.window_y,
            self.user_config.window_width,
            self.user_config.window_height
        )

        self.is_processing = False
        self.scanner_thread = None
        self.scanner_worker = None

        self.gpu_detector = GPUDetector()
        self.device = self.gpu_detector.recommended_device

        self.processing_controller = ProcessingController(self)
        self.supported_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.wav', '.mp3', '.flac', '.m4a']

        # 输出管理（优先级2）
        self.output_manager_dialog = None
        self.completed_files = {}  # source_file -> [output_files]

        self._setup_ui()
        self._setup_connections()
        self._load_saved_settings()  # 加载保存的设置
        self._check_dependencies()
        self.log_message(f"系统检测到最佳设备: {self.device.upper()}")
        self.log_message("[OK] UI已就绪。引擎将在开始处理时按需加载。")

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        top_layout = QHBoxLayout()
        self.select_file_button = QPushButton("选择文件")
        self.select_folder_button = QPushButton("选择文件夹")
        self.clear_button = QPushButton("清空列表")
        top_layout.addWidget(self.select_file_button)
        top_layout.addWidget(self.select_folder_button)
        top_layout.addWidget(self.clear_button)
        top_layout.addStretch()

        # 使用增强的文件列表（优先级1）
        self.file_list_widget = EnhancedFileListWidget()

        settings_group = QGroupBox("处理设置")
        settings_layout = QGridLayout(settings_group)

        # 添加预设选择（优先级3）
        settings_layout.addWidget(QLabel("配置预设:"), 0, 0)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(ConfigPresets.get_preset_names())
        self.preset_combo.setCurrentText("自定义")
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        settings_layout.addWidget(self.preset_combo, 0, 1)

        settings_layout.addWidget(QLabel("输出格式:"), 1, 0)
        self.srt_checkbox = QCheckBox("SRT字幕"); self.srt_checkbox.setChecked(True)
        self.srt_txt_checkbox = QCheckBox("SRT格式(.txt)")
        self.txt_checkbox = QCheckBox("TXT文本"); self.txt_checkbox.setChecked(False)
        self.json_checkbox = QCheckBox("JSON数据")
        self.txt_md_checkbox = QCheckBox("TXT (Markdown格式)")
        self.docx_checkbox = QCheckBox("DOCX (.docx)")
        self.pdf_checkbox = QCheckBox("PDF (.pdf)")
        format_layout = QHBoxLayout()
        format_layout.addWidget(self.srt_checkbox)
        format_layout.addWidget(self.srt_txt_checkbox)
        format_layout.addWidget(self.txt_checkbox)
        format_layout.addWidget(self.json_checkbox)
        format_layout.addWidget(self.txt_md_checkbox)
        format_layout.addWidget(self.docx_checkbox)
        format_layout.addWidget(self.pdf_checkbox)
        settings_layout.addLayout(format_layout, 1, 1)

        # 添加checkbox变化监听，自动切换到"自定义"
        for checkbox in [self.srt_checkbox, self.srt_txt_checkbox, self.txt_checkbox,
                        self.json_checkbox, self.txt_md_checkbox, self.docx_checkbox, self.pdf_checkbox]:
            checkbox.stateChanged.connect(self._on_setting_changed)

        self.cfr_conversion_checkbox = QCheckBox("启用VFR转CFR (修复手机录屏等变帧率视频的音画同步问题)")
        self.cfr_conversion_checkbox.stateChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.cfr_conversion_checkbox, 2, 0, 1, 2)

        # FFSubSync 选项组
        self.ffsubsync_checkbox = QCheckBox("启用FFSubSync校准 (对识别后的字幕进行二次精校)")
        self.ffsubsync_checkbox.setChecked(True)  # 默认勾选
        self.ffsubsync_checkbox.stateChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.ffsubsync_checkbox, 3, 0, 1, 2)

        # 【新增】FFSubSync 高级选项
        ffsubsync_advanced_layout = QHBoxLayout()
        ffsubsync_advanced_layout.addWidget(QLabel("  ├─ VAD算法:"))
        self.vad_combo = QComboBox()
        self.vad_combo.addItems(["silero (最准确,深度学习)", "webrtc (默认,快速)", "auditok (低质量音频)"])
        self.vad_combo.setCurrentIndex(0)  # 默认选择 silero
        self.vad_combo.setToolTip("Silero: 最准确（推荐）; WebRTC: 快速通用; Auditok: 适合低质量音频")
        self.vad_combo.currentIndexChanged.connect(self._on_setting_changed)
        ffsubsync_advanced_layout.addWidget(self.vad_combo)

        ffsubsync_advanced_layout.addWidget(QLabel("  最大偏移(秒):"))
        self.max_offset_spinbox = QSpinBox()
        self.max_offset_spinbox.setRange(10, 300)
        self.max_offset_spinbox.setValue(60)
        self.max_offset_spinbox.setToolTip("限制字幕搜索范围，值越小速度越快")
        self.max_offset_spinbox.valueChanged.connect(self._on_setting_changed)
        ffsubsync_advanced_layout.addWidget(self.max_offset_spinbox)
        ffsubsync_advanced_layout.addStretch()
        settings_layout.addLayout(ffsubsync_advanced_layout, 4, 0, 1, 2)

        # 新增：断点续传选项
        self.resume_checkbox = QCheckBox("启用断点续传 (跳过已完成的文件)")
        self.resume_checkbox.setChecked(True)
        self.resume_checkbox.stateChanged.connect(self._on_setting_changed)
        settings_layout.addWidget(self.resume_checkbox, 5, 0, 1, 2)

        self.progress_bar = QProgressBar()
        # --- 核心改动 ---
        self.status_label = QLabel("就绪。请添加文件并点击开始。")
        
        # 新增：统计信息显示
        self.stats_label = QLabel("统计信息: 等待开始...")
        
        self.log_widget = QTextEdit(); self.log_widget.setReadOnly(True)

        # 输出管理面板（优先级2）
        self.output_panel = QuickOutputPanel()
        self.output_panel.view_results_button.clicked.connect(self._show_output_manager)

        bottom_layout = QHBoxLayout()
        # --- 核心改动 ---
        self.run_button = QPushButton("开始处理"); self.run_button.setEnabled(False)
        self.pause_button = QPushButton("暂停"); self.pause_button.setEnabled(False)  # 新增
        self.stop_button = QPushButton("停止处理"); self.stop_button.setEnabled(False)
        bottom_layout.addWidget(self.run_button)
        bottom_layout.addWidget(self.pause_button)  # 新增
        bottom_layout.addWidget(self.stop_button)
        bottom_layout.addStretch()

        main_layout.addLayout(top_layout)
        main_layout.addWidget(QLabel("文件列表 (可拖拽文件或文件夹到此区域):"))
        main_layout.addWidget(self.file_list_widget)
        main_layout.addWidget(settings_group)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.stats_label)  # 新增：统计信息显示
        main_layout.addWidget(self.output_panel)  # 新增：输出管理面板
        main_layout.addWidget(QLabel("日志:"))
        main_layout.addWidget(self.log_widget)
        main_layout.addLayout(bottom_layout)

    def _setup_connections(self):
        self.select_file_button.clicked.connect(self.select_files)
        self.select_folder_button.clicked.connect(self.select_folder)
        self.clear_button.clicked.connect(self.clear_file_list)
        # 增强文件列表的信号连接
        self.file_list_widget.files_changed.connect(self._update_run_button_state)
        self.run_button.clicked.connect(self.start_processing)
        self.pause_button.clicked.connect(self.toggle_pause)  # 新增：暂停按钮连接
        self.stop_button.clicked.connect(self.stop_processing)

        self.processing_controller.state_changed.connect(self._on_processing_state_changed)
        self.processing_controller.progress_updated.connect(self._on_processing_progress)
        self.processing_controller.log_message.connect(self.log_message)
        self.processing_controller.error_occurred.connect(self._on_processing_error)
        self.processing_controller.processing_completed.connect(self._on_processing_completed)
        # 新增：统计信息和内存警告信号连接
        self.processing_controller.stats_updated.connect(self._on_stats_updated)
        self.processing_controller.memory_warning.connect(self._on_memory_warning)
        # --- 核心改动 ---
        # 不再需要 engine_ready 信号，因为它现在是处理流程的一部分

    def _load_saved_settings(self):
        """加载保存的设置（优先级3）"""
        # 恢复输出格式设置
        self.srt_checkbox.setChecked(self.user_config.generate_srt)
        self.srt_txt_checkbox.setChecked(self.user_config.generate_srt_txt)
        self.txt_checkbox.setChecked(self.user_config.generate_txt)
        self.json_checkbox.setChecked(self.user_config.generate_json)
        self.txt_md_checkbox.setChecked(self.user_config.generate_txt_md)
        self.docx_checkbox.setChecked(self.user_config.generate_docx)
        self.pdf_checkbox.setChecked(self.user_config.generate_pdf)

        # 恢复处理选项
        self.cfr_conversion_checkbox.setChecked(self.user_config.cfr_enabled)
        self.ffsubsync_checkbox.setChecked(self.user_config.ffsubsync_enabled)
        self.resume_checkbox.setChecked(self.user_config.enable_resume)

        # 恢复VAD算法选择
        vad_index = 0
        if self.user_config.ffsubsync_vad == "webrtc":
            vad_index = 1
        elif self.user_config.ffsubsync_vad == "auditok":
            vad_index = 2
        self.vad_combo.setCurrentIndex(vad_index)

        # 恢复最大偏移量
        self.max_offset_spinbox.setValue(self.user_config.ffsubsync_max_offset)

    def _save_current_settings(self):
        """保存当前设置（优先级3）"""
        # 更新配置对象
        self.user_config.generate_srt = self.srt_checkbox.isChecked()
        self.user_config.generate_srt_txt = self.srt_txt_checkbox.isChecked()
        self.user_config.generate_txt = self.txt_checkbox.isChecked()
        self.user_config.generate_json = self.json_checkbox.isChecked()
        self.user_config.generate_txt_md = self.txt_md_checkbox.isChecked()
        self.user_config.generate_docx = self.docx_checkbox.isChecked()
        self.user_config.generate_pdf = self.pdf_checkbox.isChecked()

        self.user_config.cfr_enabled = self.cfr_conversion_checkbox.isChecked()
        self.user_config.ffsubsync_enabled = self.ffsubsync_checkbox.isChecked()
        self.user_config.enable_resume = self.resume_checkbox.isChecked()

        # VAD算法
        vad_text = self.vad_combo.currentText()
        self.user_config.ffsubsync_vad = vad_text.split()[0]

        # 最大偏移量
        self.user_config.ffsubsync_max_offset = self.max_offset_spinbox.value()

        # 窗口位置和大小
        self.user_config.window_width = self.width()
        self.user_config.window_height = self.height()
        self.user_config.window_x = self.x()
        self.user_config.window_y = self.y()

        # 保存到磁盘
        self.config_manager.save_config(self.user_config)

    def _on_preset_changed(self, preset_name: str):
        """预设配置变化（优先级3）"""
        if preset_name == "自定义":
            return  # 不做任何改变

        preset = ConfigPresets.get_preset_by_name(preset_name)
        if not preset:
            return

        # 应用预设配置
        self.srt_checkbox.setChecked(preset.get("generate_srt", True))
        self.srt_txt_checkbox.setChecked(preset.get("generate_srt_txt", False))
        self.txt_checkbox.setChecked(preset.get("generate_txt", False))
        self.json_checkbox.setChecked(preset.get("generate_json", False))
        self.txt_md_checkbox.setChecked(preset.get("generate_txt_md", False))
        self.docx_checkbox.setChecked(preset.get("generate_docx", False))
        self.pdf_checkbox.setChecked(preset.get("generate_pdf", False))

        self.cfr_conversion_checkbox.setChecked(preset.get("cfr_enabled", False))
        self.ffsubsync_checkbox.setChecked(preset.get("ffsubsync_enabled", True))
        self.resume_checkbox.setChecked(preset.get("enable_resume", True))

        if "ffsubsync_vad" in preset:
            vad = preset["ffsubsync_vad"]
            if vad == "silero":
                self.vad_combo.setCurrentIndex(0)
            elif vad == "webrtc":
                self.vad_combo.setCurrentIndex(1)
            elif vad == "auditok":
                self.vad_combo.setCurrentIndex(2)

        if "ffsubsync_max_offset" in preset:
            self.max_offset_spinbox.setValue(preset["ffsubsync_max_offset"])

    def _on_setting_changed(self):
        """设置变化时自动切换到"自定义"（优先级3）"""
        # 如果当前不是"自定义"，切换到"自定义"
        if self.preset_combo.currentText() != "自定义":
            # 阻止信号触发，避免递归
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentText("自定义")
            self.preset_combo.blockSignals(False)

    def _show_output_manager(self):
        """显示输出管理对话框（优先级2）"""
        if not self.output_manager_dialog:
            self.output_manager_dialog = OutputManagerDialog(self)

        # 添加已完成的文件
        for source_file, output_files in self.completed_files.items():
            self.output_manager_dialog.add_source_file(source_file, output_files)

        self.output_manager_dialog.exec()
        

    def select_files(self):
        """选择文件（修改版）"""
        # 使用保存的最后文件夹
        start_dir = self.user_config.last_folder if self.user_config.last_folder else ""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择音频/视频文件",
            start_dir,
            f"媒体文件 ({' '.join(['*' + ext for ext in self.supported_extensions])})"
        )
        if files:
            # 保存最后使用的文件夹
            self.user_config.last_folder = str(Path(files[0]).parent)
            self._add_files_to_list(files)

    def select_folder(self):
        """选择文件夹（修改版）"""
        start_dir = self.user_config.last_folder if self.user_config.last_folder else ""
        folder = QFileDialog.getExistingDirectory(self, "选择包含媒体文件的文件夹", start_dir)
        if folder:
            self.user_config.last_folder = folder
            self._add_folder_to_list(folder)

    def _add_files_to_list(self, file_paths: list):
        """添加文件到列表（新方法 - 批量优化版）"""
        # 过滤支持的文件
        valid_files = [
            file_path for file_path in file_paths
            if Path(file_path).suffix.lower() in self.supported_extensions
        ]

        if not valid_files:
            return

        # 使用批量添加
        if len(valid_files) > 10:
            self.log_message(f"[INFO] 正在添加 {len(valid_files)} 个文件...")
            self.file_list_widget.add_files_batch(valid_files)
            self.log_message(f"[SUCCESS] 已添加 {len(valid_files)} 个文件")
        else:
            # 少量文件使用单个添加
            for file_path in valid_files:
                self.file_list_widget.add_file(file_path)

    def _add_folder_to_list(self, folder_path: str):
        """添加文件夹到列表（新方法 - 批量优化版）"""
        # 使用后台线程扫描文件夹
        self.scanner_worker = FileScannerWorker(self.supported_extensions, batch_size=50)
        self.scanner_thread = QThread()
        self.scanner_worker.moveToThread(self.scanner_thread)

        # 连接批量信号（性能优化）
        self.scanner_worker.files_batch_found.connect(self.file_list_widget.add_files_batch)
        self.scanner_worker.progress_updated.connect(self._on_scan_progress)
        self.scanner_worker.finished.connect(self._on_scan_finished)
        self.scanner_worker.finished.connect(self.scanner_thread.quit)
        self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)

        self.scanner_thread.started.connect(lambda: self.scanner_worker.run([folder_path]))
        self.scanner_thread.start()

        # 显示扫描提示
        self.log_message(f"[INFO] 正在扫描文件夹: {folder_path}")

    def _on_scan_progress(self, current: int, total: int):
        """扫描进度更新"""
        if total > 0:
            self.log_message(f"[INFO] 已扫描 {current}/{total} 个文件")
        else:
            self.log_message(f"[INFO] 已扫描 {current} 个文件...")

    def _on_scan_finished(self):
        """扫描完成"""
        total = len(self.file_list_widget.get_all_files())
        self.log_message(f"[SUCCESS] 扫描完成，共添加 {total} 个文件")

        # 如果是大量文件，提示用户
        if total > self.file_list_widget.LARGE_FILE_THRESHOLD:
            self.log_message(f"[INFO] 检测到大量文件({total}个)，已启用性能优化模式")
        if total > self.file_list_widget.SKIP_METADATA_THRESHOLD:
            self.log_message(f"[INFO] 文件数量过多，已跳过元信息加载以提升性能")

    def clear_file_list(self):
        """清空文件列表（修改版）"""
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_worker.stop()
            self.scanner_thread.quit()
            self.scanner_thread.wait()

        self.file_list_widget.clear_all()
        self.log_message("[NOTE] 文件列表已清空")

    def _update_run_button_state(self):
        """更新开始按钮状态（修改版）"""
        has_files = len(self.file_list_widget.get_all_files()) > 0
        can_run = has_files and not self.is_processing
        self.run_button.setEnabled(can_run)

    def start_processing(self):
        """开始处理（修改版）"""
        if self.is_processing:
            return

        all_files = self.file_list_widget.get_all_files()
        if not all_files:
            QMessageBox.warning(self, "提示", "请先添加至少一个文件。")
            return

        if not any([self.srt_checkbox.isChecked(), self.srt_txt_checkbox.isChecked(),
                    self.txt_checkbox.isChecked(), self.json_checkbox.isChecked(),
                    self.txt_md_checkbox.isChecked(), self.docx_checkbox.isChecked(),
                    self.pdf_checkbox.isChecked()]):
            QMessageBox.warning(self, "提示", "请至少选择一种输出格式。")
            return

        # 保存当前设置
        self._save_current_settings()

        # 提取 VAD 算法
        vad_text = self.vad_combo.currentText()
        vad_method = vad_text.split()[0]

        config = ProcessingConfig(
            input_files=all_files,
            generate_srt=self.srt_checkbox.isChecked(),
            generate_srt_txt=self.srt_txt_checkbox.isChecked(),
            generate_txt=self.txt_checkbox.isChecked(),
            generate_json=self.json_checkbox.isChecked(),
            generate_txt_md=self.txt_md_checkbox.isChecked(),
            generate_docx=self.docx_checkbox.isChecked(),
            generate_pdf=self.pdf_checkbox.isChecked(),
            cfr_enabled=self.cfr_conversion_checkbox.isChecked(),
            ffsubsync_enabled=self.ffsubsync_checkbox.isChecked(),
            ffsubsync_vad=vad_method,
            ffsubsync_max_offset=self.max_offset_spinbox.value(),
            enable_resume=self.resume_checkbox.isChecked(),
            device=self.device
        )

        if self.processing_controller.start_processing(config):
            self.is_processing = True
            self._update_ui_for_processing_start()

            # 设置输出文件夹（取第一个文件的父目录）
            if all_files:
                output_folder = str(Path(all_files[0]).parent)
                self.output_panel.set_output_folder(output_folder)
        else:
            QMessageBox.warning(self, "无法开始", "无法启动处理流程，请检查日志获取详情。")

    def toggle_pause(self):
        """切换暂停状态"""
        if self.processing_controller.is_paused:
            self.processing_controller.resume_processing()
            self.pause_button.setText("暂停")
        else:
            self.processing_controller.pause_processing()
            self.pause_button.setText("恢复")

    def stop_processing(self):
        if self.processing_controller:
            self.processing_controller.cancel_processing()

    def _update_ui_for_processing_start(self):
        """更新UI状态 - 处理开始时"""
        self.run_button.setEnabled(False)
        self.pause_button.setEnabled(True)  # 新增
        self.stop_button.setEnabled(True)
        self.select_file_button.setEnabled(False)
        self.select_folder_button.setEnabled(False)
        self.clear_button.setEnabled(False)

    def _update_ui_for_processing_end(self):
        """更新UI状态 - 处理结束时"""
        self.is_processing = False
        self.pause_button.setEnabled(False)  # 新增
        self.pause_button.setText("暂停")  # 新增
        self.stop_button.setEnabled(False)
        self.run_button.setText("开始处理")
        self._update_run_button_state()
        self.select_file_button.setEnabled(True)
        self.select_folder_button.setEnabled(True)
        self.clear_button.setEnabled(True)

    def _on_processing_state_changed(self, state: ProcessingState):
        self.status_label.setText(f"状态: {state.value}")
        if state == ProcessingState.ENGINE_STARTING:
            self.run_button.setText("引擎启动中...")
        elif state == ProcessingState.PROCESSING:
            self.run_button.setText("处理中...")
        
        # 任何最终状态都会重置UI
        if state in [ProcessingState.COMPLETED, ProcessingState.ERROR, ProcessingState.CANCELLED, ProcessingState.IDLE]:
            self._update_ui_for_processing_end()

    def _on_processing_progress(self, progress, message):
        self.progress_bar.setValue(progress)
        self.status_label.setText(f"进度 {progress}%: {message}")

    def _on_processing_error(self, error_type, error_message):
        self.log_message(f"[ERROR] 发生错误 - {error_type}: {error_message}")
        QMessageBox.critical(self, error_type, error_message)

    def _on_processing_completed(self, results):
        """处理完成（修改版）"""
        self.log_message("[SUCCESS] 所有处理已完成！")

        # 收集输出文件
        all_files = self.file_list_widget.get_all_files()
        for source_file in all_files:
            output_files = find_output_files(source_file, self.processing_controller.config)
            if output_files:
                self.completed_files[source_file] = output_files

        QMessageBox.information(
            self,
            "处理完成",
            f"所有任务已执行完毕。\n成功: {results['summary']['success']}, 失败: {results['summary']['failed']}"
        )

        # 不自动清空列表，让用户查看状态
        # self.clear_file_list()

    def _on_stats_updated(self, stats_dict):
        """更新统计信息显示"""
        stats_text = (f"统计: 完成 {stats_dict['completed']}/{stats_dict['total']}, "
                     f"成功率 {stats_dict['success_rate']:.1f}%, "
                     f"峰值内存 {stats_dict['peak_memory']:.1f}%")
        self.stats_label.setText(stats_text)

    def _on_memory_warning(self, memory_percent):
        """处理内存警告"""
        QMessageBox.warning(self, "内存警告", 
                           f"内存使用率达到 {memory_percent:.1f}%\n"
                           f"建议暂停处理或关闭其他程序")

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.append(f"[{timestamp}] {message}")

    def closeEvent(self, event):
        """关闭事件（修改版）"""
        if self.is_processing:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "有任务正在处理中，确定要退出吗？后台进程将全部关闭。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        # 保存当前设置
        self._save_current_settings()

        self.log_message("应用即将退出，正在关闭所有后台服务...")
        if self.scanner_thread and self.scanner_thread.isRunning():
            self.scanner_worker.stop()
            self.scanner_thread.quit()
            self.scanner_thread.wait()

        self.processing_controller.shutdown()
        event.accept()

    def _check_dependencies(self):
        if not FFSUBSYNC_AVAILABLE:
            self.ffsubsync_checkbox.setChecked(False)
            self.ffsubsync_checkbox.setEnabled(False)
            self.ffsubsync_checkbox.setToolTip("未检测到 ffsubsync, 此功能不可用。请运行 pip install ffsubsync[all]")
            self.log_message("[WARNING] 未检测到 ffsubsync，字幕精校功能已禁用。")

        # 在代码中增加检查
        try:
            import win32com.client
            # 检查 Word 是否可用
        except ImportError:
            print("未安装 Microsoft Word，PDF 功能将禁用")

def start_app():
    # 【关键修复】spawn模式下，子进程会重新import整个模块
    # 必须确保只在主进程中创建GUI，否则会导致multiprocessing.Manager()重复启动失败
    import multiprocessing
    current_process = multiprocessing.current_process()

    # 只在主进程中启动GUI（进程名为'MainProcess'）
    if current_process.name != 'MainProcess':
        # 子进程不应该执行start_app()，直接返回
        return

    app = QApplication(sys.argv)

    # 修改moviepy检测逻辑，兼容打包环境 - moviepy 改为可选依赖
    moviepy_available = False
    try:
        if VideoFileClip is not None:
            moviepy_available = True
        else:
            # 在打包环境中重新尝试导入
            import moviepy.editor
            moviepy_available = True
    except ImportError:
        moviepy_available = False

    # moviepy 改为可选依赖，只警告不退出
    if not moviepy_available:
        print("[WARNING] 警告: moviepy 库未安装，视频处理功能可能受限。")

    if not ensure_ffmpeg_is_ready():
        print("[WARNING] 警告: FFmpeg环境未就绪，部分功能可能无法使用。")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    # 防止在打包环境中重复启动
    multiprocessing.freeze_support()
    
    # 只在真正的主进程中设置启动方法
    if multiprocessing.current_process().name == 'MainProcess':
        try:
            multiprocessing.set_start_method('spawn', force=True)
        except (RuntimeError, ValueError):
            pass
        
        start_app()