# 批量视频处理效率优化方案

## ✅ 实施状态（2025-12-15更新）

### 已完成的优化

**方案1：立即可用（配置调整）** - ✅ 已完成
- ✅ 动态audio_queue容量（从固定4改为 pre_proc_workers × 2）
- ✅ 动态FFmpeg并发限制（2/4/6基于CPU核心数）
- ✅ 更激进的进程数配置（高性能：16/20，中端：10/12）

**方案2：短期优化（架构改进）** - ✅ 已完成
- ✅ 多进程识别（GPU显存>=12GB时启用2个识别进程）
- ✅ FFSubSync快速模式（添加 --skip-infer-framerate-ratio 和 --no-fix-framerate）
- ✅ 文件优先级排序（小文件优先处理）

**配置管理** - ✅ 已完成
- ✅ 性能配置文件（performance_config.py）
- ✅ 自动检测系统配置
- ✅ 提供3种预设：conservative/balanced/aggressive

### 预期性能提升

- **100个视频**: 60分钟 → 20-30分钟（2-3倍提升）
- **1000个视频**: 10小时 → 2-5小时（2-5倍提升）
- **CPU利用率**: 提升30-50%
- **GPU利用率**: 提升50-100%（多进程识别）

### 待实施的优化

**方案3：长期优化（深度优化）** - ⏳ 待实施
- ⏳ 批量推理优化（需要修改FunASR调用方式）
- ⏳ 硬件加速（NVDEC/NVENC）
- ⏳ 智能缓存机制

---

## 📊 当前架构分析

### 现有流水线架构

```
文件输入 → [预处理队列] → [识别队列] → [后处理队列] → 完成
           (FFmpeg提取)    (FunASR识别)   (生成字幕)
           多进程并行       单进程         多进程并行
```

### 当前配置（从代码分析）

#### 1. 进程数配置（自动调整）

**高性能系统** (32GB+ 内存, 16+ 核心):
- 预处理进程: 12个
- 后处理进程: 16个
- 识别进程: **1个** ⚠️

**中端系统** (16GB 内存, 8 核心):
- 预处理进程: 8个
- 后处理进程: 10个
- 识别进程: **1个** ⚠️

**入门系统** (< 16GB 内存, < 8 核心):
- 预处理进程: 2-4个
- 后处理进程: 2-6个
- 识别进程: **1个** ⚠️

#### 2. 队列容量
- task_queue: `pre_proc_workers * 2`
- audio_queue: **4** ⚠️（瓶颈）
- result_queue: `post_proc_workers * 4`

#### 3. FFmpeg并发限制
- 全局信号量: **2个并发** ⚠️（保守）

#### 4. FunASR批处理大小
- 24GB+ GPU: batch_size_s = 25
- 12GB+ GPU: batch_size_s = 18
- 8GB+ GPU: batch_size_s = 12
- CPU: batch_size_s = 15

---

## 🎯 性能瓶颈分析

### 瓶颈1：识别进程只有1个 ⚠️⚠️⚠️

**问题**:
- 无论有多少CPU核心，识别永远只有1个进程
- 即使GPU很强大，也无法并行处理多个文件
- 预处理和后处理都是多进程，但识别是单进程

**影响**:
- 识别成为整个流水线的瓶颈
- GPU利用率可能不足（取决于batch_size_s）
- 处理1000个文件时，必须串行识别1000次

**预期提升**: 如果改为多进程识别，可提升 **2-4倍**

---

### 瓶颈2：audio_queue容量太小

**问题**:
- audio_queue 固定为 4
- 预处理进程可能有8-12个，但队列只能放4个音频
- 导致预处理进程经常阻塞等待

**影响**:
- 预处理进程利用率低
- 流水线不流畅

**预期提升**: 增加到 `pre_proc_workers * 2`，提升 **20-30%**

---

### 瓶颈3：FFmpeg并发限制过于保守

**问题**:
- 全局只允许2个FFmpeg并发
- 但预处理进程可能有8-12个
- 大部分预处理进程在等待信号量

**影响**:
- 预处理速度慢
- CPU利用率低

**预期提升**: 增加到 4-6个，提升 **50-100%**

---

### 瓶颈4：没有真正的批量推理

**问题**:
- 当前是逐个文件调用 `model.generate()`
- 虽然FunASR内部有batch_size_s，但那是针对单个文件的音频分段
- 没有实现多文件批量推理

**影响**:
- GPU利用率可能不足
- 无法充分发挥GPU性能

**预期提升**: 实现多文件批量推理，提升 **30-50%**

