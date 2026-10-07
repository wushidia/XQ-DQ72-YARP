#!/usr/bin/env python3
"""Check release inputs without downloading or compiling Android."""
import ast
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for path in (root / "scripts").glob("*.py"):
    ast.parse(path.read_text(), filename=path.name)
for path in (root / "scripts").glob("*.sh"):
    subprocess.run(["bash", "-n", str(path)], check=True)
spec = json.loads((root / "patches/series.json").read_text())
assert spec["version"] == 1 and spec["build_id"] == "final-logging-v1"
manifest = ET.parse(root / "manifests/final-platform.xml")
projects = {p.get("path", p.get("name")): p for p in manifest.getroot().findall("project")}
for project in projects.values():
    assert re.fullmatch(r"[a-f0-9]{40}", project.get("revision", "")), project.get("name")
for item in spec["projects"]:
    assert item["path"] in projects
    assert re.fullmatch(r"[a-f0-9]{40}", item["base_tree"])
    patch = root / item["patch"]
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == item["patch_sha256"], patch.name
    assert b"GIT binary patch" not in patch.read_bytes()
    if "revision" in item:
        assert projects[item["path"]].get("revision") == item["revision"]
remotes = json.loads((root / "config/source-remotes.json").read_text())
for remote in manifest.getroot().findall("remote"):
    assert remote.get("name") in remotes
    assert remotes[remote.get("name")]["scheme"] == "https"
logger = root / "overlays/device/sony/pdx234/bootlog"
assert (logger / "yarp_bootlog.c").exists() and (logger / "logging_settings.h").exists()
assert 'mPersist.SetValue("tw_metadata_logging", "1")' in (root / "patches/bootable-recovery.patch").read_text()
print(f"PASS release configuration: {len(projects)} pinned dependencies, {len(spec['projects'])} checked source patches.")
