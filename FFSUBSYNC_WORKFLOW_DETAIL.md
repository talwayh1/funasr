# FFSubSync 字幕精校详细流程说明

## 📋 目录
1. [流程概述](#流程概述)
2. [详细步骤](#详细步骤)
3. [文件名变化](#文件名变化)
4. [示例说明](#示例说明)
5. [常见问题](#常见问题)

---

## 流程概述

当启用 `ffsubsync_enabled` 选项时，后处理流程如下：

```
┌─────────────────────────────────────────────────────────────┐
│ 第1步：生成原始SRT文件                                      │
│ 文件名: 视频名.srt                                         │
│ 例如: 混动房车.srt                                         │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 第2步：调用 ffsubsync 进行精校                              │
│ 命令: ffsubsync 视频.mp4 -i 视频名.srt -o 视频名_Ffsub.srt │
│ 精校输出: 视频名_Ffsub.srt                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 第3步：删除原始SRT，保留精校后的SRT                         │
│ 删除: 视频名.srt                                           │
│ 保留: 视频名_Ffsub.srt                                     │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ 最终结果：                                                  │
│ 用户只看到精校后的文件: 视频名_Ffsub.srt                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 详细步骤

### **步骤1：生成原始SRT文件（未精校）**

**代码位置**: `pipeline_workers.py` 行560-563

```python
if config.get('generate_srt'):
    srt_path = output_dir / f"{stem}.srt"
    _write_srt_from_result(rec_result, str(srt_path))
    log_queue.put(f"✅ SRT字幕已生成: {srt_path.name}")
```

**操作**:
- 从 `rec_result[0]['sentence_info']` 提取时间戳和文本
- 生成标准SRT格式文件
- 文件名格式: `视频名.srt`

**示例**:
```
输入视频: 混动房车购置税减免10月18日.mp4
生成文件: 混动房车购置税减免10月18日.srt
```

**SRT文件内容示例**:
```srt
1
00:00:00,090 --> 00:00:00,850
这个车子问题，

2
00:00:00,850 --> 00:00:07,350
他说咱们那个呃铝居版是承载式车身跟非承载式车身的那种。

3
00:00:07,770 --> 00:00:08,010
嗯，
```

---

### **步骤2：FFSubSync 精校（如果启用）**

**触发条件**: `pipeline_workers.py` 行641

```python
if config.get('ffsubsync_enabled') and srt_path and srt_path.exists() and srt_path.stat().st_size > 0:
```

**判断条件**:
1. ✅ `ffsubsync_enabled` 配置为 `True`
2. ✅ `srt_path` 存在（即勾选了生成SRT）
3. ✅ SRT文件存在
4. ✅ SRT文件不为空（size > 0）

**执行流程**: 行642-659

```python
# 1. 准备文件名
log_queue.put(f"开始对 '{srt_path.name}' 进行 ffsubsync 字幕精校...")
synced_srt_path = output_dir / f"{stem}_Ffsub.srt"

# 2. 构建命令（使用相对路径）
relative_video_path = p_video_for_sync.name
relative_srt_path = srt_path.name
relative_synced_path = synced_srt_path.name

sync_cmd = [
    'ffsubsync',
    str(relative_video_path),  # 视频.mp4
    '-i', str(relative_srt_path),  # 原始.srt
    '-o', str(relative_synced_path)  # 精校后_Ffsub.srt
]

# 3. 执行精校（在视频所在目录）
result = run_silent(sync_cmd, cwd=output_dir)

# 4. 检查结果
if synced_srt_path.exists() and synced_srt_path.stat().st_size > 0:
    # 成功：删除原始SRT
    try:
        srt_path.unlink()
        log_queue.put(f"✅ ffsubsync 精校成功！输出文件: {synced_srt_path.name}")
    except OSError as e:
        log_queue.put(f"警告: ffsubsync 成功，但删除原始SRT失败: {e}")
else:
    # 失败：保留原始SRT
    error_details = result.stderr.strip() if result.stderr else "未知错误"
    log_queue.put(f"警告: ffsubsync 执行失败。保留原始字幕。错误: {error_details}")
```

**FFSubSync 命令示例**:
```bash
ffsubsync 混动房车购置税减免10月18日.mp4 \
         -i 混动房车购置税减免10月18日.srt \
         -o 混动房车购置税减免10月18日_Ffsub.srt
```

**FFSubSync 工作原理**:
1. 从视频文件中提取音频
2. 分析视频实际音频的语音时间轴
3. 对比原始SRT的时间戳
4. 自动调整时间戳，使字幕与实际音频完美同步
5. 输出精校后的SRT文件

---

### **步骤3：删除原始SRT（成功时）**

**代码位置**: 行652-656

```python
if synced_srt_path.exists() and synced_srt_path.stat().st_size > 0:
    try:
        srt_path.unlink()  # 删除原始 "视频名.srt"
        log_queue.put(f"✅ ffsubsync 精校成功！输出文件: {synced_srt_path.name}")
    except OSError as e:
        log_queue.put(f"警告: ffsubsync 成功，但删除原始SRT失败: {e}")
```

**删除逻辑**:
- 只有精校成功（精校文件存在且不为空）才删除原始SRT
- 如果删除失败（文件被占用），会记录警告但不影响处理
- 最终用户只看到精校后的 `_Ffsub.srt` 文件

---

## 文件名变化

### **场景1：启用 FFSubSync（成功）**

```
处理前：
├── 混动房车购置税减免10月18日.mp4  (原始视频)

处理中：
├── 混动房车购置税减免10月18日.mp4
├── 混动房车购置税减免10月18日_extracted.wav  (临时音频)
├── 混动房车购置税减免10月18日.srt  (原始SRT，临时)

FFSubSync精校后：
├── 混动房车购置税减免10月18日.mp4
├── 混动房车购置税减免10月18日_Ffsub.srt  (精校后SRT)
└── [删除] 混动房车购置税减免10月18日.srt  (原始SRT被删除)

最终用户看到：
├── 混动房车购置税减免10月18日.mp4
├── 混动房车购置税减免10月18日_Ffsub.srt  ✅ 精校后的字幕
├── 混动房车购置税减免10月18日.txt
├── 混动房车购置税减免10月18日.json
└── ...其他格式
```

**关键变化**:
- ❌ **删除**: `视频名.srt`（原始识别生成的SRT）
- ✅ **保留**: `视频名_Ffsub.srt`（精校后的SRT）

---

### **场景2：启用 FFSubSync（失败）**

```
处理前：
├── 混动房车购置税减免10月18日.mp4

FFSubSync失败后：
├── 混动房车购置税减免10月18日.mp4
├── 混动房车购置税减免10月18日.srt  ✅ 保留原始SRT
└── [不存在] 混动房车购置税减免10月18日_Ffsub.srt  (精校失败)

最终用户看到：
├── 混动房车购置税减免10月18日.mp4
├── 混动房车购置税减免10月18日.srt  ⚠️ 原始字幕（未精校）
├── 混动房车购置税减免10月18日.txt
└── ...其他格式
```

**关键变化**:
- ✅ **保留**: `视频名.srt`（原始SRT，因为精校失败）
- ❌ **不生成**: `视频名_Ffsub.srt`

---

### **场景3：未启用 FFSubSync**

```
处理前：
├── 混动房车购置税减免10月18日.mp4

处理后：
├── 混动房车购置税减免10月18日.mp4
├── 混动房车购置税减免10月18日.srt  ✅ 原始SRT
├── 混动房车购置税减免10月18日.txt
└── ...其他格式
```

**关键变化**:
- ✅ **保留**: `视频名.srt`（原始SRT）
- ❌ **不生成**: `视频名_Ffsub.srt`（未启用精校）

---

## 示例说明

### **完整示例1：启用FFSubSync + 生成SRT**

**配置**:
```python
config = {
    'generate_srt': True,
    'ffsubsync_enabled': True
}
```

**处理流程**:
```
1. 生成原始SRT
   → 创建: 硬派越野.srt

2. 调用FFSubSync精校
   → 命令: ffsubsync 硬派越野.mp4 -i 硬派越野.srt -o 硬派越野_Ffsub.srt
   → 创建: 硬派越野_Ffsub.srt

3. 精校成功，删除原始
   → 删除: 硬派越野.srt

最终文件:
   ✅ 硬派越野_Ffsub.srt  (精校后的字幕)
```

**日志输出**:
```
[后处理] 开始为视频 '硬派越野.mp4' 生成文件...
   - ✅ SRT字幕已生成: 硬派越野.srt
   - 开始对 '硬派越野.srt' 进行 ffsubsync 字幕精校...
   - ✅ ffsubsync 精校成功！输出文件: 硬派越野_Ffsub.srt
✅ 处理成功: 硬派越野.mp4
```

---

### **完整示例2：启用FFSubSync + 生成SRT和SRT.MD**

**配置**:
```python
config = {
    'generate_srt': True,
    'generate_srt_md': True,
    'ffsubsync_enabled': True
}
```

**处理流程**:
```
1. 生成原始SRT
   → 创建: 硬派越野.srt

2. 生成SRT.MD
   → 创建: 硬派越野.srt.md

3. 调用FFSubSync精校（只对.srt精校，不对.srt.md精校）
   → 命令: ffsubsync 硬派越野.mp4 -i 硬派越野.srt -o 硬派越野_Ffsub.srt
   → 创建: 硬派越野_Ffsub.srt

4. 精校成功，删除原始.srt（保留.srt.md）
   → 删除: 硬派越野.srt

最终文件:
   ✅ 硬派越野_Ffsub.srt  (精校后的SRT)
   ✅ 硬派越野.srt.md     (原始时间戳的SRT.MD)
```

**注意**:
- `.srt.md` 文件**不会被精校**，保持原始识别的时间戳
- 只有 `.srt` 文件会被精校为 `_Ffsub.srt`

---

### **完整示例3：FFSubSync失败**

**处理流程**:
```
1. 生成原始SRT
   → 创建: 硬派越野.srt

2. 调用FFSubSync精校
   → 命令: ffsubsync 硬派越野.mp4 -i 硬派越野.srt -o 硬派越野_Ffsub.srt
   → 错误: ffsubsync命令失败

3. 精校失败，保留原始SRT
   → 保留: 硬派越野.srt

最终文件:
   ✅ 硬派越野.srt  (原始字幕，未精校)
```

**日志输出**:
```
[后处理] 开始为视频 '硬派越野.mp4' 生成文件...
   - ✅ SRT字幕已生成: 硬派越野.srt
   - 开始对 '硬派越野.srt' 进行 ffsubsync 字幕精校...
   - 警告: ffsubsync 执行失败或未生成有效文件。保留原始字幕。错误详情: [错误信息]
✅ 处理成功: 硬派越野.mp4
```

---

## 常见问题

### **Q1: 为什么最终文件名是 `_Ffsub.srt` 而不是 `.srt`？**

**A**: 这是有意设计的，原因：

1. **清晰标识**: `_Ffsub.srt` 后缀让用户清楚知道这是经过精校的版本
2. **版本区分**: 如果精校失败，用户会得到 `.srt`，一眼就能看出区别
3. **兼容性**: 所有视频播放器都能识别 `_Ffsub.srt` 文件

**原始设计理念**:
```
视频名.srt         → 原始识别（可能有偏差）
视频名_Ffsub.srt   → 精校后（与音频完美同步）✅
```

---

### **Q2: 如果不想要 `_Ffsub` 后缀怎么办？**

**A**: 可以修改代码，将精校后的文件直接覆盖原始文件：

**修改 `pipeline_workers.py` 行643**:

```python
# 原始代码（生成 _Ffsub.srt）
synced_srt_path = output_dir / f"{stem}_Ffsub.srt"

# 修改为（直接覆盖原始 .srt）
synced_srt_path = output_dir / f"{stem}.srt"
```

然后删除行653的 `srt_path.unlink()`（因为输出文件名相同，会自动覆盖）。

**修改后效果**:
```
最终文件: 视频名.srt  (精校后，覆盖了原始)
```

---

### **Q3: FFSubSync精校需要多长时间？**

**A**: 取决于视频长度和硬件性能：

- **5分钟视频**: 约10-30秒
- **30分钟视频**: 约1-3分钟
- **1小时视频**: 约3-10分钟

**影响因素**:
- 视频音频质量
- CPU性能（ffsubsync主要使用CPU）
- 磁盘IO速度

---

### **Q4: FFSubSync精校可能失败的原因？**

**常见原因**:

1. **ffsubsync未安装**
   ```bash
   # 安装命令
   pip install ffsubsync
   ```

2. **视频无音频**
   - FFSubSync需要从视频中提取音频
   - 如果视频是纯视频（无音轨），精校会失败

3. **音频质量太差**
   - 背景噪音过大
   - 语音不清晰
   - 音量过低

4. **权限问题**
   - 无法读取视频文件
   - 无法写入输出目录

5. **路径问题**
   - 文件路径包含特殊字符
   - 路径过长

---

### **Q5: 如何判断精校是否成功？**

**A**: 查看日志和文件：

**成功标志**:
```
✅ ffsubsync 精校成功！输出文件: 视频名_Ffsub.srt
```

**失败标志**:
```
⚠️ 警告: ffsubsync 执行失败或未生成有效文件。保留原始字幕。
```

**文件检查**:
- 成功：存在 `视频名_Ffsub.srt`，不存在 `视频名.srt`
- 失败：存在 `视频名.srt`，不存在 `视频名_Ffsub.srt`

---

### **Q6: 精校后的字幕与原始字幕有什么区别？**

**A**: 时间戳精度不同：

**原始SRT（FunASR直接输出）**:
```srt
1
00:00:00,090 --> 00:00:00,850
这个车子问题，
```
- 基于VAD（语音活动检测）的时间戳
- 可能与实际音频有微小偏差（±0.5秒）

**精校SRT（FFSubSync处理后）**:
```srt
1
00:00:00,120 --> 00:00:00,880
这个车子问题，
```
- 基于实际音频波形对齐
- 与实际音频完美同步（误差 < 0.1秒）

**视觉效果**:
- 原始：字幕可能稍微提前或延后
- 精校：字幕与说话完美同步 ✅

---

### **Q7: 是否可以批量精校？**

**A**: 可以，系统会自动处理批量文件：

**批量处理流程**:
```
文件1.mp4 → 文件1.srt → ffsubsync → 文件1_Ffsub.srt
文件2.mp4 → 文件2.srt → ffsubsync → 文件2_Ffsub.srt
文件3.mp4 → 文件3.srt → ffsubsync → 文件3_Ffsub.srt
```

每个视频的精校是独立的，一个失败不影响其他。

---

## 总结

### **FFSubSync流程总结**

```
┌────────────────────────────┐
│ 1. FunASR识别              │
│    → 生成 sentence_info    │
│    → 时间戳来自VAD         │
└────────────────────────────┘
              ↓
┌────────────────────────────┐
│ 2. 生成原始SRT             │
│    → 视频名.srt            │
│    → 基于VAD时间戳         │
└────────────────────────────┘
              ↓
┌────────────────────────────┐
│ 3. FFSubSync精校（可选）   │
│    → 分析实际音频波形      │
│    → 自动调整时间戳        │
│    → 生成 _Ffsub.srt       │
└────────────────────────────┘
              ↓
┌────────────────────────────┐
│ 4. 清理原始文件            │
│    → 删除 视频名.srt       │
│    → 保留 视频名_Ffsub.srt │
└────────────────────────────┘
```

### **文件名规则**

| 场景 | 最终SRT文件名 | 说明 |
|------|--------------|------|
| **未启用FFSubSync** | `视频名.srt` | 原始识别结果 |
| **FFSubSync成功** | `视频名_Ffsub.srt` | 精校后，原始被删除 |
| **FFSubSync失败** | `视频名.srt` | 保留原始，精校失败 |

### **关键代码位置**

| 功能 | 文件 | 行号 |
|------|------|------|
| 生成原始SRT | `pipeline_workers.py` | 560-563 |
| FFSubSync判断 | `pipeline_workers.py` | 641 |
| FFSubSync执行 | `pipeline_workers.py` | 642-659 |
| 删除原始SRT | `pipeline_workers.py` | 653 |

---

**文档生成时间**: 2025-10-19 22:35
**适用版本**: v5.9.3
