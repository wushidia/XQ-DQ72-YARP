#!/usr/bin/env python3
"""Report build resource use and stop before exhaustion kills the Actions runner."""
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
job_start_file = Path(os.environ["ARTIFACT_DIR"]) / "job-started-epoch.txt"
time_limit = int(os.environ.get("BUILD_TIME_LIMIT_MINUTES", "330" if os.environ.get("GITHUB_ACTIONS") == "true" else "0"))
job_deadline = int(job_start_file.read_text().strip()) + time_limit * 60 if time_limit else None
command = """set -eo pipefail
source build/envsetup.sh
lunch twrp_pdx234 bp2a eng
if [ "${RUN_INSTALLCLEAN:-1}" = "1" ]; then mka installclean; fi
mka -j"$BUILD_JOBS" recoveryimage
"""
process = subprocess.Popen(["bash", "-c", command], cwd=root, start_new_session=True)
started = time.monotonic()
last_report = -60.0
while process.poll() is None:
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        memory[key] = int(value.split()[0]) * 1024
    free = shutil.disk_usage(root).free
    elapsed = time.monotonic() - started
    if elapsed - last_report >= 60:
        print(f"Build resources at {elapsed / 60:.1f} min: disk free {free / 1024**3:.2f} GiB; "
              f"RAM available {memory['MemAvailable'] / 1024**3:.2f} GiB; "
              f"swap free {memory['SwapFree'] / 1024**3:.2f} GiB", flush=True)
        result = subprocess.run(["ps", "-eo", "pid,ppid,rss,pcpu,comm", "--sort=-rss"],
                                text=True, capture_output=True)
        print("\n".join(result.stdout.splitlines()[:7]), flush=True)
        last_report = elapsed
    reason = None
    if free < 4 * 1024**3:
        reason = "fewer than 4 GiB remain for the runner and diagnostics"
    elif memory["MemAvailable"] < 192 * 1024**2 and memory["SwapFree"] < 512 * 1024**2:
        reason = "RAM and swap are nearly exhausted"
    elif job_deadline is not None and time.time() >= job_deadline:
        reason = "the job is approaching its 6-hour limit; preserving diagnostics before cancellation"
    if reason:
        print("Stopping the build safely: " + reason, flush=True)
        # Include descendants that create their own process groups.
        descendants = {process.pid}
        table = subprocess.check_output(["ps", "-eo", "pid=,ppid="], text=True)
        pairs = [tuple(map(int, line.split())) for line in table.splitlines()]
        changed = True
        while changed:
            changed = False
            for pid, parent in pairs:
                if parent in descendants and pid not in descendants:
                    descendants.add(pid)
                    changed = True
        for pid in sorted(descendants, reverse=True):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            for pid in descendants:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
        print(subprocess.check_output(["du", "-h", "--max-depth=2", str(root / "out")],
                                      text=True), flush=True)
        sys.exit(86)
    time.sleep(5)
sys.exit(process.returncode if process.returncode >= 0 else 1)
