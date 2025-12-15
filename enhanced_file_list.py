# -*- coding: utf-8 -*-
"""
增强的文件列表组件
支持：文件元信息显示、状态跟踪、单个删除、右键菜单
"""
from pathlib import Path
from enum import Enum
from qt_compat import *
import os
import subprocess
import json
from threading import Thread
from queue import Queue


class FileStatus(Enum):
    """文件处理状态"""
    PENDING = ("等待中", "#808080")
    EXTRACTING = ("提取音频", "#2196F3")
    RECOGNIZING = ("识别中", "#FF9800")
    POST_PROCESSING = ("后处理", "#9C27B0")
    COMPLETED = ("已完成", "#4CAF50")
    FAILED = ("失败", "#F44336")
    SKIPPED = ("已跳过", "#607D8B")


class FileInfo:
    """文件信息数据类"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = Path(file_path).name
        self.file_size = 0
        self.duration = ""
        self.format_info = ""
        self.status = FileStatus.PENDING
        self.progress = 0
        self.error_message = ""
        self.metadata_loaded = False

    def get_size_str(self) -> str:
        """获取格式化的文件大小"""
        if self.file_size == 0:
            return "计算中..."
        size_mb = self.file_size / (1024 * 1024)
        if size_mb < 1024:
            return f"{size_mb:.1f} MB"
        else:
            return f"{size_mb/1024:.2f} GB"

    def get_duration_str(self) -> str:
        """获取格式化的时长"""
        return self.duration if self.duration else "获取中..."


class FileItemWidget(QWidget):
    """文件列表项的自定义Widget"""
    delete_requested = pyqtSignal(str)  # 请求删除文件

    def __init__(self, file_info: FileInfo):
        super().__init__()
        self.file_info = file_info
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        # 状态指示器（彩色圆点）
        self.status_label = QLabel("●")
        self.status_label.setFixedWidth(20)
        self._update_status_color()

        # 文件名（加粗）
        self.name_label = QLabel(self.file_info.file_name)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.name_label.setMinimumWidth(200)

        # 文件大小
        self.size_label = QLabel(self.file_info.get_size_str())
        self.size_label.setFixedWidth(80)

        # 时长
        self.duration_label = QLabel(self.file_info.get_duration_str())
        self.duration_label.setFixedWidth(80)

        # 状态文本
        self.status_text_label = QLabel(self.file_info.status.value[0])
        self.status_text_label.setFixedWidth(80)

        # 进度条（初始隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setMaximumHeight(15)
        self.progress_bar.setVisible(False)

        # 删除按钮
        self.delete_button = QPushButton("✕")
        self.delete_button.setFixedSize(25, 25)
        self.delete_button.setToolTip("从列表移除")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        # 添加到布局
        layout.addWidget(self.status_label)
        layout.addWidget(self.name_label)
        layout.addWidget(self.size_label)
        layout.addWidget(self.duration_label)
        layout.addWidget(self.status_text_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.delete_button)
        layout.addStretch()

    def _update_status_color(self):
        """更新状态颜色"""
        color = self.file_info.status.value[1]
        self.status_label.setStyleSheet(f"color: {color}; font-size: 16px;")

    def _on_delete_clicked(self):
        """删除按钮点击"""
        self.delete_requested.emit(self.file_info.file_path)

    def update_metadata(self, size: int, duration: str, format_info: str):
        """更新元信息"""
        self.file_info.file_size = size
        self.file_info.duration = duration
        self.file_info.format_info = format_info
        self.file_info.metadata_loaded = True

        self.size_label.setText(self.file_info.get_size_str())
        self.duration_label.setText(self.file_info.get_duration_str())

    def update_status(self, status: FileStatus, progress: int = 0):
        """更新处理状态"""
        self.file_info.status = status
        self.file_info.progress = progress

        self._update_status_color()
        self.status_text_label.setText(status.value[0])

        # 显示/隐藏进度条
        if status in [FileStatus.EXTRACTING, FileStatus.RECOGNIZING, FileStatus.POST_PROCESSING]:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(progress)
        else:
            self.progress_bar.setVisible(False)


class MetadataLoader(QObject):
    """后台加载文件元信息（优化版：限制并发，延迟加载）"""
    metadata_ready = pyqtSignal(str, int, str, str)  # file_path, size, duration, format

    def __init__(self, max_workers: int = 3, max_queue_size: int = 100):
        super().__init__()
        self.queue = Queue()
        self.running = False
        self.threads = []
        self.max_workers = max_workers  # 最大并发worker数
        self.max_queue_size = max_queue_size  # 最大队列大小
        self.processed_count = 0
        self.skip_metadata = False  # 大量文件时跳过元信息加载

    def start(self):
        """启动后台线程池"""
        if self.running:
            return
        self.running = True

        # 启动多个worker线程
        for i in range(self.max_workers):
            thread = Thread(target=self._worker_loop, daemon=True, name=f"MetadataWorker-{i}")
            thread.start()
            self.threads.append(thread)

    def stop(self):
        """停止所有后台线程"""
        self.running = False
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1)
        self.threads.clear()

    def add_file(self, file_path: str):
        """添加文件到加载队列"""
        # 如果跳过元信息加载，直接返回默认值
        if self.skip_metadata:
            self.metadata_ready.emit(file_path, 0, "跳过", "")
            return

        # 限制队列大小，防止内存溢出
        if self.queue.qsize() < self.max_queue_size:
            self.queue.put(file_path)

    def set_skip_metadata(self, skip: bool):
        """设置是否跳过元信息加载（大量文件时使用）"""
        self.skip_metadata = skip

    def _worker_loop(self):
        """工作线程循环"""
        while self.running:
            try:
                file_path = self.queue.get(timeout=0.5)
                self._load_metadata(file_path)
                self.processed_count += 1
            except:
                continue

    def _load_metadata(self, file_path: str):
        """加载文件元信息"""
        try:
            # 获取文件大小
            size = os.path.getsize(file_path)

            # 使用ffprobe获取时长和格式
            duration = ""
            format_info = ""

            try:
                # 尝试调用ffprobe
                from ffmpeg_manager import get_ffprobe_path
                ffprobe_path = get_ffprobe_path()

                cmd = [
                    ffprobe_path,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    file_path
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    encoding='utf-8',
                    errors='ignore'
                )

                if result.returncode == 0:
                    data = json.loads(result.stdout)

                    # 获取时长
                    if 'format' in data and 'duration' in data['format']:
                        duration_sec = float(data['format']['duration'])
                        minutes = int(duration_sec // 60)
                        seconds = int(duration_sec % 60)
                        duration = f"{minutes}:{seconds:02d}"

                    # 获取格式信息
                    if 'format' in data and 'format_name' in data['format']:
                        format_info = data['format']['format_name'].split(',')[0].upper()

            except Exception:
                # ffprobe失败，使用默认值
                duration = "未知"
                format_info = Path(file_path).suffix[1:].upper()

            # 发送信号
            self.metadata_ready.emit(file_path, size, duration, format_info)

        except Exception:
            # 加载失败，发送默认值
            self.metadata_ready.emit(file_path, 0, "错误", "")


class EnhancedFileListWidget(QListWidget):
    """增强的文件列表Widget（性能优化版）"""
    files_changed = pyqtSignal()  # 文件列表变化信号
    loading_progress = pyqtSignal(int, int)  # 加载进度信号 (当前, 总数)

    # 性能优化阈值
    LARGE_FILE_THRESHOLD = 500  # 超过此数量视为大量文件
    SKIP_METADATA_THRESHOLD = 1000  # 超过此数量跳过元信息加载

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.file_items = {}  # file_path -> FileItemWidget
        self.file_infos = {}  # file_path -> FileInfo

        # 元信息加载器（限制并发）
        self.metadata_loader = MetadataLoader(max_workers=3, max_queue_size=100)
        self.metadata_loader.metadata_ready.connect(self._on_metadata_ready)
        self.metadata_loader.start()

        # 设置右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # 性能优化标志
        self.is_large_file_mode = False

    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        """拖拽放下事件"""
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            # 发送信号给主窗口处理
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._emit_files_dropped(files))

    def _emit_files_dropped(self, files):
        """延迟发送文件拖放信号"""
        # 这个方法会被主窗口的filesDropped信号替代
        pass

    def add_file(self, file_path: str):
        """添加文件到列表"""
        if file_path in self.file_items:
            return  # 已存在

        # 创建文件信息
        file_info = FileInfo(file_path)
        self.file_infos[file_path] = file_info

        # 创建列表项
        item = QListWidgetItem(self)
        item.setSizeHint(QSize(0, 35))  # 设置行高

        # 创建自定义Widget
        widget = FileItemWidget(file_info)
        widget.delete_requested.connect(self.remove_file)
        self.file_items[file_path] = widget

        # 设置到列表
        self.addItem(item)
        self.setItemWidget(item, widget)

        # 异步加载元信息
        self.metadata_loader.add_file(file_path)

        self.files_changed.emit()

    def remove_file(self, file_path: str):
        """从列表移除文件"""
        if file_path not in self.file_items:
            return

        # 找到对应的item并删除
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if widget and widget.file_info.file_path == file_path:
                self.takeItem(i)
                break

        # 清理引用
        del self.file_items[file_path]
        del self.file_infos[file_path]

        self.files_changed.emit()

    def clear_all(self):
        """清空所有文件"""
        self.clear()
        self.file_items.clear()
        self.file_infos.clear()
        self.files_changed.emit()

    def get_all_files(self) -> list:
        """获取所有文件路径"""
        return list(self.file_items.keys())

    def update_file_status(self, file_path: str, status: FileStatus, progress: int = 0):
        """更新文件状态"""
        if file_path in self.file_items:
            self.file_items[file_path].update_status(status, progress)

    def _on_metadata_ready(self, file_path: str, size: int, duration: str, format_info: str):
        """元信息加载完成"""
        if file_path in self.file_items:
            self.file_items[file_path].update_metadata(size, duration, format_info)

    def _show_context_menu(self, position):
        """显示右键菜单"""
        item = self.itemAt(position)
        if not item:
            return

        widget = self.itemWidget(item)
        if not widget:
            return

        menu = QMenu(self)

        # 删除操作
        remove_action = menu.addAction("从列表移除")
        remove_action.triggered.connect(lambda: self.remove_file(widget.file_info.file_path))

        # 如果失败，添加重试选项
        if widget.file_info.status == FileStatus.FAILED:
            menu.addSeparator()
            retry_action = menu.addAction("重试此文件")
            # TODO: 连接到重试逻辑

            if widget.file_info.error_message:
                error_action = menu.addAction("查看错误详情")
                error_action.triggered.connect(
                    lambda: QMessageBox.warning(self, "错误详情", widget.file_info.error_message)
                )

        # 打开文件位置
        menu.addSeparator()
        open_folder_action = menu.addAction("打开文件位置")
        open_folder_action.triggered.connect(
            lambda: self._open_file_location(widget.file_info.file_path)
        )

        menu.exec(self.mapToGlobal(position))

    def _open_file_location(self, file_path: str):
        """打开文件所在文件夹"""
        import platform
        folder_path = str(Path(file_path).parent)

        if platform.system() == "Windows":
            os.startfile(folder_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", folder_path])
        else:  # Linux
            subprocess.run(["xdg-open", folder_path])

    def add_files_batch(self, file_paths: list):
        """批量添加文件（性能优化）"""
        if not file_paths:
            return

        # 检查是否进入大量文件模式
        total_files = len(self.file_items) + len(file_paths)
        if total_files > self.SKIP_METADATA_THRESHOLD:
            self.is_large_file_mode = True
            self.metadata_loader.set_skip_metadata(True)
        elif total_files > self.LARGE_FILE_THRESHOLD:
            self.is_large_file_mode = True

        # 暂时阻止信号发送
        self.blockSignals(True)

        added_count = 0
        for file_path in file_paths:
            if file_path not in self.file_items:
                # 创建文件信息
                file_info = FileInfo(file_path)
                self.file_infos[file_path] = file_info

                # 创建列表项
                item = QListWidgetItem(self)
                item.setSizeHint(QSize(0, 35))

                # 创建自定义Widget
                widget = FileItemWidget(file_info)
                widget.delete_requested.connect(self.remove_file)
                self.file_items[file_path] = widget

                # 设置到列表
                self.addItem(item)
                self.setItemWidget(item, widget)

                # 异步加载元信息（大量文件时可能跳过）
                self.metadata_loader.add_file(file_path)

                added_count += 1

                # 每100个文件强制处理一次事件，避免界面卡死
                if added_count % 100 == 0:
                    QApplication.processEvents()

        # 恢复信号并发送一次
        self.blockSignals(False)
        self.files_changed.emit()

        # 发送加载进度
        self.loading_progress.emit(len(self.file_items), len(self.file_items))

    def closeEvent(self, event):
        """关闭事件"""
        self.metadata_loader.stop()
        super().closeEvent(event)


class FileScannerWorker(QObject):
    """文件扫描工作线程（优化版：批量发送信号）"""
    file_found = pyqtSignal(str)  # 单个文件发现（保留兼容性）
    files_batch_found = pyqtSignal(list)  # 批量文件发现（新增）
    finished = pyqtSignal()
    progress_updated = pyqtSignal(int, int)  # 当前数量, 总数

    def __init__(self, supported_extensions: list, batch_size: int = 50):
        super().__init__()
        self.supported_extensions = supported_extensions
        self.batch_size = batch_size  # 批量大小
        self._stop_flag = False

    def stop(self):
        """停止扫描"""
        self._stop_flag = True

    def run(self, paths: list):
        """扫描文件（批量优化版）"""
        all_files = []
        batch_buffer = []

        for path in paths:
            if self._stop_flag:
                break

            path_obj = Path(path)

            if path_obj.is_file():
                # 单个文件
                if path_obj.suffix.lower() in self.supported_extensions:
                    batch_buffer.append(str(path_obj))

                    # 达到批量大小，发送信号
                    if len(batch_buffer) >= self.batch_size:
                        self.files_batch_found.emit(batch_buffer.copy())
                        all_files.extend(batch_buffer)
                        self.progress_updated.emit(len(all_files), -1)  # -1表示总数未知
                        batch_buffer.clear()

            elif path_obj.is_dir():
                # 文件夹：递归扫描
                for file_path in path_obj.rglob('*'):
                    if self._stop_flag:
                        break

                    if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                        batch_buffer.append(str(file_path))

                        # 达到批量大小，发送信号
                        if len(batch_buffer) >= self.batch_size:
                            self.files_batch_found.emit(batch_buffer.copy())
                            all_files.extend(batch_buffer)
                            self.progress_updated.emit(len(all_files), -1)
                            batch_buffer.clear()

        # 发送剩余的文件
        if batch_buffer and not self._stop_flag:
            self.files_batch_found.emit(batch_buffer.copy())
            all_files.extend(batch_buffer)
            self.progress_updated.emit(len(all_files), len(all_files))

        self.finished.emit()
