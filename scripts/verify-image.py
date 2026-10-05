#!/usr/bin/env python3
import os
import struct
from pathlib import Path

root = Path(os.environ["ARTIFACT_DIR"])
image = root / "recovery.img"
with image.open("rb") as stream:
    header = stream.read(4096)
assert header[:8] == b"ANDROID!", "Recovery image lacks the Android boot magic"
kernel_size, ramdisk_size = struct.unpack_from("<II", header, 8)
header_size = struct.unpack_from("<I", header, 20)[0]
header_version = struct.unpack_from("<I", header, 40)[0]
assert header_version == 4, f"Unexpected recovery header version {header_version}"
assert header_size == 1584, f"Unexpected v4 header size {header_size}"
assert ramdisk_size > 0, "Recovery ramdisk is empty"
assert image.stat().st_size <= 104857600, "Image exceeds the recovery partition"
ramdisk_offset = 4096 + ((kernel_size + 4095) // 4096) * 4096
assert ramdisk_offset + ramdisk_size <= image.stat().st_size, "Truncated ramdisk"
report = (f"Android recovery header version: {header_version}\n"
          f"Header size: {header_size}\nKernel size: {kernel_size}\n"
          f"Ramdisk size: {ramdisk_size}\nImage size: {image.stat().st_size}\n"
          "Recovery partition limit: 104857600\n")
(root / "recovery-header.txt").write_text(report)
print(report)
