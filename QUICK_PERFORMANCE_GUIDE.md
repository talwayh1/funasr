# 批量处理性能优化 - 快速指南

## ✅ 实施状态（2025-12-15）

**所有优化已完成并集成到代码中！**

- ✅ 方案1（配置优化）：已完成
- ✅ 方案2（架构优化）：已完成
- ✅ 性能配置文件：已创建
- ✅ 测试验证：全部通过

**使用方法**：直接启动应用即可，所有优化自动生效！

---

## 🎯 核心问题

**当前瓶颈**:
1. ⚠️ 识别进程只有1个（最大瓶颈）
2. ⚠️ audio_queue容量太小（4个）
3. ⚠️ FFmpeg并发限制过于保守（2个）

**影响**: 处理1000个视频需要10小时

---

## 🚀 快速优化（3步搞定）

### 方案1：立即可用（2-3倍提升）⭐

**实施时间**: 5分钟
**难度**: ⭐（极简单）
**效果**: 10小时 → 3-5小时

#### 自动优化（推荐）

```bash
cd /opt/funasrui
python3 apply_performance_boost.py
```

#### 手动优化

编辑 `processing_controller.py`:

1. **第168行附近** - 增加audio_queue容量:
```python
# 修改前
self.audio_queue = self.manager.Queue(maxsize=4)

# 修改后
self.audio_queue = self.manager.Queue(maxsize=pre_proc_workers * 2)
```

2. **第176行** - 放宽FFmpeg并发:
```python
# 修改前
self.ffmpeg_semaphore = self.manager.Semaphore(2)

# 修改后（16核心系统）
self.ffmpeg_semaphore = self.manager.Semaphore(6)

# 修改后（8核心系统）
self.ffmpeg_semaphore = self.manager.Semaphore(4)
```

3. **第581-592行** - 增加进程数:
```python
# 高性能系统
pre_proc_workers = min(16, physical_cores)  # 从12改为16
post_proc_workers = min(20, cpu_cores)      # 从16改为20

# 中端系统
pre_proc_workers = min(10, physical_cores)  # 从8改为10
post_proc_workers = min(12, cpu_cores)      # 从10改为12
```

---

### 方案2：短期优化（4-5倍提升）⭐⭐

**实施时间**: 1-2天
**难度**: ⭐⭐（中等）
**效果**: 10小时 → 2-2.5小时

**核心**: 实现多进程识别（GPU模式）

详见 `BATCH_PROCESSING_OPTIMIZATION.md` 第2.1节

---

### 方案3：长期优化（6-10倍提升）⭐⭐⭐⭐

**实施时间**: 1-2周
**难度**: ⭐⭐⭐⭐（复杂）
**效果**: 10小时 → 1-1.5小时

**核心**: 批量推理 + 硬件加速

详见 `BATCH_PROCESSING_OPTIMIZATION.md` 第3节

---

## 📊 性能对比

| 方案 | 100个视频 | 1000个视频 | 实施难度 |
|------|----------|-----------|---------|
| **当前** | 60分钟 | 10小时 | - |
| **方案1** | 20-30分钟 | 3-5小时 | ⭐ |
| **方案1+2** | 12-15分钟 | 2-2.5小时 | ⭐⭐ |
| **方案1+2+3** | 6-10分钟 | 1-1.5小时 | ⭐⭐⭐⭐ |

---

## 🔧 测试方法

### 1. 应用优化

```bash
# 自动优化
python3 apply_performance_boost.py

# 或手动编辑 processing_controller.py
```

### 2. 重启应用

```bash
conda activate funasr2-gpu
python launcher.py
```

### 3. 测试批量处理

- 选择包含100+个视频的文件夹
- 观察日志输出
- 记录处理时间

### 4. 监控资源

```bash
# 监控GPU
watch -n 1 nvidia-smi

# 监控CPU和内存
htop
```

---

## ⚠️ 注意事项

### 内存要求

- **方案1**: 无额外要求
- **方案2**: 建议 > 16GB
- **方案3**: 建议 > 32GB

### GPU显存要求

- **方案1**: 无额外要求
- **方案2**: 建议 > 12GB
- **方案3**: 建议 > 16GB

### 恢复方法

```bash
# 如果优化后出现问题
cp processing_controller.py.backup_perf processing_controller.py
```

---

## 📞 常见问题

### Q: 优化后反而变慢？

**可能原因**:
- 内存不足（检查 `free -h`）
- GPU显存不足（检查 `nvidia-smi`）
- 磁盘IO瓶颈（使用SSD）

**解决**: 降低并发数

### Q: GPU利用率很低？

**原因**: 识别进程只有1个

**解决**: 实施方案2（多进程识别）

### Q: 如何知道哪个阶段最慢？

**方法**: 查看日志输出
- 预处理慢：增加FFmpeg并发
- 识别慢：实施方案2
- 后处理慢：增加后处理进程数

---

## 🎉 推荐路线

### 新手用户

1. ✅ 运行自动优化脚本
2. ✅ 测试效果
3. ✅ 如果满意，停止

### 进阶用户

1. ✅ 实施方案1
2. ✅ 测试效果
3. ✅ 实施方案2
4. ✅ 测试效果

### 专业用户

1. ✅ 实施方案1+2
2. ✅ 根据需求实施方案3的部分功能
3. ✅ 持续监控和调优

---

## 📚 详细文档

- **完整优化方案**: `BATCH_PROCESSING_OPTIMIZATION.md`
- **自动优化脚本**: `apply_performance_boost.py`
- **界面卡顿优化**: `PERFORMANCE_OPTIMIZATION.md`

---

**快速指南版本**: v1.0
**更新日期**: 2025-12-15
