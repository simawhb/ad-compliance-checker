"""力邦营养 · 广告审查助手 — 生产环境启动脚本"""
import os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "backend"))

if __name__ == "__main__":
    import uvicorn
    os.chdir(os.path.join(BASE, "backend"))
    print("=" * 50)
    print("广告审查助手 — 力邦营养企业定制版（生产环境）")
    print("=" * 50)
    print("后端端口: 8001 (仅本地，由 Nginx 反向代理)")
    print("访问地址: https://4ma.wang/ad-check/")
    print("=" * 50)
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=False,
        workers=2,
    )
