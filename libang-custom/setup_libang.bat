@echo off
title Sima Compliance - Libang Setup
cd /d "D:\驷马仓库\ad-compliance-checker"

echo ============================================
echo  Step 1/4: Create directories and extract
echo ============================================

if not exist "libang-custom" mkdir libang-custom
if not exist "libang-custom\configs" mkdir libang-custom\configs

set UPLOAD_DIR=%LOCALAPPDATA%\Claude-3p\local-agent-mode-sessions\c187ed0d\00000000\local_9c1dcd36-19d6-4134-8bd9-e9b74c154464\uploads

echo  Upload dir: %UPLOAD_DIR%
echo.

tar -xf "%UPLOAD_DIR%\afd1fad5-2b65-4780-a07b-e3ec85d3a2a8-1782881391747_ad-compliance-checker.tar.gz" -C libang-custom
if %ERRORLEVEL% NEQ 0 (
    echo [FAILED] Extract project code - file may not exist at the expected path
    echo  Try: manually extract the .tar.gz files into libang-custom\ using 7-Zip
    pause
    exit /b 1
)
echo  [OK] Project code extracted

tar -xf "%UPLOAD_DIR%\1cbffa24-3066-4574-926d-073083bcefcc-1782881365489_server-configs.tar.gz" -C libang-custom\configs
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] Config extract failed (non-critical)
) else (
    echo  [OK] Server configs extracted
)

copy "%UPLOAD_DIR%\886b0c99-2043-4ebd-83c0-b2eb0bcebce1-1782881477061_DEPLOY.md" libang-custom\DEPLOY.md >nul 2>&1
echo  [OK] DEPLOY.md copied

echo.
echo ============================================
echo  Step 2/4: Install Python dependencies
echo ============================================
cd libang-custom

pip install -r backend\requirements.txt
if %ERRORLEVEL% NEQ 0 (
    pip3 install -r backend\requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [FAILED] pip install failed. Check if Python is installed.
        pause
        exit /b 1
    )
)
pip install aiofiles jinja2 >nul 2>&1
echo  [OK] Dependencies installed

echo.
echo ============================================
echo  Step 3/4: Configure API Key
echo ============================================
echo DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY > .env
echo  [OK] .env created

echo.
echo ============================================
echo  Step 4/4: Starting server...
echo ============================================
echo  Open http://127.0.0.1:8000 in your browser
echo  Press Ctrl+C to stop
echo.

python start_server.py
if %ERRORLEVEL% NEQ 0 (
    python3 start_server.py
    if %ERRORLEVEL% NEQ 0 (
        echo [FAILED] Cannot find Python. Install Python 3.9+ and add to PATH.
        pause
        exit /b 1
    )
)

pause
