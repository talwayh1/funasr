# 界面优化实施指南

## 概述

本次优化实现了三个优先级功能：
1. **优先级1：文件列表增强** - 显示文件元信息、状态跟踪、单个删除
2. **优先级2：输出管理功能** - 查看生成的文件、打开输出文件夹
3. **优先级3：配置持久化** - 保存用户设置、配置预设

## 已创建的新文件

### 1. enhanced_file_list.py
增强的文件列表组件，包含：
- `FileStatus`: 文件状态枚举（等待中、提取音频、识别中、已完成、失败等）
- `FileInfo`: 文件信息数据类
- `FileItemWidget`: 自定义文件列表项Widget
- `MetadataLoader`: 后台加载文件元信息（大小、时长、格式）
- `EnhancedFileListWidget`: 增强的文件列表主组件

**特性：**
- 显示文件大小、时长、格式
- 彩色状态指示器
- 单个文件删除按钮
- 右键菜单（删除、打开文件位置、查看错误）
- 异步加载元信息（不阻塞UI）

### 2. output_manager.py
输出管理组件，包含：
- `OutputManagerDialog`: 输出文件管理对话框
- `QuickOutputPanel`: 快速输出面板（嵌入主窗口）
- `find_output_files()`: 查找源文件对应的输出文件

**特性：**
- 树形显示源文件和输出文件
- 双击打开文件
- 一键打开输出文件夹
- 按文件类型分组显示

### 3. config_manager.py
配置管理组件，包含：
- `UserConfig`: 用户配置数据类
- `ConfigManager`: 配置管理器（使用QSettings）
- `ConfigPresets`: 配置预设（快速模式、标准模式、完整模式）

**特性：**
- 自动保存用户设置
- 恢复窗口位置和大小
- 记住最后使用的文件夹
- 三种预设模式快速切换

## main.py 修改说明

### 需要手动完成的修改

由于main.py文件较大且修改较多，以下是需要手动修改的部分：

#### 1. 删除旧的方法

删除以下方法（已被新组件替代）：
```python
# 删除 FileScannerWorker 类（已移至 enhanced_file_list.py）
# 删除 DropAreaListWidget 类（已被 EnhancedFileListWidget 替代）
# 删除 _on_scanner_finished 方法
# 删除 _add_paths_to_list 方法
# 删除 _add_single_file 方法
```

#### 2. 添加新方法

将 `main_py_additions.py` 中的方法添加到 MainWindow 类中：
- `_load_saved_settings()` - 加载保存的设置
- `_save_current_settings()` - 保存当前设置
- `_on_preset_changed()` - 预设配置变化
- `_on_setting_changed()` - 设置变化时切换到"自定义"
- `_show_output_manager()` - 显示输出管理对话框
- `_add_files_to_list()` - 添加文件到列表
- `_add_folder_to_list()` - 添加文件夹到列表

#### 3. 修改现有方法

替换以下方法的实现（参考 `main_py_additions.py`）：
- `select_files()` - 使用保存的最后文件夹
- `select_folder()` - 使用保存的最后文件夹
- `clear_file_list()` - 调用新的 clear_all()
- `_update_run_button_state()` - 使用 get_all_files()
- `start_processing()` - 保存设置，设置输出文件夹
- `_on_processing_completed()` - 收集输出文件
- `closeEvent()` - 保存设置

## 快速集成方案

如果您想快速测试优化功能，可以：

### 方案A：使用备份恢复（推荐）

```bash
# 1. 备份已经完成
cp /opt/funasrui/main.py /opt/funasrui/main.py.backup

# 2. 手动编辑 main.py，参考 main_py_additions.py 中的代码

# 3. 如果出问题，恢复备份
cp /opt/funasrui/main.py.backup /opt/funasrui/main.py
```

### 方案B：创建测试版本

```bash
# 创建一个新的测试文件
cp /opt/funasrui/main.py /opt/funasrui/main_optimized.py

# 在 main_optimized.py 中进行修改和测试

# 测试通过后替换
mv /opt/funasrui/main_optimized.py /opt/funasrui/main.py
```

## 测试清单

完成修改后，请测试以下功能：

### 文件列表增强
- [ ] 添加文件后能看到文件大小、时长
- [ ] 文件状态正确显示（等待中→处理中→完成）
- [ ] 单个删除按钮工作正常
- [ ] 右键菜单功能正常
- [ ] 拖拽文件/文件夹正常

### 输出管理
- [ ] 处理完成后"查看所有结果"按钮可用
- [ ] 输出管理对话框正确显示文件
- [ ] 双击可以打开文件
- [ ] "打开输出文件夹"按钮工作正常

### 配置持久化
- [ ] 关闭程序后重新打开，设置被保存
- [ ] 窗口位置和大小被记住
- [ ] 预设模式切换正常
- [ ] 修改设置后自动切换到"自定义"
- [ ] 最后使用的文件夹被记住

## 已知问题和注意事项

### 1. FileScannerWorker 位置
`FileScannerWorker` 已从 main.py 移至 enhanced_file_list.py，但导入语句已更新。

### 2. 文件列表信号变化
旧版使用 `filesDropped` 信号，新版使用 `files_changed` 信号。

### 3. 配置文件位置
配置保存在系统默认位置：
- Windows: `HKEY_CURRENT_USER\Software\FunASR\VideoSubtitleTool`
- Linux: `~/.config/FunASR/VideoSubtitleTool.conf`
- macOS: `~/Library/Preferences/com.FunASR.VideoSubtitleTool.plist`

### 4. 元信息加载性能
大量文件时，元信息加载可能需要时间。已使用后台线程异步加载，不会阻塞UI。

### 5. FFprobe 依赖
文件元信息（时长、格式）需要 FFprobe。如果 FFprobe 不可用，会显示"未知"。

## 下一步优化建议

完成这三个优先级后，可以考虑：

1. **优先级4：实时进度优化**
   - 在文件列表中显示每个文件的进度条
   - 添加"当前处理"区域

2. **优先级5：设备选择界面**
   - 手动选择CPU/GPU
   - 显示GPU信息

3. **优先级6：界面布局优化**
   - 使用QTabWidget分离基础/高级设置
   - 更清爽的布局

## 技术支持

如果遇到问题：
1. 检查 `funasr_startup.log` 和 `logs/app.log`
2. 确保所有新文件都在正确位置
3. 检查导入语句是否正确
4. 使用备份恢复后重试

## 版本信息

- 优化版本: v5.10
- 基础版本: v5.9
- 优化日期: 2025-12-15
- 优化内容: 文件列表增强、输出管理、配置持久化
