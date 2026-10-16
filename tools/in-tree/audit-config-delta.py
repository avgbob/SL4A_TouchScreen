#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Read-only comparison of installed Surface kernel config vs new build config."""
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("Usage: python3 tools/in-tree/audit-config-delta.py /boot/config-WORKING /path/to/linux/.config")
old_path, candidate_path = (Path(arg).resolve() for arg in sys.argv[1:])
for path in (old_path, candidate_path):
    if not path.is_file():
        raise SystemExit(f"STOP missing kernel config: {path}")


def parse(path):
    pairs = {}
    for line in path.read_text().splitlines():
        match = re.match(r"^(CONFIG_[A-Z0-9_]+)=(.*)$", line)
        if match:
            pairs[match[1]] = match[2]
        else:
            match = re.match(r"^# (CONFIG_[A-Z0-9_]+) is not set$", line)
            if match:
                pairs[match[1]] = "n"
    return pairs


old, new = parse(old_path), parse(candidate_path)
errors, warnings = [], []
def stop(note):
    errors.append(note)


def warn(note):
    warnings.append(note)


required = {
    "CONFIG_64BIT", "CONFIG_X86_64", "CONFIG_EFI", "CONFIG_EFI_STUB",
    "CONFIG_ACPI", "CONFIG_PCI", "CONFIG_MODULES", "CONFIG_SPI",
    "CONFIG_HID", "CONFIG_INPUT", "CONFIG_FW_LOADER", "CONFIG_BLK_DEV_NVME",
}
for key in sorted(required):
    val = new.get(key, "n")
    if val not in ("y", "m"):
        stop(f"boot/core support missing: {key}={val}")
if new.get("CONFIG_BLK_DEV_NVME") != "y":
    stop("NVMe must be built in for current experiment, not module")
for key in ("CONFIG_SL4A_SPI_AMD", "CONFIG_SL4A_SPI_HID"):
    if new.get(key) != "m":
        stop(f"native touchscreen module missing: {key}={new.get(key)}")
if new.get("CONFIG_SPI_AMD", "n") != "n":
    stop("stock SPI_AMD enabled; controller binding conflict")
if new.get("CONFIG_LOCALVERSION") != '"-sl4a-pr87"':
    stop("experimental kernel release label changed")
# List deliberate boot/driver downgrade risks. This set is intentionally
# biased toward false positive WARNs rather than pretending a config is safe.
sensitive = re.compile(
    r"^CONFIG_(?:EFI|ACPI|PCI|BLK|NVME|SCSI|ATA|EXT4|BTRFS|XFS|F2FS|"
    r"VFAT|FAT|USB|HID|INPUT|I2C|SPI|DRM|AMD|PINCTRL|GPIO|FW_|MODULE_|"
    r"PM|SUSPEND|HIBERNATION|WIFI|WLAN|CFG80211|RFKILL|SND|SOUND|"
    r"CRYPTO|SECURITY|DEVTMPFS|INITRAMFS|OVERLAY_FS|FUSE_FS)"
)
dropped = [
    key for key, value in old.items()
    if value in ("y", "m") and new.get(key, "n") == "n"
    and key != "CONFIG_SPI_AMD"
]
sensitive_dropped = sorted(key for key in dropped if sensitive.match(key))
for key in sensitive_dropped:
    warn(f"working-kernel feature absent/disabled: {key} (was {old[key]})")
if dropped:
    warn(f"{len(dropped)} total formerly enabled config symbols not enabled in new kernel "
         "(can include kernel-version renames; require review)")
for key in ("CONFIG_SYSTEM_TRUSTED_KEYS", "CONFIG_SYSTEM_REVOCATION_KEYS",
            "CONFIG_MODULE_SIG_KEY"):
    v = new.get(key, "")
    if v.startswith('"') and v.endswith('"'):
        v = v[1:-1]
    if v and v != "certs/signing_key.pem":
        target = Path(v)
        if not target.is_absolute():
            target = candidate_path.parent / target
        if not target.exists():
            stop(f"{key} references nonexistent build key/cert: {v}; "
                 "do not silently disable trust")
for key in ("CONFIG_MODULE_SIG_FORCE", "CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY",
            "CONFIG_LOCK_DOWN_KERNEL_FORCE_CONFIDENTIALITY"):
    if old.get(key) == "y" and new.get(key) != "y":
        warn(f"kernel security enforcement dropped: {key}")
print(f"WORKING CONFIG: {old_path}")
print(f"NEW CONFIG: {candidate_path}")
print(f"Changed formerly enabled symbols: {len(dropped)}; "
      f"potential hardware/security impacts: {len(sensitive_dropped)}")
for note in errors:
    print(f"STOP: {note}")
for note in warnings[:45]:
    print(f"WARN: {note}")
if len(warnings) > 45:
    print(f"WARN: {len(warnings)-45} more warnings (inspect config diff)")
print(f"RESULT: {'NO-GO' if errors or sensitive_dropped else 'REVIEW'} "
      f"({len(errors)} hard stops, {len(warnings)} warnings)")
# Comparison alone can never certify firmware, signing, module precedence,
# or an actual boot; missing sensitive hardware support must fail closed.
sys.exit(1 if errors or sensitive_dropped else 0)
