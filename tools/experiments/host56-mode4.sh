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
        --protocol "$protocol" --case "$run_id" --period p1 \
        --expected-mode 4 --output "$output"
}

# One-command hardware session: return to the installed Gate5 profile on
# success, failure, or interruption. Never alter the persistent boot options.
qualify() {
    local protocol="${1:-full}"
    case "$protocol" in quick|full|contacts) ;; *)
        echo "ERROR: qualify accepts quick, contacts, or full only" >&2
        return 2 ;; esac
    require_device
    if [[ ! -r "$SYS" || "$(cat "$SYS")" != 1 ]]; then
        echo "ERROR: qualify must start from the working Gate5 mode 1." >&2
        echo "Restore the installed driver before qualifying a new module." >&2
        return 1
    fi
    prepare
    (
        trap 'restore' EXIT
        trap 'exit 130' INT
        trap 'exit 143' TERM
        activate
        capture "$protocol"
    )
}

# Three distinct warm activations of the exact SAME signed mode4 binary.
# Each activation receives its own short spoken quick session and immutable
# evidence folder; Gate5 is restored between cycles and on any failure.
# Does not request suspend, restart or change the installed DKMS/boot profile.
qualify_warm_three() {
    require_device
    [[ -r "$SYS" && "$(cat "$SYS")" == 1 ]] || {
        echo "ERROR: warm qualification requires working Gate5 mode 1 at entry." >&2
        return 1
    }
    prepare  # Build/sign ONCE; subsequent cycles reuse identical module.
    (
        trap 'restore' EXIT
        trap 'exit 130' INT
        trap 'exit 143' TERM
        local cycle
        for cycle in 1 2 3; do
            [[ -r "$SYS" && "$(cat "$SYS")" == 1 ]] || {
                echo "ERROR: baseline Gate5 missing before warm cycle $cycle" >&2
                exit 1
            }
            echo "=== WARM ACTIVATION $cycle OF 3: same module SHA256 ==="
            sha256sum "$MODULE"
            activate
            # Every session requires a confirmed spoken preflight and verifies
            # actual CapImg + MT events, reset deltas and zero dropped frames.
            capture quick
            restore
            [[ -r "$SYS" && "$(cat "$SYS")" == 1 ]] || {
                echo "ERROR: Gate5 restoration failed after cycle $cycle" >&2
                exit 1
            }
            echo "=== WARM CYCLE $cycle/3 PASSED; GATE5 RESTORED ==="
        done
        trap - EXIT
        echo "WARM 3/3: all short spoken captures passed; Gate5 mode 1 restored."
    )
}


