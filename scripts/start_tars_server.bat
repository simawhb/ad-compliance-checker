@echo off
chcp 65001 >nul
echo === TARS MCP Browser Server ?? ===
echo.

:: ????
set PORT=8931
set BROWSER=chrome

:: ??? mcp-server-browser ????
where mcp-server-browser >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [!] mcp-server-browser ?????, ? npm install -g @agent-infra/mcp-server-browser
    exit /b 1
)

echo [?] ??: %BROWSER%
echo [?] ??  : http://127.0.0.1:%PORT%/mcp
echo [???] ?? Ctrl+C ????
echo.

mcp-server-browser --port %PORT% --host 127.0.0.1 --browser %BROWSER% --headless
