#!/usr/bin/env python3
"""Stop source synchronization before a full disk kills the Actions runner."""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
process = subprocess.Popen(["repo", "sync", *sys.argv[1:]], start_new_session=True)
while process.poll() is None:
    if shutil.disk_usage(root).free < 5 * 1024**3:
        print("Stopping sync: fewer than 5 GiB remain on the runner.", flush=True)
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        result = subprocess.run(
            ["du", "-h", "--max-depth=6", str(root / ".repo/project-objects")],
            text=True, capture_output=True)
        sizes = []
        for line in result.stdout.splitlines():
            size, path = line.split("\t", 1)
            scale = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
            suffix = size[-1]
            value = float(size[:-1]) * scale[suffix] if suffix in scale else float(size)
            sizes.append((value, line))
        print("\n".join(line for _, line in sorted(sizes, reverse=True)[:30]), flush=True)
        print(subprocess.check_output(["df", "-h"], text=True), flush=True)
        sys.exit(86)
    time.sleep(2)
sys.exit(process.returncode if process.returncode >= 0 else 1)
