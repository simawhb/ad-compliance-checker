"""解压立邦定制版 ZIP 包"""
import zipfile, os, shutil, stat

BASE_DIR = r"D:\驷马仓库\ad-compliance-checker"
UPLOAD_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    r"Claude-3p\local-agent-mode-sessions\c187ed0d\00000000\local_9c1dcd36-19d6-4134-8bd9-e9b74c154464\uploads"
)
TARGET_DIR = os.path.join(BASE_DIR, "libang-custom")

zip_path = os.path.join(UPLOAD_DIR, "db296f98-ce4f-4f2b-8374-cad07fb22713-1782892533943_ad-checker-libang.zip")
print(f"ZIP: {zip_path}")
print(f"Exists: {os.path.exists(zip_path)}")

# List contents
with zipfile.ZipFile(zip_path, 'r') as zf:
    names = zf.namelist()
    print(f"\nTotal entries: {len(names)}")
    print("\nFirst 50 entries:")
    for n in names[:50]:
        info = zf.getinfo(n)
        print(f"  {'D' if n.endswith('/') else 'F'} {n}  ({info.file_size} bytes)")
    if len(names) > 50:
        print(f"  ... and {len(names)-50} more")

    # Top-level
    tops = set()
    for n in names:
        tops.add(n.split("/")[0])
    print(f"\nTop-level: {sorted(tops)}")

print("\n--- Extracting ---")
os.makedirs(TARGET_DIR, exist_ok=True)

with zipfile.ZipFile(zip_path, 'r') as zf:
    zf.extractall(path=TARGET_DIR)

print(f"Extracted to: {TARGET_DIR}")

# Show structure
print("\nStructure (excluding .git & venv):")
for root, dirs, files in os.walk(TARGET_DIR):
    rel = root.replace(TARGET_DIR, "").replace(os.sep, "/")
    if "/.git/" in rel or "/venv/" in rel or rel in ("/.git", "/venv"):
        continue
    level = rel.count("/")
    if level > 2:
        continue
    indent = "  " * level
    name = os.path.basename(root) if level > 0 else "libang-custom"
    print(f"{indent}{name}/")
    for f in files[:5]:
        print(f"{indent}  {f}")
