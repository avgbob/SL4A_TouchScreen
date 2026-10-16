#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# No real kernel, device, DKMS, or boot operations. Fail-closed PR source pin.
set -Eeuo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
source "$repo/tools/in-tree/source-selection.sh"
exact="$repo/kernel-pins/pr87/driver"
[[ "$(sl4a_select_source "$repo" pr87)" == "$exact" ]]
[[ "$(sl4a_select_source "$repo" legacy-gate5)" == "$repo/driver" ]]
if sl4a_select_source "$repo" arbitrary >/dev/null 2>&1; then
    echo "FAIL: arbitrary source variant accepted" >&2; exit 1
fi
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp/kernel-pins/pr87"
cp -a "$repo/kernel-pins/pr87/driver" "$tmp/kernel-pins/pr87/"
cp -- "$repo/kernel-pins/pr87/DRIVER-BLOBS.txt" "$tmp/kernel-pins/pr87/"
cp -- "$repo/kernel-pins/pr87/SOURCE-COMMIT" "$tmp/kernel-pins/pr87/"
[[ "$(sl4a_select_source "$tmp" pr87)" == "$tmp/kernel-pins/pr87/driver" ]]
printf '\n/* corruption negative control */\n' >> "$tmp/kernel-pins/pr87/driver/spi-hid-core.c"
if sl4a_select_source "$tmp" pr87 >/dev/null 2>&1; then
    echo "FAIL: altered production handler passed source pin" >&2; exit 1
fi
cp -- "$repo/kernel-pins/pr87/driver/spi-hid-core.c" "$tmp/kernel-pins/pr87/driver/spi-hid-core.c"
printf '# synthetic manifest change\n' >> "$tmp/kernel-pins/pr87/DRIVER-BLOBS.txt"
if sl4a_select_source "$tmp" pr87 >/dev/null 2>&1; then
    echo "FAIL: altered pin manifest passed" >&2; exit 1
fi
cp -- "$repo/kernel-pins/pr87/DRIVER-BLOBS.txt" "$tmp/kernel-pins/pr87/DRIVER-BLOBS.txt"
printf 'not-the-real-upstream-commit\n' > "$tmp/kernel-pins/pr87/SOURCE-COMMIT"
if sl4a_select_source "$tmp" pr87 >/dev/null 2>&1; then
    echo "FAIL: incorrect source revision passed" >&2; exit 1
fi
cp -- "$repo/kernel-pins/pr87/SOURCE-COMMIT" "$tmp/kernel-pins/pr87/SOURCE-COMMIT"
rm -- "$tmp/kernel-pins/pr87/driver/mshw0231-raw.c"
if sl4a_select_source "$tmp" pr87 >/dev/null 2>&1; then
    echo "FAIL: missing tracker source passed" >&2; exit 1
fi
echo "PASS: default PR87, explicit legacy, tampered source, altered manifest, wrong revision, missing tracker"
