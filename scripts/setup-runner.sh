#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$ARTIFACT_DIR"
date +%s > "$ARTIFACT_DIR/job-started-epoch.txt"
exec > >(tee "$ARTIFACT_DIR/runner.log") 2>&1
df -h
free -h
lsblk
# Only remove preinstalled toolchains from the disposable GitHub-hosted runner.
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache /usr/local/share/powershell /usr/local/share/chromium
sudo rm -rf /opt/az /opt/microsoft /opt/google /opt/pipx \
  /usr/local/.ghcup /usr/local/share/boost /usr/local/lib/node_modules \
  /usr/share/swift /usr/share/miniconda /usr/share/gradle \
  /usr/local/julia* /usr/local/lib/R /usr/local/aws* \
  /usr/local/lib/python3.*/site-packages /usr/local/lib/python3.*/dist-packages \
  /usr/lib/llvm-* /usr/lib/jvm /usr/share/kotlinc
sudo docker image prune --all --force || true
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  bc bison build-essential ca-certificates curl flex g++-multilib gcc-multilib \
  git gnupg gperf lib32ncurses-dev lib32z1-dev libelf-dev liblz4-tool \
  libncurses-dev libsdl2-dev libssl-dev libxml2-utils lzop \
  python3 python3-pip rsync unzip xz-utils zip zstd
sudo apt-get clean
# Soong needs considerably more memory than the private-repository runner provides.
swap_root=/mnt
if [ "$(df --output=avail -BG /mnt | tail -n 1 | tr -dc '0-9')" -lt 10 ]; then
  swap_root=/
fi
swap_file="$swap_root/twrp-build.swap"
sudo fallocate -l 8G "$swap_file"
sudo chmod 600 "$swap_file"
sudo mkswap "$swap_file"
sudo swapon "$swap_file"
sudo sysctl vm.swappiness=60
echo "$swap_file" > "$ARTIFACT_DIR/swap-path.txt"
mkdir -p "$BUILD_DIR" "$HOME/bin"
curl --fail --location --retry 5 https://storage.googleapis.com/git-repo-downloads/repo -o "$HOME/bin/repo"
chmod +x "$HOME/bin/repo"
echo "$HOME/bin" >> "$GITHUB_PATH"
git config --global user.name wushidia
git config --global user.email 65842799+wushidia@users.noreply.github.com
git config --global http.version HTTP/1.1
df -h
free -h
