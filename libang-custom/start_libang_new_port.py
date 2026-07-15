"""在 8002 端口启动力邦定制版，避开端口冲突"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from main import app
import uvicorn

PORT = 8002
print(f"力邦营养企业定制版 — http://127.0.0.1:{PORT}")
uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
