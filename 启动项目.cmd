@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set "PROJECT_TEMP=%CD%\.local-temp"
if not exist "%PROJECT_TEMP%" mkdir "%PROJECT_TEMP%" >nul 2>nul
set "TEMP=%PROJECT_TEMP%"
set "TMP=%PROJECT_TEMP%"

if not exist ".venv\Scripts\python.exe" (
    echo [FAIL] 未找到 .venv\Scripts\python.exe
    echo 请先在项目根目录执行：
    echo python -m venv .venv
    echo ^& ".venv/Scripts/python.exe" -m pip install pytest
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "scripts\launcher.py"
set EXIT_CODE=%ERRORLEVEL%

echo.
if not "%EXIT_CODE%"=="0" (
    echo 启动器退出码：%EXIT_CODE%
)
pause
exit /b %EXIT_CODE%
