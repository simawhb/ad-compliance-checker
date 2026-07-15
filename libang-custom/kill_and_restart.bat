@echo off
chcp 65001 >nul
echo 正在杀掉所有 Python 进程...
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 >nul
echo.
echo 启动力邦定制版...
cd /d D:\驷马仓库\ad-compliance-checker\libang-custom
C:\Users\whb\.codex\api2codex\venv\Scripts\python.exe start_server.py
pause
