# -*- coding: utf-8 -*-
"""
配置管理组件
支持：保存和加载用户配置、配置预设
"""
from qt_compat import QSettings
from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class UserConfig:
    """用户配置数据类"""
    # 输出格式
    generate_srt: bool = True
    generate_srt_txt: bool = False
    generate_txt: bool = False
    generate_json: bool = False
    generate_txt_md: bool = False
    generate_docx: bool = False
    generate_pdf: bool = False

    # 处理选项
    cfr_enabled: bool = False
    ffsubsync_enabled: bool = True
    ffsubsync_vad: str = "silero"
    ffsubsync_max_offset: int = 60
    enable_resume: bool = True

    # 窗口设置
    window_width: int = 900
    window_height: int = 750
    window_x: int = 100
    window_y: int = 100

    # 最近使用的文件夹
    last_folder: str = ""


class ConfigManager:
    """配置管理器"""

    def __init__(self):
        self.settings = QSettings("FunASR", "VideoSubtitleTool")
        self.config = UserConfig()

    def load_config(self) -> UserConfig:
        """加载配置"""
        # 输出格式
        self.config.generate_srt = self.settings.value("generate_srt", True, type=bool)
        self.config.generate_srt_txt = self.settings.value("generate_srt_txt", False, type=bool)
        self.config.generate_txt = self.settings.value("generate_txt", False, type=bool)
        self.config.generate_json = self.settings.value("generate_json", False, type=bool)
        self.config.generate_txt_md = self.settings.value("generate_txt_md", False, type=bool)
        self.config.generate_docx = self.settings.value("generate_docx", False, type=bool)
        self.config.generate_pdf = self.settings.value("generate_pdf", False, type=bool)

        # 处理选项
        self.config.cfr_enabled = self.settings.value("cfr_enabled", False, type=bool)
        self.config.ffsubsync_enabled = self.settings.value("ffsubsync_enabled", True, type=bool)
        self.config.ffsubsync_vad = self.settings.value("ffsubsync_vad", "silero", type=str)
        self.config.ffsubsync_max_offset = self.settings.value("ffsubsync_max_offset", 60, type=int)
        self.config.enable_resume = self.settings.value("enable_resume", True, type=bool)

        # 窗口设置
        self.config.window_width = self.settings.value("window_width", 900, type=int)
        self.config.window_height = self.settings.value("window_height", 750, type=int)
        self.config.window_x = self.settings.value("window_x", 100, type=int)
        self.config.window_y = self.settings.value("window_y", 100, type=int)

        # 最近使用的文件夹
        self.config.last_folder = self.settings.value("last_folder", "", type=str)

        return self.config

    def save_config(self, config: UserConfig):
        """保存配置"""
        # 输出格式
        self.settings.setValue("generate_srt", config.generate_srt)
        self.settings.setValue("generate_srt_txt", config.generate_srt_txt)
        self.settings.setValue("generate_txt", config.generate_txt)
        self.settings.setValue("generate_json", config.generate_json)
        self.settings.setValue("generate_txt_md", config.generate_txt_md)
        self.settings.setValue("generate_docx", config.generate_docx)
        self.settings.setValue("generate_pdf", config.generate_pdf)

        # 处理选项
        self.settings.setValue("cfr_enabled", config.cfr_enabled)
        self.settings.setValue("ffsubsync_enabled", config.ffsubsync_enabled)
        self.settings.setValue("ffsubsync_vad", config.ffsubsync_vad)
        self.settings.setValue("ffsubsync_max_offset", config.ffsubsync_max_offset)
        self.settings.setValue("enable_resume", config.enable_resume)

        # 窗口设置
        self.settings.setValue("window_width", config.window_width)
        self.settings.setValue("window_height", config.window_height)
        self.settings.setValue("window_x", config.window_x)
        self.settings.setValue("window_y", config.window_y)

        # 最近使用的文件夹
        self.settings.setValue("last_folder", config.last_folder)

        # 立即同步到磁盘
        self.settings.sync()

    def get_config(self) -> UserConfig:
        """获取当前配置"""
        return self.config

    def reset_to_defaults(self):
        """重置为默认配置"""
        self.config = UserConfig()
        self.save_config(self.config)


# 配置预设
class ConfigPresets:
    """配置预设"""

    @staticmethod
    def get_quick_preset() -> Dict[str, Any]:
        """快速模式：仅生成SRT，不启用FFSubSync"""
        return {
            "generate_srt": True,
            "generate_srt_txt": False,
            "generate_txt": False,
            "generate_json": False,
            "generate_txt_md": False,
            "generate_docx": False,
            "generate_pdf": False,
            "cfr_enabled": False,
            "ffsubsync_enabled": False,
            "enable_resume": True,
        }

    @staticmethod
    def get_standard_preset() -> Dict[str, Any]:
        """标准模式：SRT + TXT，启用FFSubSync"""
        return {
            "generate_srt": True,
            "generate_srt_txt": False,
            "generate_txt": True,
            "generate_json": False,
            "generate_txt_md": False,
            "generate_docx": False,
            "generate_pdf": False,
            "cfr_enabled": False,
            "ffsubsync_enabled": True,
            "ffsubsync_vad": "silero",
            "ffsubsync_max_offset": 60,
            "enable_resume": True,
        }

    @staticmethod
    def get_complete_preset() -> Dict[str, Any]:
        """完整模式：所有格式，启用所有功能"""
        return {
            "generate_srt": True,
            "generate_srt_txt": True,
            "generate_txt": True,
            "generate_json": True,
            "generate_txt_md": True,
            "generate_docx": True,
            "generate_pdf": True,
            "cfr_enabled": True,
            "ffsubsync_enabled": True,
            "ffsubsync_vad": "silero",
            "ffsubsync_max_offset": 60,
            "enable_resume": True,
        }

    @staticmethod
    def get_preset_names() -> list:
        """获取所有预设名称"""
        return ["快速模式", "标准模式", "完整模式", "自定义"]

    @staticmethod
    def get_preset_by_name(name: str) -> Dict[str, Any]:
        """根据名称获取预设"""
        if name == "快速模式":
            return ConfigPresets.get_quick_preset()
        elif name == "标准模式":
            return ConfigPresets.get_standard_preset()
        elif name == "完整模式":
            return ConfigPresets.get_complete_preset()
        else:
            return {}  # 自定义模式返回空字典
