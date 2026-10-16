#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Source-only preflight: does NOT touch actual hardware or installed kernels.
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

bash -n tools/in-tree/prepare-kernel.sh tools/in-tree/configure-kernel.sh tools/in-tree/audit.sh
test -f driver/Kbuild
for id in AMDI0060 MSHW0231 MSHW0162; do
    if ! grep -Fq "$id" driver/spi-amd.c driver/spi-hid-core.c; then
        echo "Missing expected hardware identity: $id" >&2
        exit 1
    fi
done
# Native ACPI auto-load is deliberately a separate, hardware-gated milestone.
if grep -Eq 'MODULE_DEVICE_TABLE[[:space:]]*\([[:space:]]*acpi' driver/spi-amd.c driver/spi-hid-core.c; then
    echo "Automatic ACPI module alias was introduced unexpectedly" >&2
    exit 1
fi

temp="$(mktemp -d)"
trap 'rm -rf -- "$temp"' EXIT
mkdir -p "$temp/linux/drivers/staging"
printf 'VERSION = 6\n' > "$temp/linux/Makefile"
printf 'menu "Staging"\nendmenu\n' > "$temp/linux/drivers/staging/Kconfig"
printf '# staging Makefile\n' > "$temp/linux/drivers/staging/Makefile"

bash tools/in-tree/prepare-kernel.sh "$temp/linux"
test -f "$temp/linux/drivers/staging/sl4a/spi-hid-core.c"
test -f "$temp/linux/drivers/staging/sl4a/spi-amd.c"
test -f "$temp/linux/drivers/staging/sl4a/mshw0231-raw.c"
grep -Fq 'obj-$(CONFIG_SL4A_SPI_HID)' "$temp/linux/drivers/staging/sl4a/Makefile"
grep -Fq 'source "drivers/staging/sl4a/Kconfig"' "$temp/linux/drivers/staging/Kconfig"
if bash tools/in-tree/prepare-kernel.sh "$temp/linux" > /dev/null 2>&1; then
    echo "ERROR: second integration attempt unexpectedly succeeded" >&2
    exit 1
fi
echo "PASS: source audit, ACPI alias guard, staging integration, repeat-run refusal"
echo "NOTE: this preflight does not establish a successful Linux kernel compile."