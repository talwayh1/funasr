# Silero VAD 模型下载地址

## 官方GitHub仓库
https://github.com/snakers4/silero-vad

## 直接下载模型文件

### 方法1：直接下载JIT模型（推荐）
```
模型URL:
https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.jit

文件大小: ~1.5MB
格式: PyTorch JIT
```

### 方法2：下载ONNX模型
```
模型URL:
https://github.com/snakers4/silero-vad/raw/master/files/silero_vad.onnx

文件大小: ~1.8MB
格式: ONNX
```

## 模型保存位置

下载后，模型应该放在PyTorch Hub缓存目录：

### Windows系统
```
默认位置: 
C:\Users\<用户名>\.cache\torch\hub\snakers4_silero-vad_master\

或者:
%USERPROFILE%\.cache\torch\hub\snakers4_silero-vad_master\
```

### 完整目录结构
```
.cache\torch\hub\
└── snakers4_silero-vad_master\
    ├── files\
    │   ├── silero_vad.jit
    │   └── silero_vad.onnx
    ├── utils.py
    ├── utils_vad.py
    └── hubconf.py
```

## 使用conda环境下载（推荐）

```bash
# 激活你的conda环境
conda activate funasr2-gpu

# 使用Python下载
python -c "import torch; model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True); print('下载成功')"
```

## 手动安装步骤

### 步骤1: 下载完整仓库
```bash
# 克隆仓库
git clone https://github.com/snakers4/silero-vad.git

# 或者下载ZIP
# https://github.com/snakers4/silero-vad/archive/refs/heads/master.zip
```

### 步骤2: 手动复制到缓存目录
```bash
# Windows PowerShell
$targetDir = "$env:USERPROFILE\.cache\torch\hub\snakers4_silero-vad_master"
mkdir -p $targetDir
cp -r silero-vad/* $targetDir/
```

## 测试模型是否可用

```python
import torch

# 加载模型
model, utils = torch.hub.load(
    repo_or_dir='snakers4/silero-vad',
    model='silero_vad',
    force_reload=False
)

print("✅ Silero VAD 模型加载成功！")
```

## ffsubsync 如何使用这个模型

ffsubsync内部会自动调用：
```python
# ffsubsync内部实现
import torch
model, utils = torch.hub.load('snakers4/silero-vad', 'silero_vad')
```

所以只要PyTorch Hub缓存中有模型文件，ffsubsync就能使用。

## 国内加速镜像（如果GitHub访问慢）

### 使用Gitee镜像
```
https://gitee.com/mirrors/silero-vad
```

### 使用代理下载
```bash
# 设置代理（如果有）
set HTTP_PROXY=http://127.0.0.1:7890
set HTTPS_PROXY=http://127.0.0.1:7890

# 然后运行下载命令
python -c "import torch; ..."
```

## 离线安装包（如果完全无法联网）

可以在有网络的机器上：
1. 下载整个仓库: https://github.com/snakers4/silero-vad/archive/refs/heads/master.zip
2. 复制到目标机器的: %USERPROFILE%\.cache\torch\hub\snakers4_silero-vad_master\
3. 重命名文件夹去掉 "-master" 后缀（如果需要）

