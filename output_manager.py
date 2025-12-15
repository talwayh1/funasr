# -*- coding: utf-8 -*-
"""
输出管理组件
支持：查看生成的文件、打开输出文件夹、快速预览字幕
"""
from pathlib import Path
from qt_compat import *
import os
import subprocess
import platform


class OutputManagerDialog(QDialog):
    """输出管理对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("输出文件管理")
        self.setMinimumSize(700, 500)
        self.output_files = {}  # file_path -> [output_files]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 顶部说明
        info_label = QLabel("以下是已生成的输出文件，双击可打开文件")
        layout.addWidget(info_label)

        # 文件树
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["文件名", "类型", "大小", "路径"])
        self.tree_widget.setColumnWidth(0, 250)
        self.tree_widget.setColumnWidth(1, 80)
        self.tree_widget.setColumnWidth(2, 80)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree_widget)

        # 底部按钮
        button_layout = QHBoxLayout()

        self.open_folder_button = QPushButton("打开输出文件夹")
        self.open_folder_button.clicked.connect(self._open_selected_folder)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_output_files)

        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.accept)

        button_layout.addWidget(self.open_folder_button)
        button_layout.addWidget(self.refresh_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def add_source_file(self, source_file: str, output_files: list):
        """添加源文件及其输出文件"""
        self.output_files[source_file] = output_files
        self._add_to_tree(source_file, output_files)

    def _add_to_tree(self, source_file: str, output_files: list):
        """添加到树形控件"""
        source_path = Path(source_file)

        # 创建父节点（源文件）
        parent_item = QTreeWidgetItem(self.tree_widget)
        parent_item.setText(0, source_path.name)
        parent_item.setText(1, "源文件")
        parent_item.setText(2, self._format_size(source_path.stat().st_size))
        parent_item.setText(3, str(source_path.parent))
        parent_item.setData(0, Qt.ItemDataRole.UserRole, str(source_path))

        # 添加子节点（输出文件）
        for output_file in output_files:
            if not Path(output_file).exists():
                continue

            output_path = Path(output_file)
            child_item = QTreeWidgetItem(parent_item)
            child_item.setText(0, output_path.name)
            child_item.setText(1, output_path.suffix[1:].upper())
            child_item.setText(2, self._format_size(output_path.stat().st_size))
            child_item.setText(3, str(output_path.parent))
            child_item.setData(0, Qt.ItemDataRole.UserRole, str(output_path))

            # 根据文件类型设置图标颜色
            if output_path.suffix == '.srt':
                child_item.setForeground(0, QColor("#2196F3"))
            elif output_path.suffix == '.txt':
                child_item.setForeground(0, QColor("#4CAF50"))
            elif output_path.suffix == '.json':
                child_item.setForeground(0, QColor("#FF9800"))

        parent_item.setExpanded(True)

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """双击打开文件"""
        file_path = item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            self._open_file(file_path)

    def _open_file(self, file_path: str):
        """打开文件"""
        try:
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", file_path])
            else:  # Linux
                subprocess.run(["xdg-open", file_path])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件：{e}")

    def _open_selected_folder(self):
        """打开选中项的文件夹"""
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.information(self, "提示", "请先选择一个文件")
            return

        file_path = current_item.data(0, Qt.ItemDataRole.UserRole)
        if file_path:
            folder_path = str(Path(file_path).parent)
            self._open_file(folder_path)

    def refresh_output_files(self):
        """刷新输出文件列表"""
        self.tree_widget.clear()
        for source_file, output_files in self.output_files.items():
            # 重新扫描输出文件
            updated_files = [f for f in output_files if Path(f).exists()]
            self._add_to_tree(source_file, updated_files)


class QuickOutputPanel(QWidget):
    """快速输出面板（嵌入主窗口）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.output_folder = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 输出文件夹标签
        self.folder_label = QLabel("输出位置: 未设置")
        self.folder_label.setStyleSheet("color: #666;")

        # 打开文件夹按钮
        self.open_folder_button = QPushButton("打开输出文件夹")
        self.open_folder_button.setEnabled(False)
        self.open_folder_button.clicked.connect(self._open_output_folder)

        # 查看结果按钮
        self.view_results_button = QPushButton("查看所有结果")
        self.view_results_button.setEnabled(False)

        layout.addWidget(self.folder_label)
        layout.addStretch()
        layout.addWidget(self.open_folder_button)
        layout.addWidget(self.view_results_button)

    def set_output_folder(self, folder_path: str):
        """设置输出文件夹"""
        self.output_folder = folder_path
        self.folder_label.setText(f"输出位置: {folder_path}")
        self.open_folder_button.setEnabled(True)
        self.view_results_button.setEnabled(True)

    def _open_output_folder(self):
        """打开输出文件夹"""
        if not self.output_folder:
            return

        try:
            if platform.system() == "Windows":
                os.startfile(self.output_folder)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", self.output_folder])
            else:  # Linux
                subprocess.run(["xdg-open", self.output_folder])
        except Exception as e:
            QMessageBox.warning(self, "打开失败", f"无法打开文件夹：{e}")


def find_output_files(source_file: str, config) -> list:
    """根据配置查找源文件对应的输出文件"""
    source_path = Path(source_file)
    stem = source_path.stem
    output_dir = source_path.parent

    output_files = []

    # 根据配置检查各类输出文件
    if config.generate_srt:
        srt_file = output_dir / f"{stem}.srt"
        if srt_file.exists():
            output_files.append(str(srt_file))

    if config.generate_srt_txt:
        srt_txt_file = output_dir / f"{stem}.srt.txt"
        if srt_txt_file.exists():
            output_files.append(str(srt_txt_file))

    if config.generate_txt:
        txt_file = output_dir / f"{stem}.txt"
        if txt_file.exists():
            output_files.append(str(txt_file))

    if config.generate_json:
        json_file = output_dir / f"{stem}.json"
        if json_file.exists():
            output_files.append(str(json_file))

    if config.generate_txt_md:
        md_file = output_dir / f"{stem}.md.txt"
        if md_file.exists():
            output_files.append(str(md_file))

    if config.generate_docx:
        docx_file = output_dir / f"{stem}.docx"
        if docx_file.exists():
            output_files.append(str(docx_file))

    if config.generate_pdf:
        pdf_file = output_dir / f"{stem}.pdf"
        if pdf_file.exists():
            output_files.append(str(pdf_file))

    return output_files
