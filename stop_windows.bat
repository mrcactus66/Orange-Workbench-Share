@echo off
setlocal
if not defined WORKTABLE_PORT set "WORKTABLE_PORT=8084"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%WORKTABLE_PORT%" ^| findstr LISTENING') do taskkill /PID %%a /F
echo 已停止 %WORKTABLE_PORT% 端口上的工作台。
pause
