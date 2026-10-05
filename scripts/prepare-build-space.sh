#!/usr/bin/env bash
set -euo pipefail
exec > >(tee "$ARTIFACT_DIR/build-space.log") 2>&1
python3 "$GITHUB_WORKSPACE/scripts/drop-prebuilt-blobs.py"
swap_file=$(cat "$ARTIFACT_DIR/swap-path.txt")
sudo swapoff "$swap_file"
sudo rm "$swap_file"
# Leave at least 10 GiB for build output; use up to 16 GiB disk swap.
free_gib=$(df --output=avail -B1 "$BUILD_DIR" | tail -n 1)
swap_gib=$((free_gib / 1073741824 - 10))
if [ "$swap_gib" -gt 16 ]; then swap_gib=16; fi
if [ "$swap_gib" -lt 8 ]; then
  echo "Insufficient free disk for both compilation and swap."
  df -h
  exit 1
fi
sudo fallocate -l "${swap_gib}G" "$swap_file"
sudo chmod 600 "$swap_file"
sudo mkswap "$swap_file"
sudo swapon "$swap_file"
df -h
free -h
