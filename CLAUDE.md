# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 基本要求

- **语言**: 始终使用简体中文回复
- **代码注释**: 使用中文编写所有代码注释
- **提交信息**: Git commit message 使用中文

## 环境信息

- **Python**: 3.10.18 (conda环境: `funasr2-gpu`)
- **PyTorch**: 2.1.2 (GPU版本，支持CUDA 12.1)
- **硬件**: NVIDIA GeForce RTX 4060
- **运行模式**: CPU+GPU智能自适应（有GPU时自动使用GPU，否则降级到CPU）

## 版本信息

- **当前版本**: v5.10
- **更新日期**: 2025-10-20

## 项目概述

基于FunASR的音视频转写工具，具有PySide6图形界面。核心功能：

- 音视频语音识别（ASR）
- 多格式字幕生成（SRT、TXT、MD、JSON、DOCX、PDF）
- FFSubSync字幕精确同步（支持Silero VAD，见 `SILERO_DEPLOYMENT.md`）
- 断点续传和批量处理
- 内存优化和资源监控
- 模拟模式（无需FunASR即可测试UI）

## 常用命令

### 运行应用

```bash
# 方式1：启动脚本（推荐）
run_funasr2.cmd

# 方式2：直接运行（需手动激活conda环境）
conda activate funasr2-gpu
python launcher.py

# 开发调试（跳过launcher包装器）
python main.py
```

### 下载模型

```bash
# 下载FunASR模型到 model_cache/modelscope/
python download_models.py

# 下载Silero VAD模型（用于FFSubSync）
python download_silero.py
```

### 打包应用

```bash
# 完整打包流程
打包.cmd

# 或手动执行步骤：
conda activate funasr2-gpu
pyinstaller --clean -y funasr.spec
```

**注意**: 打包配置在 `funasr.spec` 中，包含PyTorch DLL、CUDA库、模型文件等配置。

## 核心架构

### 三阶段流水线架构

项目采用多进程队列架构，将处理任务分为三个阶段：

```
文件输入 → [预处理队列] → [识别队列] → [后处理队列] → 完成
           (CPU密集)       (GPU/CPU)      (IO密集)
```

**预处理阶段** (`pre_processing_worker` in `pipeline_workers.py`):
- FFmpeg音频提取
- VAD语音活动检测
- 音频格式转换

**识别阶段** (`recognition_worker` in `pipeline_workers.py`):
- FunASR语音识别（或模拟模式）
- 支持GPU加速
- 动态批处理

**后处理阶段** (`post_processing_worker` in `pipeline_workers.py`):
- 生成多种格式字幕
- FFSubSync精确同步（可选）
- DOCX/PDF文档生成（可选）

### 关键模块说明

**`launcher.py`** - 启动包装器
- 多进程环境初始化（`multiprocessing.freeze_support()`）
- PyTorch DLL路径配置（打包环境必需）
- GPU/CPU自动检测
- 详细启动日志记录

**`main.py`** - GUI主应用
- `VideoSubtitleTool`: 主窗口类
- `GPUDetector`: GPU检测和设备选择
- `DropAreaListWidget`: 拖放文件列表组件
- `FileScannerWorker`: 后台文件扫描

**`processing_controller.py`** - 处理控制核心
- `ProcessingController`: 协调整个流水线
- `ProcessingConfig`: 配置数据类（设备、格式、VAD等）
- `ProgressManager`: 断点续传管理
- `ResourceMonitor`: 系统资源监控（内存、进程数）
- `ProcessingStatistics`: 统计信息收集

**`pipeline_workers.py`** - 三阶段工作进程
- 包含所有worker函数的实现
- 内存监控和垃圾回收逻辑
- FFmpeg进程限流机制

**`ffmpeg_manager.py`** - FFmpeg管理
- 自动检测系统FFmpeg
- 必要时自动下载FFmpeg
- 提供统一的FFmpeg/FFprobe路径接口

**`silero_manager.py`** - Silero VAD模型管理（v5.10新增）
- 本地模型加载（优先）
- PyTorch Hub回退机制
- FFSubSync环境配置
- 详见 `SILERO_DEPLOYMENT.md`

**`qt_compat.py`** - Qt兼容层
- 统一Qt导入接口（支持PySide6/PyQt6/PyQt5）
- 跨版本信号/槽兼容

**`utils.py`** - 辅助工具
- 文件清理、路径处理等

### 关键数据流

