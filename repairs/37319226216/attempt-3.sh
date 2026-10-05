#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import os
from pathlib import Path
root = Path(os.environ["BUILD_DIR"])
workspace = Path(os.environ["GITHUB_WORKSPACE"])
(workspace / "scripts/sparse-prebuilts.py").write_text("#!/usr/bin/env python3\n\"\"\"Keep the build's Linux toolchain versions on the hosted runner.\"\"\"\nimport os\nimport subprocess\nfrom pathlib import Path\n\nroot = Path(os.environ[\"BUILD_DIR\"])\npatterns = {\n    \"prebuilts/clang/host/linux-x86\": [\n        \"/*\", \"!/*/\", \"/clang-r547379/\", \"/clang-stable/\",\n        \"/llvm-binutils-stable/\", \"/embedded-sysroots/\", \"/soong/\",\n        \"/mlgo-models/\", \"/profiles/\",\n    ],\n    \"prebuilts/rust\": [\n        \"/*\", \"!/*/\", \"/soong/\", \"/linux-x86/\", \"!/linux-x86/*/\",\n        \"/linux-x86/1.83.0/\",\n    ],\n    \"prebuilts/jdk/jdk21\": [\"/*\", \"!/*/\", \"/linux-x86/\"],\n    \"prebuilts/misc\": [\n        \"/*\", \"!/*/\", \"/.prebuilt_info/\", \"/common/\", \"/linux-x86/\", \"/protobuf_vendorcompat/\",\n    ],\n    \"prebuilts/tools\": [\"/*\", \"!/*/\", \"/common/\", \"/linux-x86_64/\"],\n    \"prebuilts/build-tools\": [\n        \"/*\", \"!/*/\", \"/common/\", \"/linux-x86/\", \"/linux_musl-x86/\", \"/path/\", \"/sysroots/\",\n    ],\n    \"cts\": [\"/*\", \"!/*/\", \"/build/\", \"/common/\", \"/libs/\"],\n    \"prebuilts/sdk\": [\n        \"/*\", \"!/*/\", \"/current/\", \"/tools/\", \"/extensions/\", \"/update_prebuilts/\",\n        \"/29/\", \"/31/\", \"/33/\", \"/34/\", \"/35/\", \"/36/\",\n    ],\n}\nfor project, rules in patterns.items():\n    gitdir = root / \".repo/projects\" / (project + \".git\")\n    assert gitdir.is_dir(), f\"Missing fetched project: {project}\"\n    subprocess.run([\"git\", \"--git-dir=\" + str(gitdir),\n                    \"config\", \"core.sparseCheckout\", \"true\"], check=True)\n    info = gitdir / \"info\"\n    info.mkdir(exist_ok=True)\n    (info / \"sparse-checkout\").write_text(\"\\n\".join(rules) + \"\\n\")\n    print(f\"Sparse checkout configured: {project}\")\n")
(workspace / "scripts/build.sh").write_text("#!/usr/bin/env bash\nset -eo pipefail\nexec > >(tee \"$ARTIFACT_DIR/build.log\") 2>&1\nrm -f \"$ARTIFACT_DIR/build-success\"\ncase \"$BUILD_JOBS\" in 1|2|3|4) ;; *) echo \"Invalid BUILD_JOBS\"; exit 1 ;; esac\ncd \"$BUILD_DIR\"\nreport_resources() {\n  status=$?\n  trap - EXIT\n  df -h\n  free -h\n  du -sh out 2>/dev/null || true\n  exit \"$status\"\n}\ntrap report_resources EXIT\nexport ALLOW_MISSING_DEPENDENCIES=true\nexport LC_ALL=C\nsource build/envsetup.sh\nlunch twrp_pdx234 bp2a eng\nmka installclean\nmka -j\"$BUILD_JOBS\" recoveryimage\nimage=\"$BUILD_DIR/out/target/product/pdx234/recovery.img\"\ntest -s \"$image\"\ncp \"$image\" \"$ARTIFACT_DIR/recovery.img\"\npython3 \"$GITHUB_WORKSPACE/scripts/verify-image.py\"\ncd \"$ARTIFACT_DIR\"\nsha256sum recovery.img > SHA256SUMS\ncat SHA256SUMS\ntouch \"$ARTIFACT_DIR/build-success\"\n{\n  echo \"### Xperia 1 V GUI2 recovery built\"\n  echo\n  echo 'Download the Xperia-1V-XQ-DQ72-GUI2 artifact for recovery.img and SHA256SUMS.'\n  echo\n  echo 'Build verification checks the Android recovery image structure and size.'\n  echo 'Boot, touchscreen and decryption still require testing on the device.'\n} >> \"$GITHUB_STEP_SUMMARY\"\n")
pattern = root / ".repo/projects/prebuilts/sdk.git/info/sparse-checkout"
text = pattern.read_text()
if "/update_prebuilts/\n" not in text:
    pattern.write_text(text + "/update_prebuilts/\n")
PY
git -C "$BUILD_DIR/prebuilts/sdk" read-tree -mu HEAD
test -f "$BUILD_DIR/prebuilts/sdk/update_prebuilts.py"
python3 "$GITHUB_WORKSPACE/scripts/drop-prebuilt-blobs.py" prebuilts/sdk
find "$BUILD_DIR/prebuilts" -xtype l -printf '%p -> %l\n' | head -n 80 || true
printf '%s\n' "Repair attempt 3: retain the SDK updater directory required by its root symlink." >> "$ARTIFACT_DIR/build-info.txt"
df -h
free -h
