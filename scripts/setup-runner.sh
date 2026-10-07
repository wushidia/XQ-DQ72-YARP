#!/usr/bin/env bash
set -euo pipefail
mkdir -p "$ARTIFACT_DIR"
date +%s > "$ARTIFACT_DIR/job-started-epoch.txt"
exec > >(tee "$ARTIFACT_DIR/runner.log") 2>&1
df -h
free -h
lsblk
# Resource cleanup is restricted to GitHub's disposable hosted runner.
if [ "${GITHUB_ACTIONS:-false}" = "true" ] && [ "${RUNNER_ENVIRONMENT:-github-hosted}" = "github-hosted" ]; then
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache /usr/local/share/powershell /usr/local/share/chromium
sudo rm -rf /opt/az /opt/microsoft /opt/google /opt/pipx \
  /usr/local/.ghcup /usr/local/share/boost /usr/local/lib/node_modules \
  /usr/share/swift /usr/share/miniconda /usr/share/gradle \
  /usr/local/julia* /usr/local/lib/R /usr/local/aws* \
  /usr/local/lib/python3.*/site-packages /usr/local/lib/python3.*/dist-packages \
  /usr/lib/llvm-* /usr/lib/jvm /usr/share/kotlinc
sudo docker image prune --all --force || true
fi
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  bc bison build-essential ca-certificates curl flex g++-multilib gcc-multilib \
  git gnupg gperf lib32ncurses-dev lib32z1-dev libelf-dev lz4 \
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
mkdir -p "$BUILD_DIR" "$ARTIFACT_DIR/tools/bin"
curl --proto-default https --proto '=https' --fail --location --retry 5 storage.googleapis.com/git-repo-downloads/repo -o "$ARTIFACT_DIR/tools/bin/repo"
chmod +x "$ARTIFACT_DIR/tools/bin/repo"
echo "$ARTIFACT_DIR/tools/bin" >> "$GITHUB_PATH"
# Only a neutral build identity is needed for the local GUI2 merge.
# No user account, login token or credential helper reaches the build.
git config --file "$ARTIFACT_DIR/gitconfig" user.name "Recovery Builder"
git config --file "$ARTIFACT_DIR/gitconfig" user.email builder@localhost
git config --file "$ARTIFACT_DIR/gitconfig" http.version HTTP/1.1
printf 'GIT_CONFIG_GLOBAL=%s\n' "$ARTIFACT_DIR/gitconfig" >> "$GITHUB_ENV"
df -h
free -h
