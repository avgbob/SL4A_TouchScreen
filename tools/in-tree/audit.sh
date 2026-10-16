#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Source-only preflight: does NOT touch actual hardware or installed kernels.
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$repo_root"

bash -n tools/in-tree/prepare-kernel.sh tools/in-tree/configure-kernel.sh \
    tools/in-tree/audit.sh tools/in-tree/source-selection.sh
source tools/in-tree/source-selection.sh
pr_root="$(sl4a_select_source "$repo_root" pr87)"
[[ "$pr_root" == "$repo_root/kernel-pins/pr87/driver" ]] || exit 1
legacy_root="$(sl4a_select_source "$repo_root" legacy-gate5)"
[[ "$legacy_root" == "$repo_root/driver" ]] || exit 1
test -f driver/Kbuild
for id in AMDI0060 MSHW0231 MSHW0162; do
    if ! grep -Fq "$id" "$pr_root/spi-amd.c" "$pr_root/spi-hid-core.c"; then
        echo "Missing expected hardware identity: $id" >&2
        exit 1
    fi
done
# Native ACPI auto-load is deliberately a separate, hardware-gated milestone.
if grep -Eq 'MODULE_DEVICE_TABLE[[:space:]]*\([[:space:]]*acpi' \
   "$pr_root/spi-amd.c" "$pr_root/spi-hid-core.c"; then
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
cmp "$pr_root/spi-hid-core.c" "$temp/linux/drivers/staging/sl4a/spi-hid-core.c"
cmp "$pr_root/mshw0231-raw.c" "$temp/linux/drivers/staging/sl4a/mshw0231-raw.c"
test "$(cat "$temp/linux/drivers/staging/sl4a/SOURCE-COMMIT")" = "18f0fe79623e6de4fdf1ae493f82a7048397386a"
test "$(cat "$temp/linux/drivers/staging/sl4a/SOURCE-FLAVOR")" = pr87
test -f "$temp/linux/drivers/staging/sl4a/INTEGRATION-COMMIT"
# Deliberately NOT mixing the old tracker algorithm into qualified PR87.
if cmp -s "$legacy_root/mshw0231-raw.c" "$temp/linux/drivers/staging/sl4a/mshw0231-raw.c"; then
    echo "ERROR: qualified PR87 tracker overwritten by legacy experiments" >&2
    exit 1
fi
grep -Fq 'obj-$(CONFIG_SL4A_SPI_HID)' "$temp/linux/drivers/staging/sl4a/Makefile"
grep -Fq 'source "drivers/staging/sl4a/Kconfig"' "$temp/linux/drivers/staging/Kconfig"
if bash tools/in-tree/prepare-kernel.sh "$temp/linux" > /dev/null 2>&1; then
    echo "ERROR: second integration attempt unexpectedly succeeded" >&2
    exit 1
fi
echo "PASS: exact PR87 C/H blob IDs, default source copy, ACPI alias guard, source provenance and repeat-run refusal"
echo "NOTE: this preflight does not establish a successful Linux kernel compile."