@echo off
chcp 65001 >nul
title 驷马合规 · 电商页面广告审查系统

echo ════════════════════════════════════════════
echo  驷马合规 · 电商页面广告审查系统
echo  版本: v1.0 | 日期: 2026-06-25
echo ════════════════════════════════════════════
echo.

REM ── 设置 Python 环境 ──
set PYTHON_PATH=C:\Users\14712\.workbuddy\binaries\python\envs\default\Scripts\python.exe
set BASE_DIR=%~dp0..
set BACKEND_DIR=%BASE_DIR%\backend

REM ── 检查 Python ──
if not exist "%PYTHON_PATH%" (
    echo [ERROR] 未找到 Python 解释器: %PYTHON_PATH%
    echo 请修改 scripts\start.bat 中的 PYTHON_PATH 为实际路径
    pause
    exit /b 1
)

echo [1/3] 检查依赖...
cd /d "%BASE_DIR%"

REM ── 检查关键依赖 ──
%PYTHON_PATH% -c "import fastapi" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] 首次运行，安装依赖...
    pip install -r requirements.txt -i https://mirror.baidu.com/pypi/simple
)

REM ── 检查 Playwright 浏览器 ──
%PYTHON_PATH% -c "from playwright.sync_api import sync_playwright" 2>nul || (
    echo [INFO] 安装 Playwright Chromium...
    playwright install chromium
)

echo [2/3] 启动 OCR 引擎（PaddleOCR + GPU）...
%PYTHON_PATH% -c "
import sys
sys.path.insert(0, '%BACKEND_DIR%')
from ocr_engine import get_ocr_engine
engine = get_ocr_engine()
print('[OK] OCR 引擎就绪')
"

echo [3/3] 启动 Web 服务...
cd /d "%BACKEND_DIR%"
%PYTHON_PATH% -m uvicorn main:app ^
    --host 127.0.0.1 ^
    --port 8000 ^
    --reload ^
    --log-level info

if %errorlevel% neq 0 (
    echo [ERROR] 服务启动失败！
    pause
)
