@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 广告审查助手 · 力邦营养企业定制版
echo ================================
echo.
echo 安装依赖...
pip install -r backend\requirements.txt -q
pip install aiofiles jinja2 -q
echo.
echo 启动服务...
echo 访问地址：http://127.0.0.1:8000
echo.
python start_server.py
pause
