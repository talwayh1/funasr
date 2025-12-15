@echo off
REM 激活conda环境并启动FunASR主程序
call conda activate funasr2-gpu
python main.py
pause 