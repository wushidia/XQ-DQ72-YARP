#!/usr/bin/env python3
"""Apply the Sony Android 12.1 tree's Android 16 compatibility adjustments."""
import json
import os
from pathlib import Path

root = Path(os.environ["BUILD_DIR"])
device = root / "device/sony/pdx234"
common = root / "device/sony/sm8550-common"

# Upstream's dependency points to a misspelled OnePlus repository. Both Sony
# trees are explicitly supplied by the local manifest; roomservice must not
# fetch that unrelated dependency.
(device / "twrp.dependencies").write_text(json.dumps([{
    "remote": "sony-sm8550",
    "repository": "device_sony_sm8550-common-TWRP",
    "target_path": "device/sony/sm8550-common",
    "branch": "android-12.1",
}], indent=2) + "\n")

product = device / "twrp_pdx234.mk"
text = product.read_text()
# Avoid deriving the OEM from MAKEFILE_LIST under the newer product importer.
text = text.replace("BOARD_VENDOR := $(or $(word 2,$(subst /, ,$(firstword $(MAKEFILE_LIST)))),$(value 2))",
                    "BOARD_VENDOR := sony")
product.write_text(text)

config = common / "BoardConfigCommon.mk"
text = config.read_text().replace("BOARD_SYSTEMSDK_VERSIONS := 31",
                                  "BOARD_SYSTEMSDK_VERSIONS := $(PLATFORM_SDK_VERSION)")
config.write_text(text)
print("Adjusted Sony dependency, OEM identity and System SDK selection.")
