"""
驷马合规 · Libang 定制版 — 重新解压（修复版 v2）
"""
import tarfile
import shutil
import os
import subprocess
import sys
import tempfile
import stat

BASE_DIR = r"D:\驷马仓库\ad-compliance-checker"
UPLOAD_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ""),
    r"Claude-3p\local-agent-mode-sessions\c187ed0d\00000000\local_9c1dcd36-19d6-4134-8bd9-e9b74c154464\uploads"
)
TARGET_DIR = os.path.join(BASE_DIR, "libang-custom")

FILES = {
    "project": "afd1fad5-2b65-4780-a07b-e3ec85d3a2a8-1782881391747_ad-compliance-checker.tar.gz",
    "configs": "1cbffa24-3066-4574-926d-073083bcefcc-1782881365489_server-configs.tar.gz",
    "deploy": "886b0c99-2043-4ebd-83c0-b2eb0bcebce1-1782881477061_DEPLOY.md",
}

KEEP_FILES = {"extract_and_setup.py", "setup_libang.bat", "inspect_tar.py"}

def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

def del_ro(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def safe_rmtree(path):
    try:
        shutil.rmtree(path, onexc=del_ro)
    except Exception as e:
        print(f"  [WARN] Could not remove {os.path.basename(path)}: {e}")

def safe_remove(path):
    try:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)
    except Exception:
        pass  # will be overwritten anyway

def extract_safe(archive_path, dest_dir):
    """Extract tar.gz to dest_dir, handling top-level directory."""
    print(f"  Extracting: {os.path.basename(archive_path)}")
    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()
        print(f"  Archive contains {len(members)} entries")

        with tempfile.TemporaryDirectory() as tmpdir:
            tar.extractall(path=tmpdir)
            items = os.listdir(tmpdir)
            print(f"  Extracted items: {items[:5]}{'...' if len(items)>5 else ''}")

            # Determine source: if single top-level dir, go inside it
            if len(items) == 1 and os.path.isdir(os.path.join(tmpdir, items[0])):
                src_root = os.path.join(tmpdir, items[0])
                print(f"  Stripping top-level dir: {items[0]}")
            else:
                src_root = tmpdir

            # Move items to destination, handling conflicts
            for item in os.listdir(src_root):
                src = os.path.join(src_root, item)
                dst = os.path.join(dest_dir, item)
                if os.path.exists(dst):
                    if os.path.isdir(dst):
                        safe_rmtree(dst)
                    else:
                        safe_remove(dst)
                try:
                    shutil.move(src, dst)
                except Exception as e:
                    print(f"  [WARN] Could not move {item}: {e}")

    print(f"  Done")

def main():
    os.chdir(BASE_DIR)
    os.makedirs(TARGET_DIR, exist_ok=True)

    # ---- Step 1: Clean (best-effort) ----
    step("Step 1: Clean old extraction (best-effort)")
    for item in os.listdir(TARGET_DIR):
        if item in KEEP_FILES:
            continue
        path = os.path.join(TARGET_DIR, item)
        if os.path.isdir(path):
            safe_rmtree(path)
            if not os.path.exists(path):
                print(f"  Removed dir: {item}")
            else:
                print(f"  Skipped dir (in use): {item}")
        else:
            safe_remove(path)
            if not os.path.exists(path):
                print(f"  Removed file: {item}")

    # ---- Step 2: Extract project ----
    step("Step 2: Extract project code")
    project_arc = os.path.join(UPLOAD_DIR, FILES["project"])
    if os.path.exists(project_arc):
        extract_safe(project_arc, TARGET_DIR)
    else:
        print(f"  [ERROR] File not found: {project_arc}")
        return

    # ---- Step 3: Extract configs ----
    step("Step 3: Extract server configs")
    configs_arc = os.path.join(UPLOAD_DIR, FILES["configs"])
    configs_dir = os.path.join(TARGET_DIR, "configs")
    os.makedirs(configs_dir, exist_ok=True)
    if os.path.exists(configs_arc):
        extract_safe(configs_arc, configs_dir)

    # ---- Step 4: DEPLOY.md ----
    step("Step 4: Copy DEPLOY.md")
    deploy_src = os.path.join(UPLOAD_DIR, FILES["deploy"])
    deploy_dst = os.path.join(TARGET_DIR, "DEPLOY.md")
    if os.path.exists(deploy_src):
        shutil.copy2(deploy_src, deploy_dst)
        print(f"  DEPLOY.md copied")

    # ---- Show structure ----
    step("Extracted structure")
    dirs, files = 0, 0
    for root, dlist, flist in os.walk(TARGET_DIR):
        # Skip .git and venv for display
        rel = root.replace(TARGET_DIR, "").replace(os.sep, "/")
        if "/.git/" in rel or rel.startswith("/.git") or "/venv/" in rel or rel.startswith("/venv"):
            continue
        level = rel.count("/")
        if level > 2:
            dirs += len(dlist)
            files += len(flist)
            continue
        indent = "  " * level
        name = os.path.basename(root) if level > 0 else "libang-custom"
        print(f"{indent}{name}/")
        for f in flist[:3]:
            print(f"{indent}  {f}")
        if len(flist) > 3:
            print(f"{indent}  ...")
        dirs += len(dlist)
        files += len(flist)
    print(f"  (Total: ~{dirs} dirs, ~{files} files, excluding .git & venv)")

    # ---- Step 5: Install deps ----
    step("Step 5: Install dependencies")
    venv_python = os.path.join(TARGET_DIR, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        python_exe = venv_python
        print(f"  Using bundled venv Python")
    else:
        python_exe = sys.executable
        print(f"  Using system Python")

    req_file = os.path.join(TARGET_DIR, "backend", "requirements.txt")
    if os.path.exists(req_file):
        r = subprocess.run(
            [python_exe, "-m", "pip", "install", "-r", req_file, "--no-cache-dir"],
            capture_output=True, text=True
        )
        if r.returncode != 0:
            print(f"  pip note: {r.stderr[:200]}")
        else:
            print(f"  Dependencies OK")

    # ---- Step 6: .env ----
    step("Step 6: Configure .env")
    with open(os.path.join(TARGET_DIR, ".env"), "w") as f:
        f.write("DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY\n")
    print(f"  .env ready")

    # ---- Step 7: Start ----
    step("Step 7: Start server")
    server_script = os.path.join(TARGET_DIR, "start_server.py")
    if os.path.exists(server_script):
        print(f"\n  http://127.0.0.1:8000\n")
        os.chdir(TARGET_DIR)
        subprocess.run([python_exe, server_script])
    else:
        print(f"  [ERROR] start_server.py not found!")

if __name__ == "__main__":
    main()
