#!/usr/bin/env python3
"""Keep the build's Linux toolchain versions on the hosted runner."""
import os
import subprocess
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
patterns = {
    "prebuilts/clang/host/linux-x86": [
        "/*", "!/*/", "/clang-r547379/", "/clang-stable/",
        "/llvm-binutils-stable/", "/embedded-sysroots/", "/soong/",
        "/mlgo-models/", "/profiles/",
    ],
    "prebuilts/rust": [
        "/*", "!/*/", "/soong/", "/linux-x86/", "!/linux-x86/*/",
        "/linux-x86/1.83.0/",
    ],
    "prebuilts/jdk/jdk21": ["/*", "!/*/", "/linux-x86/"],
    "prebuilts/sdk": [
        "/*", "!/*/", "/current/", "/tools/", "/extensions/",
        "/29/", "/31/", "/33/", "/34/", "/35/", "/36/",
    ],
}
for project, rules in patterns.items():
    gitdir = root / ".repo/projects" / (project + ".git")
    assert gitdir.is_dir(), f"Missing fetched project: {project}"
    subprocess.run(["git", "--git-dir=" + str(gitdir),
                    "config", "core.sparseCheckout", "true"], check=True)
    info = gitdir / "info"
    info.mkdir(exist_ok=True)
    (info / "sparse-checkout").write_text("\n".join(rules) + "\n")
    print(f"Sparse checkout configured: {project}")
