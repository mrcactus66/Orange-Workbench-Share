@echo off
setlocal
cd /d "%~dp0"
if not defined WORKTABLE_PORT set "WORKTABLE_PORT=8084"

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] 正在创建独立 Python 环境...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 (
    echo.
    echo 未找到 Python 3，请先从 https://www.python.org/downloads/ 安装。
    pause
    exit /b 1
  )
)

echo [2/3] 正在检查运行依赖...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo 依赖安装失败，请检查网络后重试。
  pause
  exit /b 1
)

echo [3/3] 工作台地址：http://127.0.0.1:%WORKTABLE_PORT%
echo 保持此窗口打开；按 Ctrl+C 停止工作台。
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 1; Start-Process 'http://127.0.0.1:%WORKTABLE_PORT%'"
".venv\Scripts\python.exe" web_app.py
