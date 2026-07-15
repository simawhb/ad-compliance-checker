"""杀掉旧进程，启动力邦定制版"""
import subprocess, os, time, sys

PORT = 8000
BASE = r"D:\驷马仓库\ad-compliance-checker\libang-custom"
VENV_PYTHON = r"C:\Users\whb\.codex\api2codex\venv\Scripts\python.exe"

print("=== 1. 查找并杀掉端口 8000 的进程 ===")
r = subprocess.run(f'netstat -ano | findstr ":{PORT}"', shell=True, capture_output=True, text=True)
print(r.stdout[:300])
pids = set()
for line in r.stdout.strip().split('\n'):
    parts = line.strip().split()
    if len(parts) >= 5 and parts[4].isdigit():
        pids.add(parts[4])

for pid in pids:
    subprocess.run(f'taskkill /f /pid {pid}', shell=True, capture_output=True)
    print(f"  已杀 PID: {pid}")

time.sleep(1)

# 检查端口是否释放
r2 = subprocess.run(f'netstat -ano | findstr ":{PORT}"', shell=True, capture_output=True, text=True)
if r2.stdout.strip():
    print(f"\n=== 端口 {PORT} 仍被占用，改用端口 8001 ===")
    PORT = 8001
else:
    print(f"\n=== 端口 {PORT} 已释放 ===")

print(f"\n=== 2. 启动力邦定制版 (http://127.0.0.1:{PORT}) ===")
os.chdir(BASE)

# 直接启动 uvicorn，不修改文件
sys.path.insert(0, os.path.join(BASE, "backend"))
from main import app
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
