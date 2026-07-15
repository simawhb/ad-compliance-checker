"""打包力邦营养定制版 — 生成交付压缩包"""
import os, zipfile, shutil

SOURCE = r"D:\驷马仓库\ad-compliance-checker\libang-custom"
OUTPUT = r"D:\驷马仓库\ad-compliance-checker\力邦营养_广告审查助手_交付版.zip"

# 要排除的目录
EXCLUDE_DIRS = {".git", "__pycache__", "venv", "node_modules", ".venv"}
# 要排除的文件
EXCLUDE_FILES = {
    "extract_and_setup.py", "extract_libang.py", "inspect_tar.py",
    "check_files.py", "kill_port.py", "force_restart.py",
    "restart_libang.py", "test_check.py", "setup_libang.bat",
    "extract_libang.py",
}
# 打包时额外排除的路径模式
EXCLUDE_PATTERNS = {"**/__pycache__/**", "**/*.pyc"}

def should_exclude(name, rel_path):
    # 排除指定文件
    if name in EXCLUDE_FILES:
        return True
    # 排除 .pyc 文件
    if name.endswith(".pyc"):
        return True
    # 排除路径中包含这些目录的
    parts = rel_path.replace("\\", "/").split("/")
    for part in parts:
        if part in EXCLUDE_DIRS:
            return True
    return False

files_added = 0
total_size = 0

with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(SOURCE):
        # 计算相对路径
        rel = os.path.relpath(root, SOURCE)
        if rel == ".":
            rel = ""

        # 跳过排除的目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for f in files:
            rel_path = os.path.join(rel, f) if rel else f
            if should_exclude(f, rel_path):
                continue
            full_path = os.path.join(root, f)
            arcname = os.path.join("ad-checker-libang", rel_path)
            zf.write(full_path, arcname)
            files_added += 1
            total_size += os.path.getsize(full_path)

print(f"打包完成！")
print(f"  文件数: {files_added}")
print(f"  总大小: {total_size/1024:.1f} KB")
print(f"  输出: {OUTPUT}")
print(f"\n交付给客户后，解压运行 start_libang.bat 即可。")
