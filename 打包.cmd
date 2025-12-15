@echo off
chcp 65001 >nul
cls
echo.
echo ╔═══════════════════════════════════════════════╗
echo ║  FunASR 打包 - CPU+GPU 自适应版本             ║
echo ╚═══════════════════════════════════════════════╝
echo.
echo 特点:
echo  • 自动检测 GPU 可用性（智能适配）
echo  • 有 GPU 时自动使用 GPU 加速
echo  • 无 GPU 时自动降级到 CPU
echo  • 单一可执行文件，全场景适配
echo  • 详细启动日志：funasr_startup.log
echo.

REM 检查环境
if "%CONDA_DEFAULT_ENV%"=="" (
    echo 正在激活 conda 环境...
    call conda activate funasr2-gpu
    if errorlevel 1 (
        echo ❌ 无法激活环境 funasr2-gpu
        echo.
        echo 请手动激活环境后再运行
        pause
        exit /b 1
    )
)

echo ✅ 当前环境: %CONDA_DEFAULT_ENV%
echo.

REM 验证 PyTorch 版本
echo 验证环境配置...
python -c "import torch; v=torch.__version__; cuda=torch.cuda.is_available(); print(f'  PyTorch: {v}'); print(f'  CUDA 支持: {cuda}'); exit(0 if cuda else 1)"
if errorlevel 1 (
    echo.
    echo ❌ 警告：当前环境的 PyTorch 不支持 CUDA！
    echo    这将导致打包后的程序无法使用 GPU。
    echo.
    echo 建议：
    echo    1. 确保已激活 funasr2-gpu 环境
    echo    2. 或运行 修复GPU支持.cmd 安装 CUDA 版本的 PyTorch
    echo.
    pause
)
echo.

echo 清理旧文件...
if exist "dist\FunASR" rmdir /s /q "dist\FunASR"
if exist "build" rmdir /s /q build

echo.
echo 开始打包...
echo.

pyinstaller --clean funasr.spec

if errorlevel 1 (
    echo.
    echo ❌ 打包失败！
    echo.
    echo 请检查错误信息
    pause
    exit /b 1
)

echo.
echo ╔═══════════════════════════════════════════════╗
echo ║              ✅ 打包完成！                     ║
echo ╚═══════════════════════════════════════════════╝
echo.

if exist "dist\FunASR\FunASR.exe" (
    echo 📁 输出目录: dist\FunASR\
    echo 🚀 可执行文件: FunASR.exe
    echo.
    echo ⚡ 智能特性:
    echo   • 自动检测 CUDA GPU
    echo   • 有 GPU: 自动启用 GPU 加速
    echo   • 无 GPU: 自动使用 CPU 模式
    echo   • 查看日志了解运行模式
    echo.
    echo 立即测试:
    echo   cd dist\FunASR
    echo   FunASR.exe
    echo.
    echo 💡 启动后查看 funasr_error.log 了解使用的运行模式
    echo.
) else (
    echo ❌ 未找到可执行文件
    echo.
)

pause
