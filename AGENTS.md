# 仓库指南

始终用中文回复我

## 项目结构与模块组织
FunASR2 以 Windows 上的 PySide6 GUI 封装 FunASR 流水线。运行入口是 `main.py`，由 `processing_controller.py` 与 `pipeline_workers.py` 负责前后处理、ASR 与 FFmpeg 协作。通用工具集中在 `utils.py`，环境与硬件相关逻辑分别位于 `ffmpeg_manager.py`、`silero_manager.py` 与 `qt_compat.py`。运行时配置放在 `config/*.json`，Qt 资源在 `resources/resources.qrc`，主题样式存于 `styles/default.qss`。构建与 PyInstaller 生成物位于 `build/` 与 `dist/`，长期缓存存放于 `model_cache/`，调试日志落在 `logs/`。

## 业务流程概览
GUI 启动后先完成依赖检查并根据 GPU 可用性设定默认设备。用户通过拖拽或文件选择器加入媒体，点击“开始”时 `ProcessingController` 进入引擎启动阶段，独立进程加载 FunASR `AutoModel` 并在 `engine_status_queue` 报告状态。预处理池读取任务队列，使用 FFmpeg 提取音频、必要时执行 VFR→CFR 转换与音量分析，同时将进度推送到 `progress_queue`。识别进程消费音频队列，按设备能力动态调整批量参数完成 ASR 输出。结果进入后处理池，生成多种格式字幕文本并调用 FFSubSync（若启用）进行二次校准，再写回磁盘。整个过程中 `log_queue` 驱动界面日志，完成或出错时控制器统一清理进程、队列和缓存文件并更新 UI 状态。

## 构建、测试与开发命令
- `conda env create -f environment_funasr2_gpu.yml` 创建 GPU 开发环境。
- `conda activate funasr2-gpu`
- `python download_models.py` 与 `python download_silero.py` 下载 ModelScope 与 Silero 资源到 `model_cache/`。
- `python main.py` 在开发模式启动 GUI；`python launcher.py` 复现打包后启动与 DLL 处理流程。
- `pyinstaller funasr.spec` 在 `dist/FunASR` 生成 Windows 可执行包。

## 代码风格与命名约定
项目使用 Python 3.10+，统一四空格缩进，函数采用 snake_case，类名使用 CamelCase。共享状态通过 dataclass 与 Enum 表达，新增结构需保持一致。保持显式 import，并通过 `qt_compat` 间接调用 PySide6 以兼顾打包环境。新增配置时先扩展 JSON，再在 `ProcessingConfig` 中提供默认值。字符串保持 UTF-8，并沿用现有的中英双语日志风格。

## 测试指引
目前 Smoke Test 以独立脚本为主。执行 `python test_ffsubsync_optimization.py` 校验 FFSubSync 配置，运行 `python test_silero_deployment.py` 确认 Silero VAD 可用。新增测试可与现有脚本并排，或改写为 `test_*.py` 的 pytest 风格，需确保控制台输出稳定。若模型缺失应快速失败，并在脚本头部说明依赖资源。

## 提交与合并请求规范
Git 历史使用模块范围+简短命题句，偶尔附带版本标签（示例：`Add FFSubSync advanced parameter pass-through`）。保持这一格式：主题行不超 70 字符，使用祈使句与现在时。PR 描述需包含：1) 现存问题与解决思路概述，2) 涉及的模块或配置文件，3) 验证证据（测试命令或 GUI 截图），4) 关联的 Issue 或任务编号。提醒审阅者同步模型缓存或打包步骤，避免遗漏。

## 模型与资源管理
大型 ASR/VAD 模型不应入库，依赖下载脚本与既有的 `MODELSCOPE_CACHE` 约定。若贡献引入新模型，请记录目标目录与校验哈希，并更新 `silero_manager.py` 或相关辅助模块以保证运行时自动下载。
