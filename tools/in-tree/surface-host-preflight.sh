#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
# Pure read-only preflight: no sudo, no installation, no signing, no modprobe.
set -Eeuo pipefail
if [[ $# -ne 0 ]]; then
    echo "Usage: bash tools/in-tree/surface-host-preflight.sh" >&2
    exit 2
fi
warnings=0
stops=0
note() { printf 'CHECK: %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*"; warnings=$((warnings+1)); }
stop() { printf 'STOP: %s\n' "$*"; stops=$((stops+1)); }
printf 'SL4A native kernel pre-install inventory (NO CHANGES)\n'
note "Running kernel: $(uname -r); architecture: $(uname -m)"
[[ "$(uname -m)" == x86_64 ]] || stop "requires an x86_64 Surface"
bootcfg="/boot/config-$(uname -r)"
if [[ -r "$bootcfg" ]]; then
    note "Running kernel config available: $bootcfg"
    for key in CONFIG_ACPI CONFIG_EFI CONFIG_EFI_STUB CONFIG_BLK_DEV_NVME \
               CONFIG_MODULES CONFIG_SPI CONFIG_HID CONFIG_INPUT; do
        val="$(grep -E "^$key=" "$bootcfg" || true)"
        [[ -n "$val" ]] && note "$val" || warn "running config lacks readable $key setting"
    done
else
    stop "cannot read $bootcfg; cannot prepare a Surface-specific kernel"
fi
if [[ -d /sys/firmware/efi ]]; then
    note "Boot mode: UEFI"
else
    stop "UEFI boot not detected; do not assume standard Surface boot plan"
fi
if command -v mokutil >/dev/null 2>&1; then
    state="$(mokutil --sb-state 2>&1 || true)"
    note "Secure Boot: $state"
    if grep -qi 'enabled' <<<"$state"; then
        stop "Secure Boot enabled: unsigned experimental image cannot be booted safely; a separately verified kernel/image signing plan is mandatory"
    elif ! grep -qi 'disabled' <<<"$state"; then
        warn "Secure Boot state not conclusively determined"
    fi
else
    warn "mokutil unavailable: cannot check Secure Boot"
fi
for id in AMDI0060 MSHW0231 MSHW0162; do
    count=0
    for dev in /sys/bus/acpi/devices/"$id":*; do
        [[ -e "$dev" ]] && count=$((count+1))
    done
    note "ACPI $id instances=$count"
    if [[ "$id" == AMDI0060 || "$id" == MSHW0231 ]]; then
        ((count>0)) || stop "expected ACPI $id missing"
    fi
done
for path in /sys/bus/platform/devices/AMDI0060:*/driver \
            /sys/bus/acpi/devices/MSHW0231:00/physical_node/driver; do
    for candidate in $path; do
        [[ -L "$candidate" ]] && note "binding: $candidate -> $(basename "$(readlink -f "$candidate")")"
    done
done
for name in sl4a-spi-amd sl4a-spi-hid spi-amd; do
    if command -v modinfo >/dev/null 2>&1; then
        found="$(modinfo -n "$name" 2>/dev/null || true)"
        [[ -z "$found" ]] && note "installed $name: unavailable" ||
            note "installed $name: $found"
    fi
done
for file in /sys/module/sl4a_spi_hid/srcversion \
            /sys/module/sl4a_spi_hid/parameters/std_raw_transition \
            /sys/module/sl4a_spi_hid/parameters/raw_input_beta; do
    [[ -r "$file" ]] && note "loaded $file: $(cat "$file")"
done
if command -v systemctl >/dev/null 2>&1; then
    for service in sl4a-touch-activate.service \
                   sl4a-pr87-coldboot-rollback.service \
                   sl4a-mode4-coldboot-rollback.service; do
        fragment="$(systemctl show "$service" --property=FragmentPath --value 2>/dev/null || true)"
        active="$(systemctl is-active "$service" 2>/dev/null || true)"
        if [[ -n "$fragment" ]]; then
            note "service $service: path=$fragment active=$active"
            if [[ "$service" == sl4a-touch-activate.service ]]; then
                warn "existing activation service requires isolation/disable IN THE TEST KERNEL ONLY; do not alter working Gate5 now"
            fi
        fi
    done
    for drop in /etc/systemd/system/sl4a-touch-activate.service.d/*.conf; do
        [[ -f "$drop" ]] && warn "activation service drop-in exists: $drop"
    done
fi
bootkernels=(/boot/vmlinuz-*)
count=0
for file in "${bootkernels[@]}"; do [[ -f "$file" ]] && count=$((count+1)); done
note "existing /boot kernel images: $count"
(( count >= 2 )) || warn "fewer than two existing boot images: verify a known-good boot fallback"
for path in /boot /boot/efi /; do
    if mountpoint -q "$path"; then
        note "filesystem at $path: $(df -hP "$path" | tail -n 1 | awk '{print $4 " available"}')"
    fi
done
if command -v dkms >/dev/null 2>&1; then
    note "DKMS installed: yes"
    warn "DKMS may rebuild sl4a-touch against the new kernel and override native module paths"
fi
printf '\nInventory totals: STOP=%s WARN=%s\n' "$stops" "$warnings"
printf 'No command in this script has installed, loaded, unloaded, signed, or changed anything.\n'
printf 'To proceed to a test-boot plan, resolve EVERY STOP; WARN needs documented review.\n'
((stops == 0))
