#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Read-only host inventory; no root privileges or system changes required.
set -euo pipefail
printf 'Kernel: %s\n' "$(uname -r)"
printf 'Architecture: %s\n' "$(uname -m)"
for id in AMDI0060 MSHW0231 MSHW0230 MSHW0162; do
    count=0
    for dev in /sys/bus/acpi/devices/"$id":*; do
        [[ -e "$dev" ]] && ((count += 1)) || :
    done
    printf 'ACPI %-8s: %d instance(s)\n' "$id" "$count"
done
printf '\nInstalled modules:\n'
for module in sl4a-spi-amd sl4a-spi-hid spi-amd; do
    if command -v modinfo >/dev/null 2>&1; then
        printf '%-18s ' "$module"
        modinfo -n "$module" 2>/dev/null || echo 'not installed'
    fi
done
printf '\nLoaded relevant modules:\n'
if command -v lsmod >/dev/null 2>&1; then
    lsmod | grep -E '(^sl4a|^spi_amd)' || :
fi
printf '\nSecure Boot:\n'
if command -v mokutil >/dev/null 2>&1; then
    mokutil --sb-state 2>/dev/null || :
else
    echo 'mokutil unavailable'
fi
printf '\nRead-only inventory complete; no driver was loaded or changed.\n'
