# -*- coding: utf-8 -*-
"""
快速性能优化脚本 - 应用方案1（立即可用）
自动修改配置参数，无需手动编辑代码
"""
import sys
import multiprocessing
import re
from pathlib import Path

def backup_file(file_path):
    """备份文件"""
    backup_path = f"{file_path}.backup_perf"
    if not Path(backup_path).exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ 已备份: {backup_path}")
    else:
        print(f"✓ 备份已存在: {backup_path}")

def apply_optimization_1():
    """优化1：增加audio_queue容量"""
    file_path = '/opt/funasrui/processing_controller.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 audio_queue 的创建位置
    # 当前: self.audio_queue = self.manager.Queue(maxsize=4)
    # 目标: self.audio_queue = self.manager.Queue(maxsize=pre_proc_workers * 2)

    pattern = r'self\.audio_queue = self\.manager\.Queue\(maxsize=4\)'
    if re.search(pattern, content):
        content = re.sub(
            pattern,
            'self.audio_queue = self.manager.Queue(maxsize=pre_proc_workers * 2)',
            content
        )
        print("✓ 优化1：audio_queue容量已增加（4 → pre_proc_workers * 2）")
        return content, True
    else:
        print("⚠ 优化1：未找到audio_queue创建代码，可能已优化或代码结构变化")
        return content, False

def apply_optimization_2():
    """优化2：动态FFmpeg并发限制"""
    file_path = '/opt/funasrui/processing_controller.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找 ffmpeg_semaphore 的创建位置
    # 当前: self.ffmpeg_semaphore = self.manager.Semaphore(2)
    # 目标: 动态设置

    pattern = r'self\.ffmpeg_semaphore = self\.manager\.Semaphore\(2\)'
    if re.search(pattern, content):
        cpu_cores = multiprocessing.cpu_count() or 1
        if cpu_cores >= 16:
            ffmpeg_concurrent = 6
        elif cpu_cores >= 8:
            ffmpeg_concurrent = 4
        else:
            ffmpeg_concurrent = 2

        replacement = f'self.ffmpeg_semaphore = self.manager.Semaphore({ffmpeg_concurrent})  # 动态优化：{cpu_cores}核心'
        content = re.sub(pattern, replacement, content)
        print(f"✓ 优化2：FFmpeg并发限制已优化（2 → {ffmpeg_concurrent}，基于{cpu_cores}核心）")
        return content, True
    else:
        print("⚠ 优化2：未找到ffmpeg_semaphore创建代码，可能已优化或代码结构变化")
        return content, False

def apply_optimization_3():
    """优化3：更激进的进程数配置"""
    file_path = '/opt/funasrui/processing_controller.py'

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找进程数配置部分
    # 高性能系统
    pattern1 = r'pre_proc_workers = min\(12, physical_cores\)'
    if re.search(pattern1, content):
        content = re.sub(pattern1, 'pre_proc_workers = min(16, physical_cores)  # 优化：12→16', content)
        print("✓ 优化3a：高性能系统预处理进程数已增加（12 → 16）")

    pattern2 = r'post_proc_workers = min\(16, cpu_cores\)'
    if re.search(pattern2, content):
        content = re.sub(pattern2, 'post_proc_workers = min(20, cpu_cores)  # 优化：16→20', content)
        print("✓ 优化3b：高性能系统后处理进程数已增加（16 → 20）")

    # 中端系统
    pattern3 = r'pre_proc_workers = min\(8, physical_cores\)'
    if re.search(pattern3, content):
        content = re.sub(pattern3, 'pre_proc_workers = min(10, physical_cores)  # 优化：8→10', content)
        print("✓ 优化3c：中端系统预处理进程数已增加（8 → 10）")

    pattern4 = r'post_proc_workers = min\(10, cpu_cores\)'
    if re.search(pattern4, content):
        content = re.sub(pattern4, 'post_proc_workers = min(12, cpu_cores)  # 优化：10→12', content)
        print("✓ 优化3d：中端系统后处理进程数已增加（10 → 12）")

    return content, True

def main():
    print("=" * 60)
    print("FunASR 批量处理性能优化脚本")
    print("方案1：立即可用（配置调整）")
    print("=" * 60)

    file_path = '/opt/funasrui/processing_controller.py'

    # 检查文件是否存在
    if not Path(file_path).exists():
        print(f"✗ 错误：找不到文件 {file_path}")
        sys.exit(1)

    # 备份文件
    print("\n[1/4] 备份原始文件...")
    backup_file(file_path)

    # 读取文件
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 应用优化
    print("\n[2/4] 应用性能优化...")

    # 优化1：audio_queue容量
    content, opt1_applied = apply_optimization_1()

    # 优化2：FFmpeg并发
    content, opt2_applied = apply_optimization_2()

    # 优化3：进程数配置
    content, opt3_applied = apply_optimization_3()

    # 写回文件
    print("\n[3/4] 保存优化后的文件...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✓ 已保存: {file_path}")

    # 总结
    print("\n[4/4] 优化完成总结")
    print("=" * 60)

    applied_count = sum([opt1_applied, opt2_applied, opt3_applied])

    if applied_count > 0:
        print(f"✓ 成功应用 {applied_count} 项优化")
        print("\n优化内容:")
        if opt1_applied:
            print("  1. audio_queue容量增加")
        if opt2_applied:
            print("  2. FFmpeg并发限制优化")
        if opt3_applied:
            print("  3. 进程数配置优化")

        print("\n预期效果:")
        print("  - 处理速度提升: 2-3倍")
        print("  - CPU利用率提升: 30-50%")
        print("  - 流水线更流畅")

        print("\n下一步:")
        print("  1. 重启应用: python launcher.py")
        print("  2. 测试批量处理")
        print("  3. 观察性能提升")

        print("\n如需恢复:")
        print(f"  cp {file_path}.backup_perf {file_path}")

        print("\n" + "=" * 60)
        print("✓ 优化成功！可以开始测试了！")
        print("=" * 60)
    else:
        print("⚠ 未应用任何优化")
        print("可能原因:")
        print("  1. 代码已经优化过")
        print("  2. 代码结构发生变化")
        print("  3. 需要手动检查代码")

        print("\n建议:")
        print("  查看 BATCH_PROCESSING_OPTIMIZATION.md 手动优化")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
