#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import os
import re
from pathlib import Path
log = Path(os.environ["ARTIFACT_DIR"]) / "build.log"
text = log.read_text(errors="replace")
text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
for name in ("GH_TOKEN", "GITHUB_TOKEN"):
    value = os.environ.get(name)
    if value:
        text = text.replace(value, "[REDACTED]")
lines = text.splitlines()
matches = [i for i, line in enumerate(lines) if re.search(
    r"FAILED:|error:|fatal:|ninja:|Stopping the build|Killed|AssertionError|Traceback|No space left|out of memory", line, re.I)]
selected = set(range(max(0, len(lines) - 70), len(lines)))
for i in matches[-15:]:
    selected.update(range(max(0, i - 3), min(len(lines), i + 12)))
excerpt = "\n".join(lines[i] for i in sorted(selected))[-24000:]
for number, offset in enumerate(range(0, len(excerpt), 6000), 1):
    message = excerpt[offset:offset + 6000].replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print("::notice title=Recovery failure diagnostics " + str(number) + "::" + message, flush=True)
PY
echo "Waiting for a reviewed fix on the existing runner."
endpoint="repos/$GITHUB_REPOSITORY/contents/repairs/$GITHUB_RUN_ID/fix-2.sh?ref=main"
for poll in $(seq 1 80); do
  if payload=$(gh api "$endpoint" 2>/dev/null); then
    printf '%s' "$payload" | python3 -c 'import sys,json,base64; sys.stdout.buffer.write(base64.b64decode(json.load(sys.stdin)["content"]))' > "$ARTIFACT_DIR/fix-2.sh"
    bash -n "$ARTIFACT_DIR/fix-2.sh"
    bash "$ARTIFACT_DIR/fix-2.sh" 2>&1 | tee "$ARTIFACT_DIR/fix-2.log"
    exit 0
  fi
  sleep 15
done
echo "No reviewed fix arrived before the repair deadline."
exit 1
