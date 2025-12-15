# -*- mode: python ; coding: utf-8 -*-
"""
FunASR 打包配置 - 修复 PyTorch DLL 加载问题
根据 Win10 Conda 环境打包最佳实践优化
"""
import os
from pathlib import Path

PROJECT_DIR = Path(os.getcwd())

# Conda 环境路径
conda_env = r'd:\Users\Administrator\miniconda3\envs\funasr2-gpu'
torch_lib = os.path.join(conda_env, 'lib', 'site-packages', 'torch', 'lib')
library_bin = os.path.join(conda_env, 'Library', 'bin')
third_party_ffmpeg = PROJECT_DIR / 'third_party' / 'ffmpeg_dlls'
ffmpeg6_dir = third_party_ffmpeg / 'ffmpeg6'
ffmpeg5_dir = third_party_ffmpeg / 'ffmpeg5'

# 关键 PyTorch DLL（必须手动添加）
binaries = [
    # PyTorch 核心 DLL
    (os.path.join(torch_lib, 'shm.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'fbgemm.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'c10.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'torch_cpu.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'torch_cuda.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'c10_cuda.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'torch.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'torch_global_deps.dll'), 'torch\\lib'),

    # CUDA & cuDNN DLL
    (os.path.join(torch_lib, 'cudnn64_8.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'cudnn_cnn_infer64_8.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'cudnn_ops_infer64_8.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'cudnn_adv_infer64_8.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'caffe2_nvrtc.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'nvToolsExt64_1.dll'), 'torch\\lib'),
    (os.path.join(torch_lib, 'cupti64_2023.1.1.dll'), 'torch\\lib'),

    # OpenMP & MKL（Conda NumPy 必需）
    (os.path.join(library_bin, 'libiomp5md.dll'), 'Library\\bin'),
    (os.path.join(library_bin, 'mkl_avx2.2.dll'), 'Library\\bin'),
    (os.path.join(library_bin, 'mkl_core.2.dll'), 'Library\\bin'),
    (os.path.join(library_bin, 'mkl_intel_thread.2.dll'), 'Library\\bin'),
]

# FFmpeg DLL（torchaudio 需要）
ffmpeg6_dlls = [
    'avcodec-60.dll',
    'avdevice-60.dll',
    'avfilter-9.dll',
    'avformat-60.dll',
    'avutil-58.dll',
]
ffmpeg5_dlls = [
    'avcodec-59.dll',
    'avdevice-59.dll',
    'avfilter-8.dll',
    'avformat-59.dll',
    'avutil-57.dll',
    'swscale-6.dll',
    'postproc-56.dll',
    'swresample-4.dll',
]
ffmpeg4_dlls = [
    'avcodec-58.dll',
    'avdevice-58.dll',
    'avfilter-7.dll',
    'avformat-58.dll',
    'avutil-56.dll',
    'avresample-4.dll',
    'swresample-3.dll',
    'swscale-5.dll',
    'postproc-55.dll',
]

for dll_name in ffmpeg6_dlls:
    dll_path = ffmpeg6_dir / dll_name
    binaries.append((str(dll_path), '.'))

for dll_name in ffmpeg5_dlls:
    dll_path = ffmpeg5_dir / dll_name
    binaries.append((str(dll_path), '.'))

for dll_name in ffmpeg4_dlls:
    dll_path = (third_party_ffmpeg / 'ffmpeg4') / dll_name
    binaries.append((str(dll_path), '.'))

# 数据文件
datas = [
    ('config', 'config'),
    ('resources', 'resources'),
    # 添加 ffsubsync 可执行文件
    (os.path.join(conda_env, 'Scripts', 'ffsubsync.exe'), '.'),
    # 添加 funasr 包的数据文件
    (os.path.join(conda_env, 'lib', 'site-packages', 'funasr'), 'funasr'),
]

# 隐藏导入 - 根据专业分析添加
hiddenimports = [
    # 基础
    'pkg_resources.py2_warn',

    # Qt
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',

    # PyTorch 核心
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.optim',
    'torch.cuda',
    'torch.cuda.amp',
    'torch.backends.cudnn',
    'torch.utils',
    'torch.utils.data',
    'torch.utils.data.dataloader',
    'torch.utils.data.dataset',
    'torch.multiprocessing',
    'torch.distributed',
    'torch._C',

    # TorchVision & TorchAudio
    'torchvision',
    'torchvision.models',
    'torchvision.transforms',
    'torchaudio',

    # NumPy（关键！）
    'numpy',
    'numpy.core._multiarray_umath',
    'numpy.core._methods',
    'numpy.core._dtype_ctypes',

    # FunASR
    'funasr',
    'funasr.models',
    'funasr.utils',

    # 多进程
    'multiprocessing',
    'multiprocessing.spawn',
    'multiprocessing.reduction',
    'multiprocessing.queues',

    # 工具
    'psutil',
]

# 排除问题模块（根据专业分析）
excludes = [
    # 'torch.distributions',  # 注释掉 - PyTorch 2.1.2 需要此模块
    'matplotlib',
    'IPython',
    'jupyter',
    'pytest',
    'tkinter',
    'sphinx',
    'PIL',
    'opencv',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt5',
]

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,  # 关键：手动添加 DLL
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    exclude_binaries=False,
    name='FunASR',
    debug=False,  # 设为 True 可看到更多调试信息
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 关闭控制台窗口
    disable_windowed_traceback=False,
)