1. **用户添加文件** → GUI文件列表
2. **开始处理** → `ProcessingController.start_processing()`
3. **文件入队** → 预处理队列 (`multiprocessing.Queue`)
4. **预处理worker** → 提取音频 → 识别队列
5. **识别worker** → ASR识别 → 后处理队列
6. **后处理worker** → 生成字幕 → 完成
7. **进度更新** → 通过Qt信号更新GUI

### 断点续传机制

- 进度文件: `processing_progress.json`（自动生成）
- `ProgressManager` 跟踪已完成/失败的文件
- 重启后自动跳过已处理文件
- 可通过GUI清除进度重新处理

### 内存管理

- `ResourceMonitor` 实时监控内存使用
- 超过阈值（默认85%）时触发垃圾回收
- 每个worker进程独立监控内存
- FFmpeg进程限流（避免同时运行过多实例）

## 重要开发注意事项

### 多进程和打包

**关键**: 项目使用 `multiprocessing` 进行并行处理，在Windows打包环境中必须：

1. 使用 `spawn` 启动方式（在 `launcher.py` 中配置）
2. 调用 `multiprocessing.freeze_support()`（在 `launcher.py` 中）
3. 主入口必须在 `if __name__ == '__main__'` 块中

**错误示例**:
```python
# ❌ 这会导致打包后无法启动子进程
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoSubtitleTool()
    window.show()
```

**正确示例**:
```python
# ✅ 正确的打包兼容方式
def main_launcher():
    multiprocessing.freeze_support()
    multiprocessing.set_start_method('spawn', force=True)
    # ... 初始化和启动应用

if __name__ == '__main__':
    main_launcher()
```

### PyTorch DLL打包问题

打包环境中必须显式配置PyTorch DLL路径（见 `launcher.py:89-110`）：

```python
if getattr(sys, 'frozen', False):
    os.add_dll_directory(sys._MEIPASS)
    # 添加torch/lib目录
    torch_lib = os.path.join(sys._MEIPASS, 'torch', 'lib')
    if os.path.exists(torch_lib):
        os.add_dll_directory(torch_lib)
```

所有必需的DLL在 `funasr.spec` 的 `binaries` 列表中配置。

### FFSubSync集成

使用Silero VAD时，必须在调用FFSubSync前确保模型可用（见 `pipeline_workers.py:113-116`）：

```python
if vad_method == 'silero':
    log_queue.put("检查 Silero VAD 模型...")
    ensure_silero_for_ffsubsync()  # 从 silero_manager 导入
    log_queue.put("✅ Silero 模型已就绪")
```

### 模拟模式开发

无需FunASR模型即可测试UI和流程（见 `processing_controller.py` 中的配置）：
- 识别阶段会生成模拟识别结果
- 可快速迭代GUI和流程逻辑
- 在 `recognition_worker` 中检测FunASR不可用时自动启用

### 编码问题

所有Python文件使用UTF-8编码（文件头: `# -*- coding: utf-8 -*-`）
处理外部进程输出时需指定编码：

```python
result = subprocess.run(cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='ignore')
```

## 目录结构

```
funasrui/
├── launcher.py              # 启动包装器（主入口）
├── main.py                  # GUI主应用
├── processing_controller.py # 处理控制核心
├── pipeline_workers.py      # 三阶段worker实现
├── ffmpeg_manager.py        # FFmpeg管理
├── silero_manager.py        # Silero VAD管理
├── qt_compat.py            # Qt兼容层
├── utils.py                # 工具函数
├── download_models.py      # FunASR模型下载
├── download_silero.py      # Silero模型下载
├── funasr.spec             # PyInstaller打包配置
├── run_funasr2.cmd         # 运行脚本
├── 打包.cmd                 # 打包脚本
├── model_cache/            # 模型缓存目录
│   ├── modelscope/        # FunASR模型
│   └── silero-vad/        # Silero VAD模型
├── config/                 # 配置文件
├── resources/              # 资源文件
└── SILERO_DEPLOYMENT.md    # Silero部署文档
```

## 依赖管理

项目使用conda环境管理依赖，核心依赖：

- **PySide6**: GUI框架
- **PyTorch**: 深度学习框架（GPU版本）
- **FunASR**: 语音识别引擎
- **moviepy**: 视频处理
- **psutil**: 系统资源监控
- **ffsubsync**: 字幕精校（外部命令行工具）

**注意**: `requirements.txt` 文件编码异常，实际依赖以conda环境为准。使用 `conda list` 查看完整依赖列表。