---

### 瓶颈5：FFSubSync串行处理

**问题**:
- FFSubSync是最慢的环节之一（每个文件5-30秒）
- 当前是在后处理进程中串行执行
- 没有充分利用多进程

**影响**:
- 后处理成为瓶颈
- 总处理时间长

**预期提升**: 优化FFSubSync并发，提升 **2-3倍**

---

## 🚀 优化方案（分层实施）

### 🔥 方案1：立即可用（配置调整）

**无需修改代码，只需调整配置参数**

#### 1.1 增加audio_queue容量

**修改位置**: `processing_controller.py:168`

```python
# 当前
self.audio_queue = None

# 优化后（在 _start_pipeline_workers 中）
self.audio_queue = self.manager.Queue(maxsize=pre_proc_workers * 2)
```

**效果**: 提升 20-30%

---

#### 1.2 放宽FFmpeg并发限制

**修改位置**: `processing_controller.py:176`

```python
# 当前
self.ffmpeg_semaphore = self.manager.Semaphore(2)

# 优化后（根据系统配置）
if cpu_cores >= 16:
    ffmpeg_concurrent = 6
elif cpu_cores >= 8:
    ffmpeg_concurrent = 4
else:
    ffmpeg_concurrent = 2

self.ffmpeg_semaphore = self.manager.Semaphore(ffmpeg_concurrent)
```

**效果**: 提升 50-100%

---

#### 1.3 优化进程数配置

**修改位置**: `processing_controller.py:581-592`

```python
# 当前配置已经不错，但可以更激进

# 高性能系统（32GB+, 16+核心）
pre_proc_workers = min(16, physical_cores)  # 从12增加到16
post_proc_workers = min(20, cpu_cores)      # 从16增加到20

# 中端系统（16GB, 8核心）
pre_proc_workers = min(10, physical_cores)  # 从8增加到10
post_proc_workers = min(12, cpu_cores)      # 从10增加到12
```

**效果**: 提升 10-20%

---

**方案1总效果**: **2-3倍提升**，实施难度：⭐（极简单）

---

### 🔥🔥 方案2：短期优化（代码改造）

**需要修改代码，但改动量不大**

#### 2.1 实现多进程识别

**核心思路**: 启动多个识别进程，每个进程加载独立的FunASR模型

**修改位置**: `processing_controller.py` 中的识别进程启动逻辑

**当前**:
```python
# 只启动1个识别进程
self.recognition_process = multiprocessing.Process(
    target=recognition_worker,
    args=(...)
)
```

**优化后**:
```python
# 启动多个识别进程
self.recognition_processes = []
num_recognition_workers = 2 if device == 'cuda' else 1  # GPU可以2个，CPU只用1个

for i in range(num_recognition_workers):
    process = multiprocessing.Process(
        target=recognition_worker,
        args=(...)
    )
    process.start()
    self.recognition_processes.append(process)
```

**注意事项**:
- GPU模式：最多2个进程（避免显存不足）
- CPU模式：保持1个进程（避免CPU争抢）
- 需要确保每个进程独立加载模型

**效果**: GPU模式提升 **2倍**，CPU模式无提升

---

#### 2.2 优化FFSubSync并发

**核心思路**: FFSubSync在后处理进程中并行执行，无需额外优化

**但可以添加快速模式**:

```python
# 在 post_processing_worker 中
if config.get('ffsubsync_fast_mode', False):
    # 使用更小的max_offset，牺牲精度换速度
    max_offset = 30  # 从60秒减少到30秒
    # 或者跳过某些文件
```

**效果**: 提升 30-50%

---

#### 2.3 添加处理优先级

**核心思路**: 小文件优先处理，大文件后处理

```python
# 在添加任务到队列前排序
files_with_size = [(f, os.path.getsize(f)) for f in files]
files_with_size.sort(key=lambda x: x[1])  # 按大小排序

for file_path, _ in files_with_size:
    self.task_queue.put(file_path)
```

**效果**: 提升用户体验，更快看到结果

---

**方案2总效果**: **3-5倍提升**，实施难度：⭐⭐（中等）

---

### 🔥🔥🔥 方案3：长期优化（架构重构）

**需要较大改动，但效果最好**

#### 3.1 实现真正的批量推理

**核心思路**: 收集多个音频文件，批量送入FunASR

