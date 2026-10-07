#!/usr/bin/env python3
"""Verify the Sony recovery image and its packaged ARM64 GUI2 executable."""
import os
import struct
import subprocess
from pathlib import Path

root = Path(os.environ["ARTIFACT_DIR"])
image = root / "recovery.img"
with image.open("rb") as stream:
    header = stream.read(4096)
    assert header[:8] == b"ANDROID!", "Recovery image lacks Android boot magic"
    kernel_size, ramdisk_size = struct.unpack_from("<II", header, 8)
    header_size = struct.unpack_from("<I", header, 20)[0]
    header_version = struct.unpack_from("<I", header, 40)[0]
    assert header_version == 4, f"Unexpected recovery header version {header_version}"
    assert header_size == 1584, f"Unexpected v4 header size {header_size}"
    assert kernel_size == 0, "Sony's dedicated recovery must exclude the kernel"
    assert ramdisk_size > 0, "Recovery ramdisk is empty"
    assert image.stat().st_size <= 104857600, "Image exceeds the recovery partition"
    ramdisk_offset = 4096 + ((kernel_size + 4095) // 4096) * 4096
    assert ramdisk_offset + ramdisk_size <= image.stat().st_size, "Truncated ramdisk"
    stream.seek(ramdisk_offset)
    compressed = stream.read(ramdisk_size)

cpio = subprocess.check_output(["lz4", "-d", "-c"], input=compressed)
entries = {}
offset = 0
while offset + 110 <= len(cpio):
    header = cpio[offset:offset + 110]
    assert header[:6] in (b"070701", b"070702"), f"Invalid cpio header at {offset}"
    values = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
    file_size, name_size = values[6], values[11]
    name_start = offset + 110
    name_end = name_start + name_size
    assert name_end <= len(cpio) and cpio[name_end - 1] == 0, "Truncated cpio name"
    name = cpio[name_start:name_end - 1].decode()
    if name == "TRAILER!!!":
        break
    content_start = (name_end + 3) & ~3
    content_end = content_start + file_size
    assert content_end <= len(cpio), f"Truncated cpio file: {name}"
    entries[name.removeprefix("./")] = memoryview(cpio)[content_start:content_end]
    offset = (content_end + 3) & ~3
else:
    raise AssertionError("Recovery ramdisk lacks a cpio trailer")

candidates = [(name, data) for name, data in entries.items()
              if name.rsplit("/", 1)[-1] == "recovery" and bytes(data[:4]) == b"\x7fELF"]
assert candidates, "Ramdisk lacks the recovery ELF executable"
binary_name, payload = candidates[0]
binary = bytes(payload)
assert binary[4:6] == b"\x02\x01", "Recovery executable must be 64-bit little-endian ELF"
assert struct.unpack_from("<H", binary, 18)[0] == 183, "Recovery executable must target AArch64"
assert b"gui2: invalid framebuffer" in binary, "GUI2 display implementation is absent"
# Verify the actual archive, including libraries loaded by recovery. Checking
# only an intermediate executable missed stale ramdisk shared objects before.
assert b"YARP final build: final-logging-v1" in binary, "Wrong recovery build"
assert b"Decrypt input selection" in binary, "Manual credential input is absent"
minui = bytes(entries["system/lib64/libtwrpminui.so"])
assert b"Haptics sysfs backend" in minui, "Stale minui lacks Sony haptics fallback"
expected_minui = Path(os.environ["BUILD_DIR"]) / "out/target/product/pdx234/system/lib64/libtwrpminui.so"
assert minui == expected_minui.read_bytes(), "Packaged minui differs from the newly built module"
assert b"VintfObjectRecovery" in bytes(entries["system/bin/hwservicemanager"]), "HIDL manager lacks recovery manifest support"
services = bytes(entries["init.recovery.yarp-services.rc"])
assert b"service keymint-qti" in services and b"service qseecomd" in services
assert b"/init.recovery.yarp-services.rc" in bytes(entries["init.recovery.qcom.rc"])
assert b"service keystore2 /system/bin/keystore2 /tmp/misc/keystore" in services
assert "system/bin/android.hardware.vibrator-sony.service.cs40l25" in entries
assert b"final-logging-v1" in bytes(entries["system/etc/yarp-build-id"])

logger = bytes(entries["system/bin/yarp_bootlog"])
expected_logger = Path(os.environ["BUILD_DIR"]) / "out/target/product/pdx234/obj/EXECUTABLES/yarp_bootlog_intermediates/yarp_bootlog"
assert logger == expected_logger.read_bytes(), "Packaged logger differs from the newly built module"
# Clang may fold the short settings-key comparison into immediate constants.
assert b"twrp.yarp.logging" in logger and b"/tmp/yarp-bootlog-persist" in logger, "Logger lacks early policy"
assert b"twrp.yarp.logging_active" in logger, "Logger lacks pause acknowledgement"
assert b"tw_metadata_logging" in binary, "Recovery lacks persistent logging control"

flags = bytes(entries["system/etc/twrp.flags"])
assert b"/dev/block/mmcblk1p1" in flags and b"/dev/block/mmcblk0p1" not in flags, "Wrong SD device"
persist = next(line for line in flags.splitlines() if line.startswith(b"/mnt/vendor/persist "))
assert b"fsflags=ro" not in persist, "Settings persist remains read-only"
assert b"/mnt/vendor/persist" in bytes(entries["system/etc/recovery.fstab"]), "Wrong persist mount"
assert b"USB storage enable failed; keeping mount page" in binary, "Missing UMS failure handling"
assert b"Refusing settings I/O" in binary, "Missing persistent mount guard"
usb = bytes(entries["init.recovery.usb.rc"])
assert b"sys.usb.config=mass_storage,adb && property:sys.usb.configfs=1" in usb, "Missing configfs UMS"
assert b"mass_storage.0 /config/usb_gadget/g1/configs/b.1/f1" in usb, "Missing UMS gadget function"

fstabs = [name for name, data in entries.items()
          if name.rsplit("/", 1)[-1] == "recovery.fstab" and len(data) > 0]
assert fstabs, "Recovery fstab is absent"
report = (f"Android recovery header version: {header_version}\n"
          f"Header size: {header_size}\nKernel size: {kernel_size}\n"
          f"Ramdisk size: {ramdisk_size}\nImage size: {image.stat().st_size}\n"
          "Recovery partition limit: 104857600\n"
          f"Recovery executable: {binary_name} (AArch64 ELF64)\n"
          f"Recovery fstab: {', '.join(fstabs)}\n"
          "GUI2 display implementation: present\n"
          f"Ramdisk archive entries: {len(entries)}\n")
(root / "recovery-header.txt").write_text(report)
print(report)
