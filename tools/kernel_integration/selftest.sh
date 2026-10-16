#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Exercise staging against a disposable, minimal Git kernel-tree fixture.
set -euo pipefail
script=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/stage-in-tree.sh
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
kernel="$work/linux"
mkdir -p "$kernel/drivers/spi" "$kernel/drivers/hid"
printf 'VERSION = 7\n' > "$kernel/Makefile"
printf 'mainmenu "fixture"\n' > "$kernel/Kconfig"
printf 'menu "SPI"\nendmenu\n' > "$kernel/drivers/spi/Kconfig"
printf 'menu "HID"\nendmenu\n' > "$kernel/drivers/hid/Kconfig"
printf 'obj-y += spi-core.o\n' > "$kernel/drivers/spi/Makefile"
printf 'obj-y += hid-core.o\n' > "$kernel/drivers/hid/Makefile"
git -C "$kernel" init -q
git -C "$kernel" -c user.name='SL4A selftest' -c user.email='none@example.invalid' add .
git -C "$kernel" -c user.name='SL4A selftest' -c user.email='none@example.invalid' commit -qm fixture
bash "$script" --check "$kernel"
test ! -e "$kernel/drivers/hid/sl4a"
bash "$script" --apply "$kernel"
git -C "$kernel" diff --check
test -f "$kernel/drivers/hid/sl4a/spi-hid-core.c"
test -f "$kernel/drivers/hid/sl4a/spi-amd.h"
test -f "$kernel/drivers/spi/sl4a/spi-amd.c"
test "$(cat "$kernel/drivers/hid/sl4a/SOURCE-COMMIT")" = "18f0fe79623e6de4fdf1ae493f82a7048397386a"
test "$(cat "$kernel/drivers/hid/sl4a/SOURCE-FLAVOR")" = pr87
cmp "$(dirname "$script")/../../kernel-pins/pr87/driver/spi-hid-core.c" \
    "$kernel/drivers/hid/sl4a/spi-hid-core.c"
cmp "$(dirname "$script")/../../kernel-pins/pr87/driver/spi-amd.c" \
    "$kernel/drivers/spi/sl4a/spi-amd.c"
grep -q '^config SL4A_HID_SPI$' "$kernel/drivers/hid/sl4a/Kconfig"
grep -q '^config SL4A_AMD_SPI$' "$kernel/drivers/spi/sl4a/Kconfig"
if bash "$script" --apply "$kernel" >/dev/null 2>&1; then
    echo 'FAIL: repeated staging was not blocked' >&2
    exit 1
fi
# When a built kernel header tree is supplied, compile the staged layouts too.
# This uses external-module Kbuild as a smoke check, NOT a full in-tree build.
if [[ -n "${SL4A_BUILD_KDIR:-}" ]]; then
    [[ -f "$SL4A_BUILD_KDIR/Makefile" ]] || {
        echo "SL4A_BUILD_KDIR is not a kernel header build directory" >&2
        exit 1
    }
    make -C "$SL4A_BUILD_KDIR" M="$kernel/drivers/spi/sl4a" CONFIG_SL4A_AMD_SPI=m modules
    make -C "$SL4A_BUILD_KDIR" M="$kernel/drivers/hid/sl4a" CONFIG_SL4A_HID_SPI=m modules
    test -s "$kernel/drivers/spi/sl4a/sl4a-spi-amd.ko"
    test -s "$kernel/drivers/hid/sl4a/sl4a-spi-hid.ko"
    printf 'PASS: staged SPI and HID modules compiled against %s\n' "$SL4A_BUILD_KDIR"
fi
printf 'PASS: preflight, source copy, Kconfig, whitespace, and duplicate protection\n'
