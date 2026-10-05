#!/usr/bin/env python3
"""Checkout small batches and release duplicate Git blobs between batches."""
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
scripts = Path(os.environ["GITHUB_WORKSPACE"]) / "scripts"
state_path = Path(os.environ["ARTIFACT_DIR"]) / "checkout-state.json"
completed = set(json.loads(state_path.read_text()) if state_path.exists() else [])
manifest = ET.fromstring(subprocess.check_output(["repo", "manifest"], cwd=root))
projects = sorted({p.get("path", p.get("name")) for p in manifest.findall("project")})
todo = [path for path in projects if path not in completed]
for offset in range(0, len(todo), 4):
    batch = todo[offset:offset + 4]
    print(f"Checking out {len(completed)}/{len(projects)} completed: {', '.join(batch)}",
          flush=True)
    result = subprocess.run([
        sys.executable, str(scripts / "safe-sync.py"), "--no-manifest-update",
        "--local-only", "-j4", *batch], cwd=root).returncode
    if result:
        print("Checkout paused; completed batches are preserved.", flush=True)
        sys.exit(result)
    subprocess.run([sys.executable, str(scripts / "drop-prebuilt-blobs.py"), *batch],
                   cwd=root, check=True)
    completed.update(batch)
    state_path.write_text(json.dumps(sorted(completed)) + "\n")
    print(f"Runner free space: {shutil.disk_usage(root).free / 1024**3:.2f} GiB", flush=True)
print(f"All {len(projects)} source projects checked out.", flush=True)
