#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Offline inspection only: never install, sign, load modules, or alter boot.
set -Eeuo pipefail
if [[ $# -ne 1 || ! -d "$1" ]]; then
    echo "Usage: bash tools/in-tree/audit-packages.sh /path/to/extracted-action-artifact" >&2
    exit 2
fi
out="$(realpath -e -- "$1")"
error() { echo "PACKAGE AUDIT FAIL: $*" >&2; exit 1; }
say() { printf 'AUDIT: %s\n' "$*"; }
pin=18f0fe79623e6de4fdf1ae493f82a7048397386a
release=6.18.57-sl4a-pr87
for name in kernel.config source-commit.txt source-flavor.txt integration-commit.txt \
            pinned-driver-blobs.txt READ-BEFORE-TESTING.txt SHA256SUMS.txt; do
    [[ -s "$out/$name" ]] || error "missing/empty $name"
done
[[ "$(cat "$out/source-commit.txt")" == "$pin" ]] || error "wrong pinned driver commit"
[[ "$(cat "$out/source-flavor.txt")" == pr87 ]] || error "wrong source flavor"
[[ "$(cat "$out/integration-commit.txt")" =~ ^[0-9a-f]{40}$ ]] ||
    error "invalid integration commit identity"
[[ "$(git hash-object -- "$out/pinned-driver-blobs.txt")" == 5b51fbd0596eeb4dddee76a3e899cd2ce7fc045e ]] ||
    error "source blob manifest differs from known qualified PR87"
(
    cd "$out"
    sha256sum -c SHA256SUMS.txt
) || error "one or more package/config/evidence checksums are wrong"
cfg="$out/kernel.config"
for setting in 'CONFIG_MODULES=y' 'CONFIG_SL4A_SPI_AMD=m' \
               'CONFIG_SL4A_SPI_HID=m' 'CONFIG_LOCALVERSION="-sl4a-pr87"' \
               'CONFIG_BLK_DEV_NVME=y'; do
    grep -qxF "$setting" "$cfg" || error "kernel config missing $setting"
done
grep -Eq '^CONFIG_SPI_AMD=[ym]$' "$cfg" &&
    error "stock AMD SPI controller still enabled; competing owner"
shopt -s nullglob
images=("$out"/linux-image-*.deb)
headers=("$out"/linux-headers-*.deb)
[[ ${#images[@]} -eq 1 ]] || error "expected exactly one linux-image package; got ${#images[@]}"
[[ ${#headers[@]} -ge 1 ]] || error "missing native kernel header package"
image="${images[0]}"
pkg="$(dpkg-deb --field "$image" Package)"
[[ "$pkg" == linux-image-"$release" ||
   "$pkg" == linux-image-unsigned-"$release" ]] ||
    error "unexpected kernel image package identity: $pkg"
arch="$(dpkg-deb --field "$image" Architecture)"
[[ "$arch" == amd64 ]] || error "kernel package architecture is $arch, not amd64"
# Header package release and architecture must match the image.
for hdr in "${headers[@]}"; do
    hname="$(dpkg-deb --field "$hdr" Package)"
    [[ "$hname" == linux-headers-"$release" ]] ||
        error "unexpected headers package: $hname"
    [[ "$(dpkg-deb --field "$hdr" Architecture)" == amd64 ]] ||
        error "headers architecture != amd64"
done
contents="$(dpkg-deb --contents "$image")"
[[ "$contents" == *"./boot/vmlinuz-$release"* ]] ||
    error "missing exact boot image inside Debian package"
work="$(mktemp -d)"
trap 'rm -rf -- "$work"' EXIT
for name in sl4a-spi-amd sl4a-spi-hid; do
    matches="$(printf '%s\n' "$contents" | awk '{print $NF}' |
        grep -E "^\\./(usr/)?lib/modules/$release/kernel/drivers/staging/sl4a/$name[.]ko$" || true)"
    [[ "$(printf '%s\n' "$matches" | grep -c . || true)" == 1 ]] ||
        error "not exactly one packaged native $name.ko under $release"
    path="$matches"
    dpkg-deb --fsys-tarfile "$image" | tar -xOf - "$path" > "$work/$name.ko" ||
        error "could not extract packaged $name.ko"
    [[ -s "$work/$name.ko" ]] || error "packaged $name module is empty"
    magic="$(modinfo -F vermagic "$work/$name.ko")" ||
        error "invalid ELF/module metadata in $name"
    [[ "$magic" == "$release "* ]] ||
        error "$name vermagic does not start with $release: $magic"
    if modinfo -F alias "$work/$name.ko" | grep -Eq '^acpi:'; then
        error "$name unexpectedly auto-loads via an ACPI alias"
    fi
    say "packaged $name: path=$path; vermagic=$magic; srcversion=$(modinfo -F srcversion "$work/$name.ko")"
done
say "kernel image/headers architecture: amd64"
say "kernel release: $release"
say "signed-kernel/boot-chain verification: NOT DONE (CI does not sign kernel)"
say "Surface-specific boot config validation: NOT DONE (CI uses generic defconfig)"
say "existing host DKMS/unit conflicts: NOT DONE (requires live Surface inventory)"
say "PASS: checksummed artifacts, source pin, configuration, Debian contents and exact native module metadata"