# Suspend/resume test: both platform s2idle transitions occur with one
# transient mode4 module left loaded. This is intentionally NOT a
# module-reload test, and does not change /etc/modprobe.d or installed DKMS.
qualify_s2idle_two() {
    require_device
    [[ -r "$SYS" && "$(cat "$SYS")" == 1 ]] || {
        echo "ERROR: s2idle qualification requires installed Gate5 mode 1 at entry" >&2
        return 1
    }
    [[ -r /sys/power/mem_sleep ]] || {
        echo "ERROR: kernel mem_sleep policy unavailable" >&2; return 1;
    }
    local sleep_mode
    sleep_mode="$(cat /sys/power/mem_sleep)"
    [[ "$sleep_mode" == *'[s2idle]'* ]] || {
        echo "ERROR: actual configured sleep state is NOT s2idle: $sleep_mode" >&2
        echo "Will not change platform suspend policy automatically." >&2
        return 1
    }
    command -v systemctl >/dev/null || {
        echo "ERROR: systemctl unavailable; not touching the driver." >&2; return 1;
    }
    prepare
    local root_log="$HOME/sl4a-hardware-runs"
    local session="$root_log/mode4-s2idle2-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$session"
    {
        echo "source_commit=$(git -C "$ROOT" rev-parse HEAD)"
        echo "signed_module_sha256=$(sha256sum "$MODULE" | cut -d' ' -f1)"
        echo "kernel=$(uname -r)"
        echo "mode_before=1"
        echo "mem_sleep_at_start=$sleep_mode"
        echo "test_type=s2idle2_postresume_audio_quick"
    } > "$session/provenance.txt"
    printf 'verdict=INCOMPLETE\nreason=not_all_cycles_passed\n' > "$session/qualification-status.txt"
    echo "=== S2IDLE QUALIFICATION; EVIDENCE $session ==="
    (
        trap 'restore' EXIT
        trap 'exit 130' INT
        trap 'exit 143' TERM
        activate
        local cycle before after journal_since
        for cycle in 1 2; do
            [[ -r "$SYS" && "$(cat "$SYS")" == 4 ]] || {
                echo "ERROR: mode4 missing before s2idle cycle $cycle" >&2
                exit 1
            }
            [[ "$(cat /sys/power/mem_sleep)" == *'[s2idle]'* ]] || {
                echo "ERROR: s2idle ceased to be active" >&2; exit 1
            }
            sha256sum "$MODULE" | tee "$session/driver-before-$cycle.sha256"
            cat "$STATS" > "$session/stats-before-$cycle.txt"
            python3 "$ROOT/tools/hardware_evidence/speak_operator.py" \
                "Sleep test $cycle of 2. The laptop will suspend. Wake it with the power button or keyboard. Unlock the screen if needed. Your touchscreen will be tested with spoken instructions after waking."
            printf 'Type YES to initiate actual s2idle suspend cycle %s/2: ' "$cycle"
            local confirm
            IFS= read -r confirm
            [[ "$confirm" == "YES" || "$confirm" == "yes" ]] || {
                echo "S2IDLE CANCELLED, preserving Gate5 rollback" >&2
                exit 1
            }
            # Explicit sudo prompt before sleep; never ask during touch.
            as_root true
            if (( EUID != 0 )); then sudo -v; fi
            journal_since="$(date '+%Y-%m-%d %H:%M:%S')"
            printf '%s\n' "$journal_since" > "$session/journal-since-$cycle.txt"
            before="$session/clock-before-$cycle.json"
            after="$session/clock-after-$cycle.json"
            python3 "$ROOT/tools/hardware_evidence/s2idle_clock.py" \
                --snapshot "$before"
            echo "=== ENTERING REAL S2IDLE CYCLE $cycle/2 ==="
            as_root systemctl suspend
            # CRITICAL: systemctl may return after queueing the suspend
            # request, *before* the machine has actually gone to sleep.
            # The old immediate snapshot falsely read 0.000s, restored
            # Gate5 and finished BEFORE any post-wake voice prompt.
            # Wait for the actual sleep clock gap, or fail closed.
            echo "=== SUSPEND REQUESTED; WAITING FOR VERIFIED WAKE ==="
            if ! python3 "$ROOT/tools/hardware_evidence/s2idle_clock.py" \
                --wait-after "$before" "$after" --timeout-seconds 75 \
                    | tee "$session/clock-verdict-$cycle.txt"; then
                as_root journalctl -k -b --since "$journal_since" --no-pager \
                    > "$session/kernel-resume-$cycle.log" || true
                python3 "$ROOT/tools/hardware_evidence/speak_operator.py" \
                    "The system could not verify the sleep interval. The test is stopping. The working touchscreen driver will be restored." \
                    || true
                echo "ERROR: real suspend/resume unproven. Saved kernel log." >&2
                exit 1
            fi
            sleep 2
            [[ -r "$SYS" && "$(cat "$SYS")" == 4 ]] || {
                echo "ERROR: mode4 did not survive s2idle cycle $cycle" >&2
                exit 1
            }
            [[ "$(sha256sum "$MODULE" | cut -d' ' -f1)" == \
               "$(cut -d' ' -f1 < "$session/driver-before-$cycle.sha256")" ]] || {
                echo "ERROR: signed module file changed during suspend cycle $cycle" >&2
                exit 1
            }
            cat "$STATS" > "$session/stats-after-resume-$cycle.txt"
            # Capture actual PM entry/exit records; do not accept a no-op
            # systemctl suspend as successful physical S0ix/s2idle testing.
            as_root journalctl -k -b --since "$journal_since" --no-pager \
                > "$session/kernel-resume-$cycle.log"
            grep -q 'PM: suspend entry (s2idle)' \
                "$session/kernel-resume-$cycle.log" || {
                echo "ERROR: missing kernel s2idle entry marker for cycle $cycle" >&2
                exit 1
            }
            grep -q 'PM: suspend exit' \
                "$session/kernel-resume-$cycle.log" || {
                echo "ERROR: missing kernel suspend-exit marker for cycle $cycle" >&2
                exit 1
            }
            # The desktop audio sink may reconnect only after login/unlock.
            # Do not continue until the operator confirms the POST-WAKE
            # voice was actually HEARD. This never counts terminal text
            # or a successful paplay exit as proof of audible instructions.
            python3 "$ROOT/tools/hardware_evidence/speak_operator.py" \
                --confirm --retries 5 \
                "Laptop awake after suspend cycle $cycle. Unlock the screen if necessary. This is the spoken post-wake checkpoint. Type YES in the terminal only if you heard this message. Next is the one-finger movement and two-finger pinch test."
            echo "=== POST-S2IDLE TOUCH VALIDATION $cycle/2 ==="
            capture quick | tee "$session/capture-$cycle.log"
            cat "$STATS" > "$session/stats-after-touch-$cycle.txt"
            echo "=== S2IDLE CYCLE $cycle/2 PASSED ==="
        done
        restore
        [[ -r "$SYS" && "$(cat "$SYS")" == 1 ]] || {
            echo "ERROR: installed Gate5 did not return after second resume" >&2
            exit 1
        }
        echo "mode_after=1" >> "$session/provenance.txt"
        printf 'verdict=PASS\ncompleted_cycles=2\n' > "$session/qualification-status.txt"
        ( cd "$session"; sha256sum ./*.txt ./*.json ./*.log ./*.sha256 > SHA256SUMS.txt )
        ( cd "$session"; sha256sum -c SHA256SUMS.txt )
        trap - EXIT
        echo "S2IDLE 2/2: actual sleep detected, PM markers recorded, post-wake gesture checks passed, Gate5 restored."
        echo "S2IDLE EVIDENCE: $session"
    )
}


# True cold start: unlike warm "activate", boot's normal late activation
# service substitutes the signed mode4 HID module only ONCE. No DKMS rewrite.
# User must shut down completely and physically power on to qualify cold.
coldboot_stage() {
    require_device
    [[ -r "$SYS" && "$(cat "$SYS")" == 1 ]] || {
        echo "ERROR: working Gate5 mode1 must be loaded before staging." >&2
        return 1
    }
    echo "This temporarily adds ONE root-owned systemd ExecStart drop-in."
    echo "It does NOT edit your production Gate5 modprobe profile or DKMS."
    echo "The boot hook deletes itself BEFORE first HID initialization."
    echo "A separate 20-minute systemd timer restores Gate5 if no test finishes."
    echo "A forced REBOOT after consumption returns to original Gate5."
    echo "This only qualifies a physical POWER-OFF then POWER-ON, not reboot."
    printf 'Type ARM to build/sign and stage the one-use cold-boot hook: '
    local confirm
    IFS= read -r confirm
    [[ "$confirm" == ARM ]] || {
        echo "CANCELLED; no changes to boot." >&2; return 1
    }
    prepare
    as_root bash "$ROOT/tools/experiments/host56-mode4-coldboot-once.sh" \
        stage "$MODULE" "$(git -C "$ROOT" rev-parse HEAD)"
}

coldboot_finish() {
    local hook=/usr/local/libexec/sl4a-mode4-coldboot-once
    [[ -x "$hook" ]] || {
        echo "ERROR: coldboot not staged or helper missing" >&2; return 1
    }
    if ! "$hook" verify; then
        echo "Cold-boot identity is unqualified; requesting safe rollback." >&2
        as_root "$hook" rollback || true
        return 1
    fi
    printf 'Was the laptop fully powered OFF and then powered ON? Type COLD: '
    local confirm
    IFS= read -r confirm
    [[ "$confirm" == COLD ]] || {
        echo "Not claiming cold boot. Restore Gate5 or let watchdog run." >&2
        as_root "$hook" finish FAIL || true
        return 1
    }
    # Reuse the same spoken preflight + real evdev quick gate as warm/s2idle.
    # On any ordinary capture failure we still perform immediate Gate5
    # rollback. A killed shell or hung process has a separate timer.
    if capture quick; then
        as_root "$hook" finish PASS
        echo "COLD-BOOT ACCEPTANCE: one first mode4 HID activation, gestures PASS, Gate5 RESTORED."
    else
        as_root "$hook" finish FAIL || true
        echo "COLD-BOOT INCONCLUSIVE/FAIL; original Gate5 recovery attempted." >&2
        return 1
    fi
}

case "${1:-}" in
    qualify) qualify "${2:-full}" ;;
    qualify-warm3) qualify_warm_three ;;
    qualify-s2idle2) qualify_s2idle_two ;;
    coldboot-stage) coldboot_stage ;;
    coldboot-finish) coldboot_finish ;;
    coldboot-status) /usr/local/libexec/sl4a-mode4-coldboot-once verify ;;
    coldboot-cancel) as_root /usr/local/libexec/sl4a-mode4-coldboot-once cancel ;;
    prepare) prepare ;;
    activate) activate ;;
    restore) restore ;;
    capture) capture "${2:-quick}" ;;
    audio-check) python3 "$ROOT/tools/hardware_evidence/guided_session.py" --audio-check ;;
    status) show_status ;;
    *) echo "Usage: $0 {qualify [quick|contacts|full]|qualify-warm3|qualify-s2idle2|coldboot-stage|coldboot-finish|coldboot-status|coldboot-cancel|prepare|activate|audio-check|capture [quick|pinch|contacts|full|stylus]|status|restore}" >&2; exit 2 ;;
esac
