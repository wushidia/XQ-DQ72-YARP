#!/usr/bin/env python3
"""Release duplicate promisor blob packs after a project's checkout completes."""
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
manifest = ET.fromstring(subprocess.check_output(
    ["repo", "manifest"], cwd=root))
selected = set(sys.argv[1:])
names = {p.get("name") for p in manifest.findall("project")
         if not selected or p.get("path", p.get("name")) in selected}
freed = 0
env = dict(os.environ, GIT_NO_LAZY_FETCH="1")
for name in sorted(names):
    gitdir = root / ".repo/project-objects" / (name + ".git")
    if not gitdir.is_dir():
        continue
    project_freed = 0
    for index in list((gitdir / "objects/pack").glob("*.idx")):
        if not index.with_suffix(".promisor").exists():
            continue
        objects = subprocess.check_output(
            ["git", "show-index"], input=index.read_bytes())
        ids = [line.split()[1] for line in objects.decode().splitlines()]
        if not ids:
            continue
        types = subprocess.check_output(
            ["git", "--git-dir=" + str(gitdir), "cat-file", "--batch-check=%(objecttype)"],
            input=("\n".join(ids) + "\n").encode(), env=env).decode().splitlines()
        # Keep all commit, tree and tag metadata. The worktree retains the
        # source files; a future Git operation can fetch a missing blob again.
        if len(types) != len(ids) or not all(kind == "blob" for kind in types):
            continue
        for suffix in (".pack", ".idx", ".promisor", ".rev"):
            path = index.with_suffix(suffix)
            if path.exists():
                project_freed += path.stat().st_size
                path.unlink()
    freed += project_freed
    if project_freed:
        print(f"Released {project_freed / 1024**2:.0f} MiB: {name}", flush=True)
print(f"Released {freed / 1024**3:.2f} GiB of duplicate Git blobs.", flush=True)
