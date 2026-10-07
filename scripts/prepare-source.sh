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
git -c user.name="Recovery Builder" -c user.email=builder@localhost merge --no-ff --no-edit FETCH_HEAD
git merge-base --is-ancestor "$RECOVERY_BASE_SHA" HEAD
git merge-base --is-ancestor "$GUI2_PR_HEAD" HEAD
python3 "$GITHUB_WORKSPACE/scripts/apply-customizations.py"
python3 "$GITHUB_WORKSPACE/scripts/prepare-device.py"
for project in bootable/recovery device/sony/pdx234 device/sony/sm8550-common system/hwservicemanager system/libbase system/vold; do
  git -C "$BUILD_DIR/$project" diff --check
done
{
  echo "Device: Sony Xperia 1 V / XQ-DQ72 / pdx234"
  echo "Release: final-logging-v1"
  echo "Build target: recoveryimage"
  echo "Build configuration commit: $GITHUB_SHA"
  echo "Manifest commit: $MANIFEST_SHA"
  echo "Recovery base: $RECOVERY_BASE_SHA"
  echo "GUI2 PR: TWRP-Test/android_bootable_recovery#31"
  echo "GUI2 PR head: $GUI2_PR_HEAD"
  echo "Merged recovery commit: $(git rev-parse HEAD)"
  echo "Release patch series: $(sha256sum "$GITHUB_WORKSPACE/patches/series.json" | cut -d ' ' -f 1)"
  echo "GitHub Actions run: $GITHUB_REPOSITORY $GITHUB_RUN_ID"
  echo "UTC time: $(date -u +%FT%TZ)"
} | tee "$ARTIFACT_DIR/build-info.txt"
