#!/usr/bin/env bash
set -euo pipefail
attempt="$1"
case "$attempt" in 2|3|4|5|6|7|8) ;; *) exit 1 ;; esac
repair_path="repairs/$GITHUB_RUN_ID/attempt-$attempt.sh"
endpoint="repos/$GITHUB_REPOSITORY/contents/$repair_path?ref=main"
echo "Waiting up to 45 minutes for $repair_path in this build repository."
for poll in $(seq 1 60); do
  if payload=$(gh api "$endpoint" 2>/dev/null); then
    printf '%s' "$payload" | python3 -c 'import sys,json,base64; sys.stdout.buffer.write(base64.b64decode(json.load(sys.stdin)["content"]))' > "$ARTIFACT_DIR/repair-$attempt.sh"
    bash -n "$ARTIFACT_DIR/repair-$attempt.sh"
    bash "$ARTIFACT_DIR/repair-$attempt.sh" 2>&1 | tee "$ARTIFACT_DIR/repair-$attempt.log"
    exit 0
  fi
  sleep 45
done
echo "No repair was supplied; ending this build."
exit 1
