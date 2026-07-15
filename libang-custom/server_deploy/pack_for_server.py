"""打包服务器部署包 — 上传到服务器后用 deploy.sh 一键部署"""
import os, zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(BASE, "..", "4ma_wang_服务器部署包.zip")

EXCLUDE_DIRS = {".git", "__pycache__", "venv", ".venv", "node_modules"}
EXCLUDE_FILES = {
    "package_for_client.py", "_check_whitespace.py",
    "extract_and_setup.py", "extract_libang.py", "inspect_tar.py",
    "check_files.py", "kill_port.py", "force_restart.py",
    "restart_libang.py", "test_check.py", "setup_libang.bat",
}

def should_exclude(name, rel_path):
    if name in EXCLUDE_FILES or name.endswith(".pyc"):
        return True
    parts = rel_path.replace("\\", "/").split("/")
    return any(p in EXCLUDE_DIRS for p in parts)

files_added = 0
with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(BASE):
        rel = os.path.relpath(root, BASE)
        if rel == ".":
            rel = ""
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            rel_path = os.path.join(rel, f) if rel else f
            if should_exclude(f, rel_path):
                continue
            zf.write(os.path.join(root, f), os.path.join("ad-checker-libang", rel_path))
            files_added += 1

print(f"部署包已生成！")
print(f"  文件数: {files_added}")
print(f"  输出: {OUTPUT}")
print(f"\n上传到服务器后执行:")
print(f"  cd ad-checker-libang/server_deploy")
print(f"  sudo bash deploy.sh")
