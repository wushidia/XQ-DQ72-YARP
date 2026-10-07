#!/usr/bin/env bash
set -eo pipefail
exec > >(tee "$ARTIFACT_DIR/build.log") 2>&1
rm -f "$ARTIFACT_DIR/build-success"
case "$BUILD_JOBS" in 1|2|3|4|5|6|7|8|9|10|11|12|13|14|15|16) ;; *) echo "Invalid BUILD_JOBS"; exit 1 ;; esac
cd "$BUILD_DIR"
report_resources() {
  status=$?
  trap - EXIT
  df -h
  free -h
  du -sh out 2>/dev/null || true
  exit "$status"
}
trap report_resources EXIT
export ALLOW_MISSING_DEPENDENCIES=true
export LC_ALL=C
# Use the hosted runner memory budget for Soong while retaining swap as a safety buffer.
# These remain overridable for a larger self-hosted runner.
export GOMAXPROCS="${GOMAXPROCS:-2}"
export GOGC="${GOGC:-50}"
export SOONG_GOMEMLIMIT="${SOONG_GOMEMLIMIT:-6GiB}"
export GOMEMLIMIT="${GOMEMLIMIT:-6GiB}"
echo "Soong Go settings: GOMAXPROCS=$GOMAXPROCS GOGC=$GOGC SOONG_GOMEMLIMIT=$SOONG_GOMEMLIMIT"
python3 "$GITHUB_WORKSPACE/scripts/safe-build.py"
python3 "$GITHUB_WORKSPACE/scripts/finalize-ramdisk.py"
"$BUILD_DIR/prebuilts/build-tools/linux-x86/bin/ninja" -f "$BUILD_DIR/out/combined-twrp_pdx234.ninja" recoveryimage
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
  echo 'Build verification checks image structure, size, ARM64 recovery, fstab and GUI2 presence.'
  echo 'Boot, touchscreen and decryption still require testing on the device.'
} >> "$GITHUB_STEP_SUMMARY"