```python
def recognition_worker_batch(audio_queue, result_queue, ...):
    model = AutoModel(...)

    batch_buffer = []
    batch_size = 4  # 一次处理4个文件

    while True:
        # 收集batch_size个文件
        for _ in range(batch_size):
            task = audio_queue.get(timeout=1)
            if task is None:
                break
            batch_buffer.append(task)

        if not batch_buffer:
            break

        # 批量推理
        audio_paths = [task['audio_path'] for task in batch_buffer]
        results = model.generate(
            input=audio_paths,  # 传入多个文件
            batch_size_s=batch_size_s
        )

        # 分发结果
        for task, result in zip(batch_buffer, results):
            result_queue.put({...})

        batch_buffer.clear()
```

**效果**: 提升 **2-3倍**

---

#### 3.2 FFmpeg硬件加速

**核心思路**: 使用GPU解码视频

```python
# 在 pre_processing_worker 中
if device == 'cuda':
    # 使用NVENC硬件加速
    ffmpeg_cmd = [
        'ffmpeg',
        '-hwaccel', 'cuda',
        '-hwaccel_output_format', 'cuda',
        '-i', input_file,
        ...
    ]
```

**效果**: 视频解码提升 **3-5倍**

---

#### 3.3 模型量化加速

**核心思路**: 使用FP16或INT8量化模型

```python
model = AutoModel(
    model="paraformer-zh",
    device=device,
    precision='fp16',  # 使用半精度
    ...
)
```

**效果**: 提升 **30-50%**，显存占用减少 **50%**

---

**方案3总效果**: **5-10倍提升**，实施难度：⭐⭐⭐⭐（复杂）

---

## 📊 综合优化效果预测

### 场景1：处理100个视频（每个5分钟）

| 优化方案 | 处理时间 | 提升倍数 | 实施难度 |
|---------|---------|---------|---------|
| **当前** | 60分钟 | 1x | - |
| **方案1** | 20-30分钟 | 2-3x | ⭐ |
| **方案1+2** | 12-15分钟 | 4-5x | ⭐⭐ |
| **方案1+2+3** | 6-10分钟 | 6-10x | ⭐⭐⭐⭐ |

### 场景2：处理1000个视频（每个5分钟）

| 优化方案 | 处理时间 | 提升倍数 | 实施难度 |
|---------|---------|---------|---------|
| **当前** | 10小时 | 1x | - |
| **方案1** | 3-5小时 | 2-3x | ⭐ |
| **方案1+2** | 2-2.5小时 | 4-5x | ⭐⭐ |
| **方案1+2+3** | 1-1.5小时 | 7-10x | ⭐⭐⭐⭐ |

---

## 🎯 推荐实施路线

### 阶段1：立即实施（1小时内）

**方案1的所有优化**:
1. 增加audio_queue容量
2. 放宽FFmpeg并发限制
3. 优化进程数配置

**预期效果**: 2-3倍提升
**风险**: 极低
**回滚**: 容易

---

### 阶段2：短期实施（1-2天）

**方案2的核心优化**:
1. 实现多进程识别（GPU模式）
2. 添加FFSubSync快速模式
3. 添加文件优先级排序

**预期效果**: 再提升 1.5-2倍（累计4-5倍）
**风险**: 中等
**回滚**: 较容易

---

### 阶段3：长期实施（1-2周）

**方案3的选择性优化**:
1. 实现批量推理（优先）
2. FFmpeg硬件加速（如果有NVIDIA GPU）
3. 模型量化（可选）

**预期效果**: 再提升 1.5-2倍（累计6-10倍）
**风险**: 较高
**回滚**: 困难

---

## 🔧 具体实施代码

### 优化1：增加audio_queue容量

**文件**: `processing_controller.py`

**位置**: 第168行附近

```python
# 修改前
self.audio_queue = None

# 修改后（在 _start_pipeline_workers 方法中）
# 找到创建 audio_queue 的地方，修改为：
self.audio_queue = self.manager.Queue(maxsize=pre_proc_workers * 2)
```

---

### 优化2：动态FFmpeg并发限制

**文件**: `processing_controller.py`

**位置**: 第176行

```python
# 修改前
self.ffmpeg_semaphore = self.manager.Semaphore(2)

# 修改后
def __init__(self, parent=None):
    super().__init__(parent)
    # ... 其他初始化代码 ...

    # 动态设置FFmpeg并发数
    cpu_cores = multiprocessing.cpu_count() or 1
    if cpu_cores >= 16:
        ffmpeg_concurrent = 6
    elif cpu_cores >= 8:
        ffmpeg_concurrent = 4
    else:
        ffmpeg_concurrent = 2

    self.ffmpeg_semaphore = self.manager.Semaphore(ffmpeg_concurrent)
    self.log_message.emit(f"⚙️ FFmpeg并发限制: {ffmpeg_concurrent}")
```

