#!/usr/bin/env python3
"""Apply release patches and source overlays to the verified upstream trees."""
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

workspace = Path(__file__).resolve().parents[1]
source = Path(os.environ["BUILD_DIR"]).resolve()
spec = json.loads((workspace / "patches/series.json").read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(base, relative):
    parts = relative if isinstance(relative, list) else PurePosixPath(relative).parts
    if not parts or any(p in ("", ".", "..") or "/" in p or "\\" in p for p in parts):
        raise ValueError("Invalid relative source path")
    result = base.joinpath(*parts)
    if not result.resolve().is_relative_to(base.resolve()):
        raise ValueError("Source path escapes its directory")
    return result


pending = []
for item in spec["projects"]:
    repository = safe_path(source, item["path"])
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=repository, text=True).strip()
    if tree != item["base_tree"]:
        raise RuntimeError(f"Unexpected upstream tree: {item['path']}")
    patch = safe_path(workspace, item["patch"])
    if digest(patch) != item["patch_sha256"]:
        raise RuntimeError(f"Changed release patch: {item['patch']}")
    records = item["expected_source_hashes"]
    files = [safe_path(repository, record["path"]) for record in records]
    if all(path.is_file() and digest(path) == record["sha256"]
           for path, record in zip(files, records)):
        continue
    relative_files = [path.relative_to(repository).as_posix() for path in files]
    clean = subprocess.run(["git", "diff", "--quiet", "--no-ext-diff", "HEAD", "--"]
                           + relative_files, cwd=repository, capture_output=True)
    if clean.returncode:
        raise RuntimeError(f"Release source has unexpected changes: {item['path']}")
    command = ["git", "apply", "--unidiff-zero"]
    check = subprocess.run(command + ["--check", str(patch)], cwd=repository, capture_output=True)
    if check.returncode:
        raise RuntimeError(f"Release patch conflicts: {item['path']}")
    pending.append((repository, patch))

for repository, patch in pending:
    subprocess.run(["git", "apply", "--unidiff-zero", str(patch)], cwd=repository, check=True)
for item in spec["projects"]:
    for record in item["expected_source_hashes"]:
        path = safe_path(safe_path(source, item["path"]), record["path"])
        if digest(path) != record["sha256"]:
            raise RuntimeError(f"Reconstructed source mismatch: {path.name}")

for original in sorted((workspace / "overlays").rglob("*")):
    if not original.is_file():
        continue
    if original.is_symlink():
        raise RuntimeError("Source overlays must not contain symlinks")
    destination = safe_path(source, original.relative_to(workspace / "overlays").as_posix())
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(original, destination)
for item in spec["copy_upstream_files"]:
    original = safe_path(source, item["source"])
    if digest(original) != item["sha256"]:
        raise RuntimeError("Upstream hardware service checksum mismatch")
    destination = safe_path(source, item["target"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original, destination)
print(f"Applied {spec['build_id']}: {len(spec['projects'])} verified project patches and source overlays.")
