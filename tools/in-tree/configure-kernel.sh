#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Safe-by-default config for the experimental, explicitly loaded in-tree modules.
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: bash tools/in-tree/configure-kernel.sh /path/to/linux-source [working-kernel-config]" >&2
    exit 2
fi
kernel_root="$(realpath -- "$1")"
test -f "$kernel_root/drivers/staging/sl4a/Kconfig" || {
    echo "Run prepare-kernel.sh first" >&2
    exit 2
}
if [ "$#" -eq 2 ]; then
    cp -- "$2" "$kernel_root/.config"
else
    make -C "$kernel_root" x86_64_defconfig
fi

cfg="$kernel_root/.config"
"$kernel_root/scripts/config" --file "$cfg" \
    -e MODULES -e ACPI -e SPI -e HID -e INPUT -e STAGING \
    -d SPI_AMD \
    -e BLK_DEV_NVME -m DRM_AMDGPU -m HID_MULTITOUCH \
    -m AMD_PMC \
    -m SL4A_SPI_AMD -m SL4A_SPI_HID \
    --set-str LOCALVERSION "-sl4a-gate5"
make -C "$kernel_root" olddefconfig

# Failing closed is vital: the stock AMD SPI driver must not compete for
# AMDI0060 while the replacement platform driver is under investigation.
grep -qx 'CONFIG_SL4A_SPI_AMD=m' "$cfg"
grep -qx 'CONFIG_SL4A_SPI_HID=m' "$cfg"
grep -qx 'CONFIG_BLK_DEV_NVME=y' "$cfg"
grep -qx 'CONFIG_DRM_AMDGPU=m' "$cfg"
grep -qx 'CONFIG_HID_MULTITOUCH=m' "$cfg"
if grep -Eq '^CONFIG_SPI_AMD=[ym]' "$cfg"; then
    echo "FAIL: native CONFIG_SPI_AMD may compete with experimental controller" >&2
    exit 1
fi
printf 'Configured modules only (no ACPI auto-alias):\n'
grep -E '^(CONFIG_SL4A_SPI_AMD|CONFIG_SL4A_SPI_HID|CONFIG_LOCALVERSION)=' "$cfg"
printf 'NOTE: fallback x86_64_defconfig is a CI/build baseline, not a qualified Surface boot config.\n'