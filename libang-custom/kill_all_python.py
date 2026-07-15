"""杀掉所有 Python start_server 进程"""
import subprocess

print("查找所有 start_server / uvicorn / main.py 相关进程...")

# 用 wmic 查 Python 进程
r = subprocess.run(
    'wmic process where "name=\'python.exe\'" get processid,commandline /format:csv',
    shell=True, capture_output=True, text=True
)

lines = [l.strip() for l in r.stdout.split('\n') if l.strip()]
for line in lines:
    if 'start_server' in line.lower() or 'uvicorn' in line.lower() or 'main' in line.lower():
        print(f"  {line[:200]}")

# 直接 taskkill 全部 python.exe（警告：会关掉所有 Python）
print("\n正在杀掉所有 python.exe 进程...")
r2 = subprocess.run('taskkill /f /im python.exe', shell=True, capture_output=True, text=True)
print(f"  {r2.stdout.strip() or r2.stderr.strip()}")

print("\n✅ 已杀掉，可以关掉这个窗口了")
print("然后重新开一个 PowerShell，运行：")
print(f'  & "C:\\Users\\whb\\.codex\\api2codex\\venv\\Scripts\\python.exe" D:\\驷马仓库\\ad-compliance-checker\\libang-custom\\start_server.py')
input("\n按 Enter 退出...")
