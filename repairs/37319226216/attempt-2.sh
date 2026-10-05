#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
import os
from pathlib import Path
text = "#!/usr/bin/env python3\n\"\"\"Apply the Sony Android 12.1 tree's Android 16 compatibility adjustments.\"\"\"\nimport json\nimport os\nfrom pathlib import Path\n\nroot = Path(os.environ[\"BUILD_DIR\"])\ndevice = root / \"device/sony/pdx234\"\ncommon = root / \"device/sony/sm8550-common\"\n\n# Upstream's dependency points to a misspelled OnePlus repository. Both Sony\n# trees are explicitly supplied by the local manifest; roomservice must not\n# fetch that unrelated dependency.\n(device / \"twrp.dependencies\").write_text(json.dumps([{\n    \"remote\": \"sony-sm8550\",\n    \"repository\": \"device_sony_sm8550-common-TWRP\",\n    \"target_path\": \"device/sony/sm8550-common\",\n    \"branch\": \"android-12.1\",\n}], indent=2) + \"\\n\")\n\nproduct = device / \"twrp_pdx234.mk\"\ntext = product.read_text()\n# Avoid deriving the OEM from MAKEFILE_LIST under the newer product importer.\ntext = text.replace(\"BOARD_VENDOR := $(or $(word 2,$(subst /, ,$(firstword $(MAKEFILE_LIST)))),$(value 2))\",\n                    \"BOARD_VENDOR := sony\")\nproduct.write_text(text)\n\nconfig = common / \"BoardConfigCommon.mk\"\ntext = config.read_text().replace(\"BOARD_SYSTEMSDK_VERSIONS := 31\",\n                                  \"BOARD_SYSTEMSDK_VERSIONS := $(PLATFORM_SDK_VERSION)\")\nconfig.write_text(text)\nproduct_common = common / \"device-common.mk\"\ntext = product_common.read_text()\n# Android 16 removed the legacy standalone GSI key product. Recovery does\n# not build a GSI; retain this inheritance only for trees that provide it.\ntext = text.replace(\n    \"$(call inherit-product, $(SRC_TARGET_DIR)/product/gsi_keys.mk)\",\n    \"$(call inherit-product-if-exists, $(SRC_TARGET_DIR)/product/gsi_keys.mk)\")\n# Android 16 derives BOARD_API_LEVEL from its release configuration.\ntext = \"\\n\".join(line for line in text.splitlines()\n                 if not line.startswith(\"BOARD_API_LEVEL :=\")) + \"\\n\"\nproduct_common.write_text(text)\nprint(\"Adjusted Sony dependency, OEM identity, System SDK and legacy product configuration.\")\n"
path = Path(os.environ["GITHUB_WORKSPACE"]) / "scripts/prepare-device.py"
path.write_text(text)
PY
python3 "$GITHUB_WORKSPACE/scripts/prepare-device.py"
git -C "$BUILD_DIR/device/sony/pdx234" diff --check
git -C "$BUILD_DIR/device/sony/sm8550-common" diff --check
git -C "$BUILD_DIR/device/sony/sm8550-common" diff > "$ARTIFACT_DIR/sm8550-common.patch"
printf '%s\n' "Repair attempt 2: legacy GSI key inheritance and release-managed BOARD_API_LEVEL." >> "$ARTIFACT_DIR/build-info.txt"
df -h
