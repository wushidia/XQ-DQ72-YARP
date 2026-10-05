#!/usr/bin/env bash
set -eo pipefail
exec > >(tee "$ARTIFACT_DIR/build.log") 2>&1
rm -f "$ARTIFACT_DIR/build-success"
case "$BUILD_JOBS" in 1|2|3|4) ;; *) echo "Invalid BUILD_JOBS"; exit 1 ;; esac
cd "$BUILD_DIR"
export ALLOW_MISSING_DEPENDENCIES=true
export LC_ALL=C
source build/envsetup.sh
lunch twrp_pdx234 bp2a eng
mka installclean
mka -j"$BUILD_JOBS" recoveryimage
image="$BUILD_DIR/out/target/product/pdx234/recovery.img"
test -s "$image"
cp "$image" "$ARTIFACT_DIR/recovery.img"
python3 "$GITHUB_WORKSPACE/scripts/verify-image.py"
cd "$ARTIFACT_DIR"
sha256sum recovery.img > SHA256SUMS
cat SHA256SUMS
touch "$ARTIFACT_DIR/build-success"
{
  echo "### Xperia 1 V GUI2 recovery built"
  echo
  echo 'Download the Xperia-1V-XQ-DQ72-GUI2 artifact for recovery.img and SHA256SUMS.'
  echo
  echo 'Build verification checks the Android recovery image structure and size.'
  echo 'Boot, touchscreen and decryption still require testing on the device.'
} >> "$GITHUB_STEP_SUMMARY"
