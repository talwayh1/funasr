# qt_compat.py
# -*- coding: utf-8 -*-
"""
Qt兼容性层 - 自动适配PyQt6和PySide6 (修复版)
- 修复了sip模块在PySide6环境下的兼容性问题。
"""

import sys

# 尝试导入Qt库，优先使用PySide6，回退到PyQt6
QT_API = None
sip = None

try:
    # 尝试导入PySide6
    from PySide6.QtCore import QThread, QObject, Signal as pyqtSignal, QTimer, QSettings, QMutex, Qt
    from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                                  QWidget, QLabel, QPushButton, QProgressBar, QTextEdit,
                                  QFileDialog, QMessageBox, QListWidget, QGroupBox,
                                  QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox,
                                  QSlider, QTabWidget, QSplitter, QFrame,
                                  QListWidgetItem, QGridLayout, QLineEdit)
    from PySide6.QtGui import QFont, QIcon, QPixmap, QDragEnterEvent, QDropEvent, QDragMoveEvent
    
    # 为PySide6环境创建一个模拟的sip对象
    class MockSip:
        @staticmethod
        def isdeleted(obj):
            # PySide6中，我们假设对象只要存在引用就不会被意外删除
            # 这个检查主要是为了防止PyQt下的C++对象已销毁但Python对象仍在的情况
            return obj is None
    
    sip = MockSip()
    QT_API = "PySide6"
    print("[OK] 使用PySide6 (Qt官方推荐)")
    
except ImportError:
    try:
        # 回退到PyQt6
        from PyQt6.QtCore import QThread, QObject, pyqtSignal, QTimer, QSettings, QMutex, Qt
        from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                                    QWidget, QLabel, QPushButton, QProgressBar, QTextEdit,
                                    QFileDialog, QMessageBox, QListWidget, QGroupBox,
                                    QCheckBox, QSpinBox, QDoubleSpinBox, QComboBox,
                                    QSlider, QTabWidget, QSplitter, QFrame,
                                    QListWidgetItem, QGridLayout, QLineEdit)
        from PyQt6.QtGui import QFont, QIcon, QPixmap, QDragEnterEvent, QDropEvent, QDragMoveEvent
        
        # 从PyQt6中导入真实的sip模块
        from PyQt6 import sip
        
        QT_API = "PyQt6"
        print("[OK] 使用PyQt6 (兼容模式)")
        
    except ImportError:
        print("[ERROR] 错误：未找到PyQt6或PySide6")
        print("请安装其中一个:")
        print("  pip install PySide6  # 官方推荐")
        print("  pip install PyQt6   # 兼容选项")
        # 即使失败，也提供一个模拟对象，防止其他文件导入时直接崩溃
        class MockSip:
            @staticmethod
            def isdeleted(obj): return True
        sip = MockSip()
        sys.exit(1)

# 导出所有Qt组件
__all__ = [
    'QT_API', 'sip',
    'QThread', 'QObject', 'pyqtSignal', 'QTimer', 'QMutex', 'QSettings', 'Qt',
    'QApplication', 'QMainWindow', 'QVBoxLayout', 'QHBoxLayout',
    'QWidget', 'QLabel', 'QPushButton', 'QProgressBar', 'QTextEdit',
    'QFileDialog', 'QMessageBox', 'QListWidget', 'QGroupBox',
    'QCheckBox', 'QSpinBox', 'QDoubleSpinBox', 'QComboBox',
    'QSlider', 'QTabWidget', 'QSplitter', 'QFrame',
    'QListWidgetItem', 'QGridLayout', 'QLineEdit',
    'QFont', 'QIcon', 'QPixmap', 'QDragEnterEvent', 'QDropEvent', 'QDragMoveEvent',
]
