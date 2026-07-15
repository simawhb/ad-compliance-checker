"""打包驷马粮选后端，用于服务器部署"""
import tarfile, os

BASE = r"W:\SiMaRepo\驷马粮选\backend"
OUTPUT = r"D:\驷马仓库\ad-compliance-checker\libang-custom\server_deploy\simaliangxuan-deploy.tar.gz"

EXCLUDE_DIRS = {"__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}

count = 0
with tarfile.open(OUTPUT, "w:gz") as tar:
    for root, dirs, files in os.walk(BASE):
        rel = os.path.relpath(root, BASE)
        if rel == ".":
            rel = ""
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if any(f.endswith(s) for s in EXCLUDE_SUFFIXES):
                continue
            rel_path = os.path.join(rel, f) if rel else f
            full = os.path.join(root, f)
            arcname = os.path.join("simaliangxuan", rel_path)
            tar.add(full, arcname)
            count += 1

print(f"部署包已生成！")
print(f"  文件数: {count}")
print(f"  大小: {os.path.getsize(OUTPUT)/1024:.0f} KB")
print(f"  路径: {OUTPUT}")
