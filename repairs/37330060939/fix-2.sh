#!/usr/bin/env bash
set -euo pipefail
python3 - <<'FIXPY'
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
expected = {'scripts/prepare-device.py': '89048d8c72a62046d464e74d0aa591c6d0eef8c8e6eb01ee52fb9d79f5cae647', 'scripts/safe-build.py': 'b8c52c17a0d5c2b8907f959c29ce3598cf720464ec6a6f00cf1cc82cf95b16f4'}
workspace = Path(os.environ["GITHUB_WORKSPACE"])
for relative, digest in expected.items():
    endpoint = "repos/" + os.environ["GITHUB_REPOSITORY"] + "/contents/" + relative + "?ref=main"
    payload = json.loads(subprocess.check_output(["gh", "api", endpoint], text=True))
    content = base64.b64decode(payload["content"])
    assert hashlib.sha256(content).hexdigest() == digest, "Repair source changed unexpectedly"
    (workspace / relative).write_bytes(content)
FIXPY
python3 "$GITHUB_WORKSPACE/scripts/prepare-device.py"
test -s "$BUILD_DIR/cts/tests/tests/os/assets/platform_versions.txt"
test -s "$BUILD_DIR/cts/tests/tests/os/assets/platform_releases.txt"
if grep -q '^PLATFORM_VERSION_LAST_STABLE :=' "$BUILD_DIR/device/sony/sm8550-common/BoardConfigCommon.mk"; then
  echo "Legacy stable release override remains"
  exit 1
fi
git -C "$BUILD_DIR/device/sony/pdx234" diff --check
git -C "$BUILD_DIR/device/sony/sm8550-common" diff --check
git -C "$BUILD_DIR/device/sony/sm8550-common" diff > "$ARTIFACT_DIR/sm8550-common.patch"
printf '%s\n' "Repair: restore pinned CTS release tables, use the platform stable release, and preserve incremental build output." >> "$ARTIFACT_DIR/build-info.txt"
df -h
free -h
