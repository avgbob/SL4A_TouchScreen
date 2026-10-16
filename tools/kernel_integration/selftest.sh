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
grep -q '^config SL4A_HID_SPI$' "$kernel/drivers/hid/sl4a/Kconfig"
grep -q '^config SL4A_AMD_SPI$' "$kernel/drivers/spi/sl4a/Kconfig"
if bash "$script" --apply "$kernel" >/dev/null 2>&1; then
    echo 'FAIL: repeated staging was not blocked' >&2
    exit 1
fi
printf 'PASS: preflight, source copy, Kconfig, whitespace, and duplicate protection\n'
