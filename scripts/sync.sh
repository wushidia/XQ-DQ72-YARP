#!/usr/bin/env bash
set -euo pipefail
source "$GITHUB_WORKSPACE/config/sources.env"
exec > >(tee "$ARTIFACT_DIR/sync.log") 2>&1
cd "$BUILD_DIR"
repo init -u "$MANIFEST_URL" -b "$MANIFEST_BRANCH" --depth=1 --no-clone-bundle
git -C .repo/manifests fetch --depth=1 origin "$MANIFEST_SHA"
git -C .repo/manifests checkout --detach "$MANIFEST_SHA"
mkdir -p .repo/local_manifests
cp "$GITHUB_WORKSPACE/manifests/sony.xml" .repo/local_manifests/sony.xml
synced=false
for attempt in 1 2 3; do
  if repo sync -c -j4 --no-tags --no-clone-bundle --optimized-fetch --retry-fetches=3; then
    synced=true
    break
  fi
  echo "Source sync attempt $attempt failed; retrying unfinished projects."
  sleep 15
done
if [ "$synced" != true ]; then
  exit 1
fi
repo manifest -r -o "$ARTIFACT_DIR/source-manifest.xml"
df -h
du -sh .repo prebuilts || true
