#!/usr/bin/env bash
set -euo pipefail
exec > >(tee "$ARTIFACT_DIR/build-space.log") 2>&1
python3 "$GITHUB_WORKSPACE/scripts/drop-prebuilt-blobs.py"
# Keep the 8 GiB task swap created during setup. With Soong's Go memory
# limit this leaves more disk for object files than growing swap to 16 GiB.
test -s "$ARTIFACT_DIR/swap-path.txt"
sudo sysctl vm.swappiness=30
free_bytes=$(df --output=avail -B1 "$BUILD_DIR" | tail -n 1)
if [ "$free_bytes" -lt 16106127360 ]; then
  echo "Fewer than 15 GiB remain for compilation; inspect source disk usage."
  du -h --max-depth=2 "$BUILD_DIR"
  exit 1
fi
df -h
free -h
