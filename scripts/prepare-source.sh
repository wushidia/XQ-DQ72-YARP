#!/usr/bin/env bash
set -euo pipefail
source "$GITHUB_WORKSPACE/config/sources.env"
exec > >(tee "$ARTIFACT_DIR/prepare.log") 2>&1
cd "$BUILD_DIR/bootable/recovery"
test "$(git rev-parse HEAD)" = "$RECOVERY_BASE_SHA"
remote_name=$(git remote | head -n 1)
if [ "$(git rev-parse --is-shallow-repository)" = true ]; then
  git fetch --unshallow --no-tags "$remote_name" lvgl
fi
git fetch --no-tags "$remote_name" "$GUI2_PR_HEAD"
test "$(git rev-parse FETCH_HEAD)" = "$GUI2_PR_HEAD"
git merge --no-ff --no-edit FETCH_HEAD
git merge-base --is-ancestor "$RECOVERY_BASE_SHA" HEAD
git merge-base --is-ancestor "$GUI2_PR_HEAD" HEAD
git diff --check
python3 "$GITHUB_WORKSPACE/scripts/prepare-device.py"
git -C "$BUILD_DIR/device/sony/pdx234" diff --check
git -C "$BUILD_DIR/device/sony/sm8550-common" diff --check
git -C "$BUILD_DIR/device/sony/pdx234" diff > "$ARTIFACT_DIR/pdx234.patch"
git -C "$BUILD_DIR/device/sony/sm8550-common" diff > "$ARTIFACT_DIR/sm8550-common.patch"
{
  echo "Device: Sony Xperia 1 V / XQ-DQ72 / pdx234"
  echo "Build target: recoveryimage"
  echo "Build configuration commit: $GITHUB_SHA"
  echo "Manifest branch: $MANIFEST_BRANCH"
  echo "Manifest commit: $MANIFEST_SHA"
  echo "Recovery base: $RECOVERY_BASE_SHA"
  echo "GUI2 PR: https://github.com/TWRP-Test/android_bootable_recovery/pull/31"
  echo "GUI2 PR head: $GUI2_PR_HEAD"
  echo "Merged recovery commit: $(git rev-parse HEAD)"
  echo "Device tree: $DEVICE_SHA"
  echo "SM8550 common tree: $COMMON_SHA"
  echo "LVGL: $LVGL_SHA"
  echo "Action: https://github.com/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
  echo "UTC time: $(date -u +%FT%TZ)"
} | tee "$ARTIFACT_DIR/build-info.txt"
