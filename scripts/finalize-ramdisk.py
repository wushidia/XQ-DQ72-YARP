#!/usr/bin/env python3
"""Restore the recovery-specific HIDL manager before final packaging."""
import os
import shutil
from pathlib import Path

build = Path(os.environ["BUILD_DIR"])
module = build / "out/soong/.intermediates/bootable/recovery/etc/hwservicemanager.recovery"
variants = [path for path in module.rglob("hwservicemanager")
            if path.is_file() and path.parent.name.startswith("android_recovery_")
            and path.read_bytes()[18:20] == b"\xb7\x00"
            and b"VintfObjectRecovery" in path.read_bytes()]
if not variants or len({path.read_bytes() for path in variants}) != 1:
    raise RuntimeError("Recovery HIDL manager module is absent or ambiguous")
destination = build / "out/target/product/pdx234/recovery" / "root" / "system/bin/hwservicemanager"
destination.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(variants[0], destination)
print("Restored the recovery-specific HIDL manager.")