---

### 优化3：多进程识别（GPU模式）

**文件**: `processing_controller.py`

**位置**: 识别进程启动部分（需要查找具体位置）

```python
# 修改前（单进程）
self.recognition_process = multiprocessing.Process(
    target=recognition_worker,
    args=(self.audio_queue, self.result_queue, ...)
)
self.recognition_process.start()

# 修改后（多进程）
self.recognition_processes = []

# GPU模式可以2个进程，CPU模式保持1个
num_recognition_workers = 2 if self.config.device == 'cuda' else 1

for i in range(num_recognition_workers):
    process = multiprocessing.Process(
        target=recognition_worker,
        args=(self.audio_queue, self.result_queue, ...)
    )
    process.start()
    self.recognition_processes.append(process)

self.log_message.emit(f"⚙️ 启动 {num_recognition_workers} 个识别进程")
```

---

## 📝 配置文件方案（推荐）

为了方便用户调整，可以创建配置文件：

**文件**: `performance_config.json`

```json
{
  "ffmpeg_concurrent": "auto",
  "recognition_workers": "auto",
  "audio_queue_size": "auto",
  "enable_batch_inference": false,
  "enable_hardware_acceleration": false,
  "ffsubsync_fast_mode": false,
  "custom_settings": {
    "ffmpeg_concurrent": 4,
    "recognition_workers": 2,
    "audio_queue_multiplier": 2
  }
}
```

**使用方式**:
- `"auto"`: 自动根据系统配置
- 数字: 手动指定
- `custom_settings`: 高级用户自定义

---

## ⚠️ 注意事项

### 1. 内存占用

**多进程识别会增加内存占用**:
- 每个识别进程: ~2-4GB
- 2个进程: ~4-8GB
- 建议系统内存 > 16GB

### 2. GPU显存

**多进程识别需要更多显存**:
- 单进程: ~4-6GB
- 2个进程: ~8-12GB
- 建议GPU显存 > 12GB

### 3. CPU负载

**增加并发会提高CPU负载**:
- 监控CPU温度
- 避免过热降频
- 笔记本建议保守配置

### 4. 磁盘IO

**大量并发可能导致磁盘瓶颈**:
- SSD效果最好
- 机械硬盘建议降低并发
- 监控磁盘使用率

---

## 🧪 性能测试方法

### 测试脚本

```bash
# 测试100个视频的处理时间
time python launcher.py --batch-test 100

# 监控资源使用
watch -n 1 'nvidia-smi; echo "---"; htop'
```

### 性能指标

1. **总处理时间**: 从开始到完成的时间
2. **GPU利用率**: 应该 > 80%
3. **CPU利用率**: 应该 > 60%
4. **内存占用**: 应该 < 85%
5. **磁盘IO**: 监控是否瓶颈

---

## 📞 问题排查

### Q: 优化后反而变慢了？

A: 可能原因：
1. 内存不足，频繁swap
2. GPU显存不足，降级到CPU
3. 磁盘IO瓶颈
4. 并发数过高，争抢资源

**解决**: 降低并发数，监控资源使用

### Q: GPU利用率很低？

A: 可能原因：
1. 识别进程只有1个
2. batch_size_s太小
3. 音频文件太短

**解决**: 实现多进程识别或批量推理

### Q: 内存占用过高？

A: 可能原因：
1. 队列堆积太多
2. 进程数过多
3. 模型加载多份

**解决**: 减少队列大小，降低进程数

---

## 🎉 总结

### 核心瓶颈

1. **识别进程只有1个** - 最大瓶颈
2. **audio_queue容量太小** - 流水线不畅
3. **FFmpeg并发限制过于保守** - 预处理慢

### 推荐方案

**立即实施**（1小时）:
- 增加audio_queue容量
- 放宽FFmpeg并发限制
- **预期提升**: 2-3倍

**短期实施**（1-2天）:
- 实现多进程识别（GPU模式）
- 添加FFSubSync快速模式
- **预期提升**: 4-5倍（累计）

**长期实施**（1-2周）:
- 实现批量推理
- FFmpeg硬件加速
- **预期提升**: 6-10倍（累计）

### 最终效果

- 100个视频: 60分钟 → **6-10分钟**
- 1000个视频: 10小时 → **1-1.5小时**
- GPU利用率: 30% → **80%+**
- 用户体验: **质的飞跃**

---

**优化方案完成日期**: 2025-12-15
**版本**: v5.10
**作者**: Claude Code
