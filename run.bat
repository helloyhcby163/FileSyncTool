@echo off
chcp 65001 >nul
echo 正在启动文件同步工具...
echo.

REM 检查虚拟环境是否存在
if not exist ".venv" (
    echo 错误：虚拟环境不存在，请先创建虚拟环境
    pause
    exit /b 1
)

REM 使用虚拟环境中的 Python 运行程序
".venv\Scripts\python.exe" "main.py"

if errorlevel 1 (
    echo.
    echo 程序运行出错，请检查错误信息
    pause
)
