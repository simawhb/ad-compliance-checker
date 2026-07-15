"""杀掉 8000 端口旧进程，启动力邦定制版"""
import subprocess, os, sys, time

PORT = 8000
BASE = r"D:\驷马仓库\ad-compliance-checker\libang-custom"
VENV_PYTHON = r"C:\Users\whb\.codex\api2codex\venv\Scripts\python.exe"

print(f"Step 1: 查找端口 {PORT} 占用进程...")
result = subprocess.run(f'netstat -ano | findstr ":{PORT}"', shell=True, capture_output=True, text=True)
print(result.stdout or "  (无输出)")

pids = set()
for line in result.stdout.strip().split('\n'):
    parts = line.strip().split()
    if len(parts) >= 5 and parts[4].isdigit():
        pids.add(parts[4])

if pids:
    print(f"\nStep 2: 强制杀掉 PID: {', '.join(pids)}")
    for pid in pids:
        r = subprocess.run(f'taskkill /f /pid {pid}', shell=True, capture_output=True, text=True)
        print(f"  PID {pid}: {r.stdout.strip() or r.stderr.strip()}")
    time.sleep(1)
else:
    print(f"\n  端口 {PORT} 无占用")

print(f"\nStep 3: 启动力邦定制版...")
print(f"  访问 http://127.0.0.1:{PORT}")
os.chdir(BASE)
subprocess.run([VENV_PYTHON, "start_server.py"])
