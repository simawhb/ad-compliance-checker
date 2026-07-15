"""查看 tar 包内部结构"""
import tarfile, os

UPLOAD_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    r"Claude-3p\local-agent-mode-sessions\c187ed0d\00000000\local_9c1dcd36-19d6-4134-8bd9-e9b74c154464\uploads"
)
arc = os.path.join(UPLOAD_DIR, "afd1fad5-2b65-4780-a07b-e3ec85d3a2a8-1782881391747_ad-compliance-checker.tar.gz")

print(f"Archive: {arc}")
print(f"Exists: {os.path.exists(arc)}")
print()

with tarfile.open(arc, "r:gz") as tar:
    members = tar.getmembers()
    print(f"Total entries: {len(members)}")
    print()
    print("First 30 entries:")
    for m in members[:30]:
        print(f"  {'D' if m.isdir() else 'F'} {m.name}  ({m.size} bytes)")
    if len(members) > 30:
        print(f"  ... and {len(members)-30} more")

    print()
    # Show unique top-level directories/files
    tops = set()
    for m in members:
        parts = m.name.replace("\\", "/").split("/")
        tops.add(parts[0])
    print(f"Top-level entries: {sorted(tops)}")

    # Show subdirectory structure
    dirs = set()
    for m in members:
        if m.isdir():
            dirs.add(m.name)
    print(f"\nAll directories ({len(dirs)}):")
    for d in sorted(dirs):
        print(f"  {d}")
