#!/usr/bin/env python3
"""Free duplicate binary Git blobs after the immutable toolchain is checked out."""
import os
import subprocess
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
projects = [
    "platform/prebuilts/clang/host/linux-x86",
    "platform/prebuilts/rust",
    "platform/prebuilts/sdk",
    "platform/prebuilts/jdk/jdk21",
    "platform/prebuilts/vndk/v31",
    "platform/prebuilts/go/linux-x86",
]
remove = []
for name in projects:
    gitdir = root / ".repo/project-objects" / (name + ".git")
    if not gitdir.is_dir():
        continue
    for index in (gitdir / "objects/pack").glob("*.idx"):
        promisor = index.with_suffix(".promisor")
        if not promisor.exists():
            continue
        objects = subprocess.check_output(["git", "show-index"], input=index.read_bytes(), text=False)
        ids = [line.split()[1] for line in objects.decode().splitlines()]
        if not ids:
            continue
        types = subprocess.check_output(
            ["git", "--git-dir=" + str(gitdir), "cat-file", "--batch-check=%(objecttype)"],
            input=("\n".join(ids) + "\n").encode()).decode().splitlines()
        if len(types) == len(ids) and all(kind == "blob" for kind in types):
            remove.append(index)
# Retain packs containing commits/trees/tags. Missing promisor blobs can be
# fetched again if a later source repair needs them.
freed = 0
for index in remove:
    for suffix in (".pack", ".idx", ".promisor", ".rev"):
        path = index.with_suffix(suffix)
        if path.exists():
            freed += path.stat().st_size
            path.unlink()
print(f"Released {freed / 1024**3:.2f} GiB of duplicate prebuilt Git blobs.")
