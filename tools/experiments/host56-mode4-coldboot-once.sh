#!/usr/bin/env bash
# One-shot MSHW0231 cold-start, late-boot, unchanged DKMS/MOK/Gate5 config.
# Intentionally NEVER intercepts early kernel/ACPI module auto-probing.
set -Eeuo pipefail
umask 022
BASE=/var/lib/sl4a-mode4-coldboot
HELPER=/usr/local/libexec/sl4a-mode4-coldboot-once
UNIT=sl4a-touch-activate.service
OVERRIDE=/etc/systemd/system/sl4a-touch-activate.service.d/90-mode4-once.conf
MODE=/sys/module/sl4a_spi_hid/parameters/std_raw_transition
STATS=/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats
BOOT_ID=/proc/sys/kernel/random/boot_id

readfile() { [[ -r "$1" ]] && cat "$1" || true; }
current_boot() { cat "$BOOT_ID"; }
mode() { readfile "$MODE"; }
field() { readfile "$BASE/$1"; }
write_state() { printf '%s\n' "$2" > "$BASE/$1"; }
note() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$BASE/events.log"; }
require_root() { (( EUID == 0 )) || { echo "Root required" >&2; exit 1; }; }
unhook() {
    if [[ -e "$OVERRIDE" ]]; then
        rm -f -- "$OVERRIDE"
        systemctl daemon-reload || true
    fi
}
fallback() {
    # Never unload an already running production driver during recovery.
    if [[ -z "$(mode)" ]]; then
        modprobe sl4a-spi-hid || note "ERROR could not load installed Gate5"
    fi
}
cancel_timer() { systemctl stop sl4a-mode4-coldboot-rollback.timer >/dev/null 2>&1 || true; }
stage() {
    require_root
    local module="$1" source_sha="$2" tmp
    # Ubuntu typically points /boot/vmlinuz at the newest installed
    # kernel. If that differs from the running kernel, an update may be
    # pending and a first cold boot will refuse our signed binary.
    # Fail closed rather than stage a one-use override that cannot run.
    local boot_image boot_target boot_kernel
    boot_image=""
    for boot_target in /boot/vmlinuz /vmlinuz; do
        if [[ -L "$boot_target" ]]; then
            boot_image="$boot_target"
            break
        fi
    done
    if [[ -n "$boot_image" ]]; then
        boot_target="$(readlink -f "$boot_image")"
        boot_kernel="${boot_target##*/vmlinuz-}"
        if [[ "$boot_target" == */vmlinuz-* &&
              "$boot_kernel" != "$(uname -r)" ]]; then
            echo "REFUSE staging: running kernel=$(uname -r), boot default symlink target=$boot_kernel" >&2
            echo "A kernel update may take effect on next power-on. Boot into the intended kernel first." >&2
            exit 1
        fi
    fi
    [[ "$module" == /* && -s "$module" ]] || { echo "Signed module missing" >&2; exit 1; }
    [[ -d /sys/bus/acpi/devices/MSHW0231:00 ]] || { echo "MSHW0231 absent" >&2; exit 1; }
    [[ "$(mode)" == 1 ]] || { echo "Working Gate5 mode1 required" >&2; exit 1; }
    grep -q 'std_raw_transition=1' /etc/modprobe.d/sl4a-spi-hid.conf || {
        echo "Persistent Gate5 profile not recognized" >&2; exit 1;
    }
    [[ "$(systemctl is-enabled "$UNIT")" == enabled ]] || {
        echo "Normal boot activation service not enabled" >&2; exit 1;
    }
    [[ "$(systemctl show -P FragmentPath "$UNIT")" == /etc/systemd/system/sl4a-touch-activate.service ]] || {
        echo "Unknown startup service; refusing to override" >&2; exit 1;
    }
    [[ -z "$(systemctl show -P DropInPaths "$UNIT")" ]] || {
        echo "Competing systemd drop-ins present; refusing" >&2; exit 1;
    }
    systemctl cat "$UNIT" | grep -q 'sl4a-touch.sh.*activate' || {
        echo "Unexpected boot activation command; refusing" >&2; exit 1;
    }
    command -v systemd-run >/dev/null || { echo "No independent rollback timer" >&2; exit 1; }
    [[ "$(modinfo -F vermagic "$module" | awk '{print $1}')" == "$(uname -r)" ]] || {
        echo "Signed module built for wrong kernel" >&2; exit 1;
    }
    [[ -n "$(modinfo -F signer "$module")" &&
       -n "$(modinfo -F srcversion "$module")" ]] || {
        echo "Unsigned/unidentifiable module" >&2; exit 1;
    }
    [[ ! -e "$OVERRIDE" && ! -e "$BASE/armed" ]] || {
        echo "One-shot already staged; cancel first" >&2; exit 1;
    }
    # Preserve each previous trial's immutable evidence on restaging.
    if [[ -d "$BASE" ]]; then
        local archive
        archive="$BASE-archive-$(date -u +%Y%m%dT%H%M%SZ)-$"
        mv "$BASE" "$archive"
        echo "Prior trial preserved at $archive"
    fi
    install -d -m 0755 "$BASE" /usr/local/libexec "$(dirname "$OVERRIDE")"
    install -m 0755 "$0" "$HELPER"
    install -m 0644 "$module" "$BASE/signed-mode4.ko"
    write_state source_sha "$source_sha"
    write_state stage_boot_id "$(current_boot)"
    write_state kernel "$(uname -r)"
    write_state module_sha "$(sha256sum "$BASE/signed-mode4.ko" | awk '{print $1}')"
    write_state srcversion "$(modinfo -F srcversion "$BASE/signed-mode4.ko")"
    write_state stage_epoch "$(date +%s)"
    write_state result "ARMED_NOT_TESTED"
    note "STAGE one-use boot hook; original DKMS/profile untouched"
    tmp="$(mktemp "$(dirname "$OVERRIDE")/.sl4a-mode4.XXXXXX")"
    printf '[Service]\nExecStart=\nExecStart=%s boot\n' "$HELPER" > "$tmp"
    chmod 0644 "$tmp"
    mv -f "$tmp" "$OVERRIDE"
    touch "$BASE/armed"
    systemctl daemon-reload
    if ! systemctl cat "$UNIT" | grep -Fq "$HELPER boot"; then
        unhook; rm -f "$BASE/armed"
        echo "Systemd rejected new one-shot hook; cancelled" >&2; return 1
    fi
    note "ARMED for one future DIFFERENT boot; power off physically"
    echo "STAGED. Fully power OFF: sudo systemctl poweroff"
    echo "After pressing power button and logging in:"
    echo "  bash tools/experiments/host56-mode4.sh coldboot-finish"
}
boot() {
    require_root
    [[ -d "$BASE" ]] || { fallback; return 0; }
    if [[ ! -e "$BASE/armed" ]]; then unhook; fallback; return 0; fi
    if [[ "$(field stage_boot_id)" == "$(current_boot)" ]]; then
        note "REFUSE manual service restart in staging boot; keep trial armed"
        fallback; return 0
    fi
    # Consume BEFORE any experimental loading. Subsequent reboot = Gate5.
    rm -f "$BASE/armed"
    unhook
    write_state trial_boot_id "$(current_boot)"
    write_state result "INCOMPLETE"
    note "BOOT one-shot consumed on new boot $(current_boot)"
    # Separate kernel mismatch from expiration; preserve an actionable
    # verdict instead of silently leaving result=INCOMPLETE.
    local staged_kernel live_kernel stage_epoch_now now_epoch stage_age
    staged_kernel="$(field kernel)"
    live_kernel="$(uname -r)"
    stage_epoch_now="$(field stage_epoch)"
    now_epoch="$(date +%s)"
    if [[ "$staged_kernel" != "$live_kernel" ]]; then
        write_state result "INCONCLUSIVE_KERNEL_MISMATCH"
        note "ERROR KERNEL_MISMATCH staged=$staged_kernel booted=$live_kernel; module not inserted"
        fallback; return 1
    fi
    if [[ ! "$stage_epoch_now" =~ ^[0-9]+$ ]]; then
        write_state result "INCONCLUSIVE_BAD_STAGE_EPOCH"
        note "ERROR invalid or missing staging timestamp; module not inserted"
        fallback; return 1
    fi
    stage_age=$((now_epoch - stage_epoch_now))
    if (( stage_age < 0 || stage_age > 86400 )); then
        write_state result "INCONCLUSIVE_STAGING_EXPIRED"
        note "ERROR STAGE_AGE_SECONDS=$stage_age not in 0..86400; module not inserted"
        fallback; return 1
    fi
    if [[ -d /sys/module/sl4a_spi_hid ]]; then
        note "INCONCLUSIVE: HID module already loaded before late boot hook"
        write_state result "INCONCLUSIVE_PREEXISTING_HID"
        return 0
    fi
    # Also reject an HID module that loaded and UNLOADED earlier in this
    # boot. Merely testing /sys/module at this instant is insufficient
    # to prove this is truly the first HID initialization since power-on.
    if ! journalctl -k -b --no-pager > "$BASE/boot-before-hid.log"; then
        note "ERROR cannot check prior kernel HID probes"; fallback; return 1
    fi
    if grep -Eq 'sl4a_spi_hid.*probe begin|input: MSHW0231 Touchscreen' \
            "$BASE/boot-before-hid.log"; then
        note "INCONCLUSIVE: earlier HID probe already appears in kernel journal"
        write_state result "INCONCLUSIVE_EARLIER_HID_PROBE"
        return 0
    fi
    if [[ "$(sha256sum "$BASE/signed-mode4.ko" | awk '{print $1}')" != "$(field module_sha)" ]]; then
        note "ERROR signed copy changed"; fallback; return 1
    fi
    # Independent timed systemd recovery, armed BEFORE experimental insert.
    if ! systemd-run --unit=sl4a-mode4-coldboot-rollback --on-active=20m \
         "$HELPER" rollback >/dev/null; then
        note "ERROR cannot arm 20-minute Gate5 rollback"; fallback; return 1
    fi
    note "WATCHDOG 20min armed"
    if ! modprobe sl4a-spi-amd; then
        note "ERROR AMD controller load"; fallback; cancel_timer; return 1
    fi
    if ! journalctl -k -b --no-pager > "$BASE/boot-after-amd.log"; then
        note "ERROR cannot check AMD-phase HID probes"
        write_state result "INCONCLUSIVE_JOURNAL_UNAVAILABLE"
        fallback; cancel_timer; return 1
    fi
    if [[ -d /sys/module/sl4a_spi_hid ]] ||
       grep -Eq 'sl4a_spi_hid.*probe begin|input: MSHW0231 Touchscreen' \
           "$BASE/boot-after-amd.log"; then
        note "INCONCLUSIVE: HID initialized during AMD controller setup"
        write_state result "INCONCLUSIVE_HID_AUTOLOADED"
        cancel_timer; return 0
    fi
    if ! insmod "$BASE/signed-mode4.ko" \
        raw_mode=N raw_input_beta=Y wire_double_opcode=1 \
        gate3_observe_only=1 skip_std_getfeat=1 \
        std_raw_transition=4 get_noread=0 getfeat_delay_ms=0 \
        std_liveness_ms=0 std_liveness_recover=0 wait_reset_kick_ms=0; then
        note "ERROR mode4 first load; falling back to installed Gate5"
        write_state result "FAIL_INSERT"
        fallback; cancel_timer; return 1
    fi
    sleep 3
    if [[ "$(mode)" != 4 ]] ||
       [[ "$(readfile /sys/module/sl4a_spi_hid/srcversion)" != "$(field srcversion)" ]]; then
        note "ERROR new driver profile/identity mismatch"
        write_state result "FAIL_IDENTITY"
        rollback
        return 1
    fi
    cat "$STATS" > "$BASE/stats-boot.txt" || true
    write_state result "ACTIVE_AWAITING_POSTBOOT_TOUCH"
    note "BOOT first HID insertion mode4; awaiting verified postboot gestures"
}
rollback() {
    require_root
    unhook
    rm -f "$BASE/armed" 2>/dev/null || true
    # Never unload the driver's instance on any other boot or stale trial.
    if [[ -d "$BASE" && "$(field trial_boot_id)" == "$(current_boot)" ]] &&
       [[ "$(mode)" == 4 ]] &&
       [[ "$(readfile /sys/module/sl4a_spi_hid/srcversion)" == "$(field srcversion)" ]]; then
        note "ROLLBACK unloading only matching staged mode4"
        modprobe -r sl4a-spi-hid || { note "ERROR unload failed; reboot to restore"; return 1; }
        modprobe sl4a-spi-hid || { note "ERROR Gate5 reload failed; reboot"; return 1; }
        sleep 3
        [[ "$(mode)" == 1 ]] || { note "ERROR expected Gate5 mode1, reboot"; return 1; }
        note "ROLLBACK Gate5 mode1 restored"
        if [[ "$(field result)" == "ACTIVE_AWAITING_POSTBOOT_TOUCH" ]]; then
            write_state result "INCONCLUSIVE_WATCHDOG_ROLLBACK"
        fi
    else
        note "ROLLBACK no matching mode4 current boot; leave loaded driver alone"
    fi
}
finish() {
    require_root
    local outcome="$1" valid=0
    [[ "$outcome" == PASS || "$outcome" == FAIL ]] || exit 2
    if [[ "$(field trial_boot_id)" == "$(current_boot)" &&
          "$(field result)" == "ACTIVE_AWAITING_POSTBOOT_TOUCH" &&
          "$(mode)" == 4 &&
          "$(readfile /sys/module/sl4a_spi_hid/srcversion)" == "$(field srcversion)" ]]; then
        valid=1
    fi
    cat "$STATS" > "$BASE/stats-after-touch.txt" 2>/dev/null || true
    journalctl -k -b --no-pager |
        grep -E 'sl4a_spi_hid|MSHW0231|PM:|CapImg' > "$BASE/kernel-coldboot.log" || true
    rollback
    cancel_timer
    if [[ "$outcome" == PASS && "$valid" == 1 && "$(mode)" == 1 ]]; then
        write_state result "PASS_COLD_FIRST_HID_AND_POSTBOOT_QUICK"
        note "PASS one cold first-HID load, actual gestures, restored Gate5"
    else
        write_state result "INCONCLUSIVE_OR_FAILED"
        note "NOT PASS; verification, gestures, or Gate5 restore did not pass"
        return 1
    fi
    # The operator's evdev capture has its own manifest/checksums.
    # Also seal the root-owned cross-boot module/clock/provenance evidence
    # with an independently checkable file list.
    ( cd "$BASE"
      sha256sum signed-mode4.ko module_sha srcversion source_sha stage_boot_id \
          trial_boot_id kernel stats-boot.txt stats-after-touch.txt \
          boot-before-hid.log boot-after-amd.log \
          kernel-coldboot.log result events.log > SHA256SUMS.txt
      sha256sum -c SHA256SUMS.txt
    )
    echo "SEALED COLD-BOOT EVIDENCE: $BASE"
}
diagnose() {
    # Purely observational; accepts previous failed/inconclusive runs.
    # Never unloads, loads, arms or changes any unit.
    [[ -d "$BASE" ]] || { echo "No staged coldboot evidence"; return 1; }
    local stored now age saved live
    saved="$(field kernel)"
    live="$(uname -r)"
    stored="$(field stage_epoch)"
    now="$(date +%s)"
    echo "=== COLD-BOOT READ-ONLY DIAGNOSIS ==="
    echo "Last result: $(field result)"
    echo "Staged kernel: ${saved:-MISSING}"
    echo "Current kernel: $live"
    echo "Staged module vermagic: $(modinfo -F vermagic "$BASE/signed-mode4.ko" 2>/dev/null || echo unavailable)"
    echo "Staged module SHA256 expected: $(field module_sha)"
    echo "Staged source commit: $(field source_sha)"
    echo "Staging boot ID: $(field stage_boot_id)"
    echo "Trial boot ID: $(field trial_boot_id)"
    echo "Current boot ID: $(current_boot)"
    echo "Loaded mode: $(mode)"
    echo "One-shot override present: $([[ -e "$OVERRIDE" ]] && echo YES || echo NO)"
    echo "Rollback timer: $(systemctl is-active sl4a-mode4-coldboot-rollback.timer 2>/dev/null || true)"
    if [[ "$stored" =~ ^[0-9]+$ ]]; then
        age=$((now - stored))
        echo "Staging age (seconds): $age"
        if (( age < 0 || age > 86400 )); then
            echo "VERDICT: staging time invalid/expired; safe fallback required."
        elif [[ "$saved" != "$live" ]]; then
            echo "VERDICT: kernel changed from $saved to $live; safe fallback was correct."
        else
            echo "VERDICT: kernel and age compatible; inspect events.log for remaining cause."
        fi
    else
        echo "VERDICT: staging timestamp missing/invalid; trial unqualified."
    fi
    echo "Recorded boot decisions:"
    [[ -f "$BASE/events.log" ]] && tail -n 16 "$BASE/events.log" || true
}
verify() {
    [[ -d "$BASE" ]] || { echo "No staged coldboot evidence"; return 1; }
    echo "Status: $(field result)"
    echo "Source commit: $(field source_sha)"
    echo "Signed module SHA256: $(field module_sha)"
    echo "Staged boot: $(field stage_boot_id)"
    echo "Trial boot: $(field trial_boot_id)"
    echo "Current boot: $(current_boot)"
    echo "Live mode: $(mode)"
    [[ "$(field trial_boot_id)" == "$(current_boot)" &&
       "$(field result)" == "ACTIVE_AWAITING_POSTBOOT_TOUCH" &&
       "$(mode)" == 4 &&
       "$(readfile /sys/module/sl4a_spi_hid/srcversion)" == "$(field srcversion)" ]] || {
        echo "NOT QUALIFIED: mode4 was not first-loaded in this boot" >&2; return 1;
    }
}
cancel() {
    require_root
    unhook
    rm -f "$BASE/armed" 2>/dev/null || true
    rollback
    cancel_timer
    [[ -d "$BASE" ]] && write_state result "CANCELLED_OR_RESTORED"
    echo "One-shot cancelled; installed Gate5 boot service preserved."
}
case "$1" in
    stage) stage "$2" "$3" ;;
    boot) boot ;;
    rollback) rollback ;;
    finish) finish "$2" ;;
    verify|status) verify ;;
    diagnose) diagnose ;;
    cancel) cancel ;;
    *) echo "Usage: $0 {stage SIGNED_MODULE SHA|boot|verify|diagnose|finish PASS|finish FAIL|rollback|cancel}" >&2; exit 2 ;;
esac
