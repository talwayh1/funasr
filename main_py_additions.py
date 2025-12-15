# -*- coding: utf-8 -*-
"""
main.py 需要添加的新方法
将这些方法添加到 MainWindow 类中
"""

# 在 _setup_connections 之后添加

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

# 修改现有方法

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
    """添加文件到列表（新方法）"""
    for file_path in file_paths:
        if Path(file_path).suffix.lower() in self.supported_extensions:
            self.file_list_widget.add_file(file_path)

def _add_folder_to_list(self, folder_path: str):
    """添加文件夹到列表（新方法）"""
    # 使用后台线程扫描文件夹
    self.scanner_worker = FileScannerWorker(self.supported_extensions)
    self.scanner_thread = QThread()
    self.scanner_worker.moveToThread(self.scanner_thread)
    self.scanner_worker.file_found.connect(lambda f: self.file_list_widget.add_file(f))
    self.scanner_worker.finished.connect(self.scanner_thread.quit)
    self.scanner_thread.finished.connect(self.scanner_thread.deleteLater)
    self.scanner_thread.started.connect(lambda: self.scanner_worker.run([folder_path]))
    self.scanner_thread.start()

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
        f"所有任务已执行完毕。\\n成功: {results['summary']['success']}, 失败: {results['summary']['failed']}"
    )

    # 不自动清空列表，让用户查看状态
    # self.clear_file_list()

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
