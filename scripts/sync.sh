#!/usr/bin/env bash
set -euo pipefail
source "$GITHUB_WORKSPACE/config/sources.env"
export REPO_ALLOW_SHALLOW=1
phase="$1"
cd "$BUILD_DIR"
sync_phase() {
  for attempt in 1 2 3; do
    result=0
    python3 "$GITHUB_WORKSPACE/scripts/safe-sync.py" \
      --no-manifest-update -c -j4 --no-tags --no-clone-bundle \
      --optimized-fetch --retry-fetches=3 "$@" || result=$?
    if [ "$result" = 0 ]; then return 0; fi
    if [ "$result" = 86 ]; then return 86; fi
    echo "Sync attempt $attempt failed; retrying unfinished projects."
    sleep 15
  done
  return 1
}
case "$phase" in
  metadata)
    exec > >(tee "$ARTIFACT_DIR/sync.log") 2>&1
    repo init -u "$MANIFEST_URL" -b "$MANIFEST_BRANCH" --depth=1 --no-clone-bundle \
      --partial-clone --clone-filter=blob:none
    test "$(git -C .repo/manifests rev-parse HEAD)" = "$MANIFEST_SHA"
    mkdir -p .repo/local_manifests
    cp "$GITHUB_WORKSPACE/manifests/sony.xml" .repo/local_manifests/sony.xml
    git -C .repo/manifests config --get-regexp 'repo.(depth|clonefilter|partialclone)'
    sync_phase --network-only
    ;;
  checkout)
    exec > >(tee "$ARTIFACT_DIR/checkout.log") 2>&1
    python3 "$GITHUB_WORKSPACE/scripts/sparse-prebuilts.py"
    sync_phase --local-only
    repo manifest -r -o "$ARTIFACT_DIR/source-manifest.xml"
    ;;
  *) echo "Unknown sync phase"; exit 1 ;;
esac
df -h
du -sh .repo prebuilts 2>/dev/null || true
