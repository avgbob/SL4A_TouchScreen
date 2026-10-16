#!/usr/bin/env bash
# MSHW0231 ONLY. Load a locally built mode-4 module without changing DKMS
# installation or the permanent Gate5 modprobe configuration.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODULE="$ROOT/driver/sl4a-spi-hid.ko"
SYS=/sys/module/sl4a_spi_hid/parameters/std_raw_transition
STATS=/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats
KDIR="/lib/modules/$(uname -r)/build"

as_root() {
    if (( EUID == 0 )); then "$@"; else sudo "$@"; fi
}
require_device() {
    [[ -d /sys/bus/acpi/devices/MSHW0231:00 ]] || {
        echo "ERROR: no MSHW0231:00 ACPI panel; refusing mode 4" >&2
        exit 1
    }
}
secure_boot_on() {
    command -v mokutil >/dev/null 2>&1 &&
        mokutil --sb-state 2>/dev/null | grep -qi 'SecureBoot enabled'
}
show_status() {
    printf 'Installed boot profile: '
    grep '^options sl4a_spi_hid' /etc/modprobe.d/sl4a-spi-hid.conf || true
    printf 'Live mode: '
    if [[ -r "$SYS" ]]; then cat "$SYS"; else echo 'not loaded'; fi
    if [[ -r "$STATS" ]]; then cat "$STATS"; fi
}
prepare() {
    require_device
    [[ -f "$KDIR/Makefile" ]] || {
        echo "ERROR: kernel headers missing for $(uname -r)" >&2; exit 1;
    }
    [[ -r "$ROOT/driver/spi-hid-core.c" ]] || exit 1
    grep -q 'std_host56_mshw0231' "$ROOT/driver/spi-hid-core.c" || {
        echo "ERROR: checkout does not contain mode 4" >&2; exit 1;
    }
    make -C "$KDIR" M="$ROOT/driver" modules
    [[ -s "$MODULE" ]] || { echo "ERROR: build has no HID .ko" >&2; exit 1; }
    if secure_boot_on; then
        local cert=/var/lib/shim-signed/mok/MOK.der
        local key=/var/lib/shim-signed/mok/MOK.priv
        [[ -s "$cert" && -s "$key" && -x "$KDIR/scripts/sign-file" ]] || {
            echo "ERROR: enrolled Ubuntu MOK signing files unavailable. Driver untouched." >&2
            exit 1
        }
        # The Ubuntu MOK directory can be root-only. A plain mokutil call
        # therefore reports failure to read the certificate even when that
        # exact certificate is enrolled and signs the production DKMS module.
        # Verify with the same privileges used to sign, and preserve the
        # underlying output if trust verification genuinely fails.
        local mok_test_output
        # mokutil's exit status varies across versions; its reported
        # enrollment state is the trust decision (same as the DKMS installer).
        mok_test_output="$(as_root mokutil --test-key "$cert" 2>&1 || true)"
        if ! grep -qi 'already enrolled' <<<"$mok_test_output"; then
            echo "ERROR: Ubuntu signing key is not enrolled:" >&2
            echo "$mok_test_output" >&2
            exit 1
        fi
        as_root "$KDIR/scripts/sign-file" sha256 "$key" "$cert" "$MODULE"
    fi
    [[ "$(modinfo -F vermagic "$MODULE" | awk '{print $1}')" == "$(uname -r)" ]] || {
        echo "ERROR: built module vermagic does not match running kernel" >&2; exit 1;
    }
    if secure_boot_on; then
        [[ -n "$(modinfo -F signer "$MODULE")" ]] || {
            echo "ERROR: unsigned module; driver untouched." >&2; exit 1;
        }
    fi
    echo "Prepared transient module; original DKMS module and boot profile unchanged."
    modinfo -F signer "$MODULE"
    sha256sum "$MODULE"
}
activate() {
    require_device
    [[ -s "$MODULE" ]] || { echo "Run: $0 prepare" >&2; exit 1; }
    [[ "$(modinfo -F vermagic "$MODULE" | awk '{print $1}')" == "$(uname -r)" ]] || {
        echo "Wrong kernel module; run prepare again" >&2; exit 1;
    }
    if secure_boot_on && [[ -z "$(modinfo -F signer "$MODULE")" ]]; then
        echo "Module is unsigned under Secure Boot. Run prepare." >&2; exit 1
    fi
    if [[ -r "$SYS" && "$(cat "$SYS")" == 4 ]]; then
        echo "Mode 4 already loaded"; exit 0
    fi
    echo "Unloading HID module only; AMD controller stays bound."
    as_root modprobe -r sl4a-spi-hid
    if ! as_root insmod "$MODULE" \
        raw_mode=N raw_input_beta=Y wire_double_opcode=1 \
        gate3_observe_only=1 skip_std_getfeat=1 \
        std_raw_transition=4 get_noread=0 getfeat_delay_ms=0 \
        std_liveness_ms=0 std_liveness_recover=0 wait_reset_kick_ms=0
    then
        echo "Mode 4 insertion failed. Restoring installed Gate5 module..." >&2
        as_root modprobe sl4a-spi-hid || {
            echo "WARNING: Gate5 reload failed. REBOOT to restore." >&2; exit 1;
        }
        exit 1
    fi
    sleep 3
    [[ "$(cat "$SYS")" == 4 ]] || {
        echo "ERROR: mode 4 not active; restoring Gate5" >&2
        restore
        exit 1
    }
    echo "Temporary mode 4 active. Reboot or run '$0 restore' for Gate5."
    show_status
}
restore() {
    as_root modprobe -r sl4a-spi-hid
    as_root modprobe sl4a-spi-hid
    sleep 3
    echo "Restored installed DKMS module from unchanged Gate5 configuration:"
    show_status
}
capture() {
    require_device
    local protocol="${1:-quick}"
    case "$protocol" in quick|pinch|contacts|full|stylus) ;; *)
        echo "ERROR: protocol must be quick, pinch, contacts, full, or stylus" >&2
        exit 2 ;; esac
    [[ -r "$SYS" && "$(cat "$SYS")" == 4 ]] || {
        echo "ERROR: guided mode4 capture requires experimental mode 4 active" >&2
        exit 1
    }
    local run_id="mode4-${protocol}-$(date -u +%Y%m%dT%H%M%SZ)"
    local output="${HOME}/sl4a-hardware-runs/${run_id}"
    echo "Audibly guided test, timestamped cue markers, evtest and sysfs evidence."
    echo "Evidence destination: $output"
    python3 "$ROOT/tools/hardware_evidence/guided_session.py" \
        --protocol "$protocol" --case "$run_id" --period p1 --output "$output"
}

case "${1:-}" in
    prepare) prepare ;;
    activate) activate ;;
    restore) restore ;;
    capture) capture "${2:-quick}" ;;
    audio-check) python3 "$ROOT/tools/hardware_evidence/guided_session.py" --audio-check ;;
    status) show_status ;;
    *) echo "Usage: $0 {prepare|activate|audio-check|capture [quick|pinch|contacts|full|stylus]|status|restore}" >&2; exit 2 ;;
esac
