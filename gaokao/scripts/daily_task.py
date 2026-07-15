"""驷马报考 每日采集脚本 — 由 Windows 任务计划程序调用"""
import subprocess, sys
from pathlib import Path

PROJECT = Path(r"D:\WorkBuddy\gaokao-database")
SCRIPTS = PROJECT / "src" / "scripts"

def run(cmd):
    print(f"[RUN] {cmd}")
    result = subprocess.run(cmd, cwd=str(PROJECT), capture_output=False)
    if result.returncode != 0:
        print(f"[FAIL] exit={result.returncode}")

print("=== Sima Gaokao Daily Pipeline ===")
run([sys.executable, str(SCRIPTS / "daily_run.py")])
run([sys.executable, str(SCRIPTS / "import_to_sqlite.py")])
run([sys.executable, str(SCRIPTS / "fix_forum_school_ids.py")])
print("=== Done ===")
