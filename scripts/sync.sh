#!/usr/bin/env bash
set -euo pipefail
source "$GITHUB_WORKSPACE/config/sources.env"
exec > >(tee "$ARTIFACT_DIR/sync.log") 2>&1
cd "$BUILD_DIR"
repo init -u "$MANIFEST_URL" -b "$MANIFEST_BRANCH" --depth=1 --no-clone-bundle \
  --partial-clone --clone-filter=blob:none
test "$(git -C .repo/manifests rev-parse HEAD)" = "$MANIFEST_SHA"
mkdir -p .repo/local_manifests
cp "$GITHUB_WORKSPACE/manifests/sony.xml" .repo/local_manifests/sony.xml
sync_phase() {
  for attempt in 1 2 3; do
    if repo sync --no-manifest-update -c -j4 --no-tags --no-clone-bundle \
        --optimized-fetch --retry-fetches=3 "$@"; then
      return 0
    fi
    echo "Sync attempt $attempt failed; retrying unfinished projects."
    sleep 15
  done
  return 1
}
# Fetch commit/tree metadata first. Do not fetch unused compiler/host binaries.
sync_phase --network-only
python3 "$GITHUB_WORKSPACE/scripts/sparse-prebuilts.py"
sync_phase --local-only
repo manifest -r -o "$ARTIFACT_DIR/source-manifest.xml"
df -h
du -sh .repo prebuilts || true
