#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Stage the existing SL4A DKMS sources into a separate Linux kernel checkout.
# No automatic binding, kernel installation, or boot changes are made here.
set -euo pipefail

usage() {
    echo "Usage: $0 --check|--apply /path/to/clean/linux-kernel-source" >&2
    exit 2
}
[[ $# -eq 2 ]] || usage
mode=$1
[[ $mode == --check || $mode == --apply ]] || usage
kernel=$(realpath -e -- "$2") || usage
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
src="$repo/driver"

for path in Makefile Kconfig drivers/spi/Kconfig drivers/spi/Makefile drivers/hid/Kconfig drivers/hid/Makefile; do
    [[ -f "$kernel/$path" ]] || { echo "Missing kernel source file: $path" >&2; exit 1; }
done
[[ -f "$src/Kbuild" ]] || { echo "Missing SL4A Kbuild" >&2; exit 1; }
for name in spi-amd.c spi-amd.h spi-hid-core.c spi-hid-core.h spi-hid-capimg.c \
    spi-hid-capimg.h mshw0231-raw.c mshw0231-raw.h trace.c; do
    [[ -f "$src/$name" ]] || { echo "Missing SL4A source: $name" >&2; exit 1; }
done

# Refuse to work on a dirty tracked tree, or on an already-staged tree.
# This is intended for a *dedicated* kernel checkout, not a daily-driver tree.
[[ $(git -C "$kernel" rev-parse --show-toplevel 2>/dev/null) == "$kernel" ]] || {
    echo "Kernel source must be the root of a Git checkout." >&2; exit 1;
}
git -C "$kernel" diff --quiet -- || { echo "Kernel checkout has tracked modifications." >&2; exit 1; }
git -C "$kernel" diff --cached --quiet -- || { echo "Kernel checkout has staged modifications." >&2; exit 1; }
for path in drivers/spi/sl4a drivers/hid/sl4a; do
    [[ ! -e "$kernel/$path" ]] || { echo "Refusing to replace $path" >&2; exit 1; }
done
for entry in 'CONFIG_SL4A_AMD_SPI' 'CONFIG_SL4A_HID_SPI' 'drivers/spi/sl4a/Kconfig' 'drivers/hid/sl4a/Kconfig'; do
    if grep -Fq "$entry" "$kernel/drivers/spi/Kconfig" "$kernel/drivers/hid/Kconfig" "$kernel/drivers/spi/Makefile" "$kernel/drivers/hid/Makefile"; then
        echo "A SL4A integration marker already exists ($entry); refusing to duplicate it." >&2; exit 1
    fi
done

printf 'Kernel checkout: %s\nSL4A sources:    %s\n' "$kernel" "$src"
if [[ $mode == --check ]]; then
    echo "Preflight PASS; no files modified. Run --apply on this dedicated checkout to stage."
    exit 0
fi

mkdir -p "$kernel/drivers/spi/sl4a" "$kernel/drivers/hid/sl4a"
cp -- "$src/spi-amd.c" "$src/spi-amd.h" "$kernel/drivers/spi/sl4a/"
# Keep the local SPI header in the HID subtree: spi-hid-core.c includes it.
# It is a duplicate for the staging prototype and must be reconciled upstream.
cp -- "$src"/*.h "$kernel/drivers/hid/sl4a/"
for file in "$src"/*.c; do
    [[ ${file##*/} == spi-amd.c ]] && continue
    cp -- "$file" "$kernel/drivers/hid/sl4a/"
done

cat > "$kernel/drivers/spi/sl4a/Kconfig" <<'KCONFIG'
# SPDX-License-Identifier: GPL-2.0-only
config SL4A_AMD_SPI
    tristate "Experimental Surface Laptop AMD AMDI0060 SPI controller"
    depends on ACPI && SPI_MASTER && X86 && m
    help
      Prototype-only SPI controller for the Surface Laptop AMD touchscreen.
      Module-only: manual opt-in required. Do not enable on unknown hardware.
KCONFIG
cat > "$kernel/drivers/spi/sl4a/Makefile" <<'MAKEFILE'
# SPDX-License-Identifier: GPL-2.0
obj-$(CONFIG_SL4A_AMD_SPI) += sl4a-spi-amd.o
sl4a-spi-amd-y := spi-amd.o
MAKEFILE
cat > "$kernel/drivers/hid/sl4a/Kconfig" <<'KCONFIG'
# SPDX-License-Identifier: GPL-2.0-only
config SL4A_HID_SPI
    tristate "Experimental Surface Laptop AMD SPI touchscreen"
    depends on ACPI && SPI_MASTER && HID && INPUT && SL4A_AMD_SPI && m
    help
      Prototype-only HID-over-SPI V0 and Gate5 CapImg touchscreen driver.
      Module-only; the qualified module parameters must be supplied manually.
KCONFIG
cat > "$kernel/drivers/hid/sl4a/Makefile" <<'MAKEFILE'
# SPDX-License-Identifier: GPL-2.0
ccflags-y := -I$(src)
obj-$(CONFIG_SL4A_HID_SPI) += sl4a-spi-hid.o
sl4a-spi-hid-y := spi-hid-core.o spi-hid-capimg.o mshw0231-raw.o trace.o
MAKEFILE

cat >> "$kernel/drivers/spi/Kconfig" <<'KCONFIG'

# SL4A experimental in-tree prototype (not for upstream submission as-is)
source "drivers/spi/sl4a/Kconfig"
KCONFIG
cat >> "$kernel/drivers/spi/Makefile" <<'MAKEFILE'

# SL4A experimental in-tree prototype
obj-$(CONFIG_SL4A_AMD_SPI) += sl4a/
MAKEFILE
cat >> "$kernel/drivers/hid/Kconfig" <<'KCONFIG'

# SL4A experimental in-tree prototype (not for upstream submission as-is)
source "drivers/hid/sl4a/Kconfig"
KCONFIG
cat >> "$kernel/drivers/hid/Makefile" <<'MAKEFILE'

# SL4A experimental in-tree prototype
obj-$(CONFIG_SL4A_HID_SPI) += sl4a/
MAKEFILE

printf 'Staged source files and Kconfig/Makefile entries.\n'
printf 'No ACPI modalias, boot configuration, DKMS installation, or service was changed.\n'
printf 'Next: review git diff, configure both CONFIG_SL4A_* options =m, then build test kernel.\n'
