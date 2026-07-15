"""检查知识库和关键文件"""
import os

TARGET = r"D:\驷马仓库\ad-compliance-checker\libang-custom"

print("=== 检查目录 ===")
for root, dirs, files in os.walk(TARGET):
    level = root.replace(TARGET, "").count(os.sep)
    if level > 2:
        continue
    indent = "  " * level
    name = os.path.basename(root) if level > 0 else "libang-custom"
    print(f"{indent}{name}/")
    for f in files:
        print(f"{indent}  {f}")

print("\n=== 知识库 ===")
kb = os.path.join(TARGET, "knowledge", "forbidden_words.json")
print(f"knowledge\\forbidden_words.json exists: {os.path.exists(kb)}")

# Also check inline kb
kb_inline = os.path.join(TARGET, "backend", "knowledge", "forbidden_words.json")
print(f"backend\\knowledge\\forbidden_words.json exists: {os.path.exists(kb_inline)}")

# Check the zip for knowledge
import zipfile
UPLOAD_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    r"Claude-3p\local-agent-mode-sessions\c187ed0d\00000000\local_9c1dcd36-19d6-4134-8bd9-e9b74c154464\uploads"
)
zip_path = os.path.join(UPLOAD_DIR, "db296f98-ce4f-4f2b-8374-cad07fb22713-1782892533943_ad-checker-libang.zip")
if os.path.exists(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names = zf.namelist()
        kb_files = [n for n in names if 'knowledge' in n or 'forbidden' in n]
        print(f"\n=== ZIP 中知识库相关文件 ===")
        for f in kb_files:
            print(f"  {f}")
