import os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "backend"))

if __name__ == "__main__":
    import uvicorn
    os.chdir(os.path.join(BASE, "backend"))
    print("=" * 50)
    print(u"驶马合规 · 广告审查助手 — 力邦营养企业定制版")
    print("=" * 50)
    print(u"启动地址: http://127.0.0.1:8000")
    print(u"批量图片审查: http://127.0.0.1:8000/batch/")
    print(u"企业内用版 · 无配额限制")
    print("=" * 50)
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
