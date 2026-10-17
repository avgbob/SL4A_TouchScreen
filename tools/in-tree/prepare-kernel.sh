#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Experimental, reversible copy of SL4A sources into an extracted kernel tree.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: bash tools/in-tree/prepare-kernel.sh /path/to/linux-source" >&2
    exit 2
fi
repo_root="$(cd "$(dirname "$0")/../.." && pwd)"
source "$repo_root/tools/in-tree/source-selection.sh"
driver_root="$(sl4a_select_source "$repo_root" "${SL4A_IN_TREE_SOURCE:-pr87}")"
source_flavor="${SL4A_IN_TREE_SOURCE:-pr87}"
kernel_root="$(realpath -- "$1")"
dest="$kernel_root/drivers/staging/sl4a"

if [ ! -f "$kernel_root/Makefile" ] || [ ! -f "$kernel_root/drivers/staging/Kconfig" ] || [ ! -f "$kernel_root/drivers/staging/Makefile" ]; then
    echo "Target must be an extracted Linux source tree with drivers/staging" >&2
    exit 2
fi
if [ -e "$dest" ] ||
   grep -Fq 'source "drivers/staging/sl4a/Kconfig"' "$kernel_root/drivers/staging/Kconfig" ||
   grep -Fq 'sl4a/' "$kernel_root/drivers/staging/Makefile"; then
    echo "SL4A integration already exists; refusing to overwrite the kernel tree" >&2
    exit 2
fi

mkdir -p "$dest"
cp -- "$driver_root"/*.c "$driver_root"/*.h "$dest/"
cat > "$dest/Makefile" <<'KBUILD'
# Experimental in-tree modules. Keep the two drivers distinct.
ccflags-y += -I$(src)
obj-$(CONFIG_SL4A_SPI_AMD) += sl4a-spi-amd.o
sl4a-spi-amd-y := spi-amd.o
obj-$(CONFIG_SL4A_SPI_HID) += sl4a-spi-hid.o
sl4a-spi-hid-y := spi-hid-core.o spi-hid-capimg.o mshw0231-raw.o trace.o
KBUILD
cat > "$dest/Kconfig" <<'KCONFIG'
# SPDX-License-Identifier: GPL-2.0
config SL4A_SPI_AMD
    tristate "Experimental Surface Laptop AMD AMDI0060 SPI controller"
    depends on STAGING && ACPI && SPI && X86
    help
      Build the experimental Surface Laptop AMD SPI V2 controller driver.
      This is not intended for generic AMD SPI hosts. Select M for testing.
      The driver deliberately lacks a MODULE_DEVICE_TABLE ACPI alias, so
      it will not auto-load merely because AMDI0060 is present.

config SL4A_SPI_HID
    tristate "Experimental Surface Laptop AMD HID-over-SPI touchscreen"
    depends on SL4A_SPI_AMD && HID && INPUT && ACPI
    help
      Build the experimental Surface Laptop AMD touchscreen driver.
      Only enable on hardware documented by SL4A. Select M for testing.
      Hardware activation remains explicitly opt-in.
KCONFIG
printf '\nsource "drivers/staging/sl4a/Kconfig"\n' >> "$kernel_root/drivers/staging/Kconfig"
printf '\nobj-$(CONFIG_SL4A_SPI_AMD) += sl4a/\n' >> "$kernel_root/drivers/staging/Makefile"

if [[ "$source_flavor" == pr87 ]]; then
    cat "$repo_root/kernel-pins/pr87/SOURCE-COMMIT" > "$dest/SOURCE-COMMIT"
else
    git -C "$repo_root" rev-parse HEAD > "$dest/SOURCE-COMMIT"
fi
printf '%s\n' "$source_flavor" > "$dest/SOURCE-FLAVOR"
git -C "$repo_root" rev-parse HEAD > "$dest/INTEGRATION-COMMIT"
printf 'Prepared experimental in-tree sources at %s\n' "$dest"
printf 'Source flavor: %s\n' "$source_flavor"
printf 'Driver source commit: %s\n' "$(cat "$dest/SOURCE-COMMIT")"
printf 'Integration commit: %s\n' "$(cat "$dest/INTEGRATION-COMMIT")"
printf 'ACPI auto-load intentionally disabled; compile modules and test explicitly.\n'