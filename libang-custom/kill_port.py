"""杀掉占用 8000 端口的进程"""
import subprocess, sys, os

PORT = 8000

# 方法1: 用 taskkill 通过 findstr 查端口
cmds = [
    f'netstat -ano | findstr :{PORT}',
    f'for /f "tokens=5" %p in (\'netstat -ano ^| findstr :{PORT}\') do @taskkill /f /pid %p 2>nul',
]

print(f"查找端口 {PORT} 占用进程...")

# 先查
result = subprocess.run(
    f'netstat -ano | findstr :{PORT}',
    shell=True, capture_output=True, text=True
)
print(result.stdout or result.stderr[:200])

# 获取 PID 并杀掉
lines = result.stdout.strip().split('\n')
pids = set()
for line in lines:
    parts = line.strip().split()
    if len(parts) >= 5:
        pid = parts[4]
        if pid.isdigit():
            pids.add(pid)

if pids:
    for pid in pids:
        kill = subprocess.run(
            f'taskkill /f /pid {pid}',
            shell=True, capture_output=True, text=True
        )
        print(f"PID {pid}: {kill.stdout.strip() or kill.stderr.strip()}")
    print("进程已杀掉，可以重启服务了")
else:
    print(f"端口 {PORT} 没有占用的进程")

# 确认
result2 = subprocess.run(
    f'netstat -ano | findstr :{PORT}',
    shell=True, capture_output=True, text=True
)
if result2.stdout.strip():
    print(f"⚠️ 仍有进程占用: {result2.stdout.strip()[:200]}")
else:
    print(f"✅ 端口 {PORT} 已释放")
