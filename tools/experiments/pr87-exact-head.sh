#!/usr/bin/env bash
# Reversible, opt-in Syax89 PR #87 exact-driver warm hardware acceptance.
# This harness lives on experiment/sl4-std-host56-set5, OUTSIDE the PR.
# No DKMS install, boot-unit modification, initramfs, or persistent config.
set -Eeuo pipefail

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PR_ROOT="${SL4A_PR87_ROOT:-$HOME/SL4A_TouchScreen-pr87}"
PR_URL=https://github.com/avgbob/SL4A_TouchScreen.git
PR_BRANCH=upstream/std-capimg-mt
PR_HEAD=18f0fe79623e6de4fdf1ae493f82a7048397386a
HID=/sys/module/sl4a_spi_hid
MODE="$HID/parameters/std_raw_transition"
STATS=/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats
CONTROLLER=/sys/bus/platform/devices/AMDI0060:00
TOUCH=/sys/bus/acpi/devices/MSHW0231:00/physical_node
UNIT_OVERRIDE=/etc/systemd/system/sl4a-touch-activate.service.d/90-mode4-once.conf
MODULE="$PR_ROOT/driver/sl4a-spi-hid.ko"
KDIR="/lib/modules/$(uname -r)/build"
active=0
experiment_src=""
production_src=""
session=""

die() { echo "ERROR: $*" >&2; exit 1; }
root() { if (( EUID == 0 )); then "$@"; else sudo "$@"; fi; }
field() { [[ -r "$1" ]] && cat "$1" || true; }
binding() { [[ -L "$1/driver" ]] && basename "$(readlink -f "$1/driver")" || true; }
sha() { sha256sum "$1" | awk '{print $1}'; }
preflight() {
    [[ -d /sys/bus/acpi/devices/MSHW0231:00 ]] || die "MSHW0231:00 missing; wrong hardware"
    [[ -r "$MODE" && "$(field "$MODE")" == 1 ]] || die "working production Gate5 mode1 required"
    [[ "$(binding "$CONTROLLER")" == sl4a_spi_amd_v2_multi ]] || die "AMD SPI controller unbound"
    [[ "$(binding "$TOUCH")" == sl4a_spi_hid ]] || die "touchscreen HID unbound"
    [[ -r "$STATS" ]] || die "no readable protocol_stats"
    [[ ! -e "$UNIT_OVERRIDE" && ! -e /var/lib/sl4a-mode4-coldboot/armed ]] ||
        die "a different one-shot boot experiment is staged"
    [[ -f "$KDIR/Makefile" ]] || die "running kernel headers missing"
    [[ -e /etc/modprobe.d/sl4a-spi-hid.conf ]] || die "production Gate5 config absent"
    grep -q 'std_raw_transition=1' /etc/modprobe.d/sl4a-spi-hid.conf ||
        die "production Gate5 profile not recognized"
    production_src="$(modinfo -F srcversion sl4a-spi-hid)"
    [[ -n "$production_src" && "$(field "$HID/srcversion")" == "$production_src" ]] ||
        die "running HID is NOT installed Gate5 module"
    echo "BASELINE PASS: kernel=$(uname -r), Gate5=$production_src, both bindings active"
}
checkout_exact() {
    if [[ ! -d "$PR_ROOT/.git" ]]; then
        [[ ! -e "$PR_ROOT" ]] || die "PR_ROOT exists and is not a git checkout: $PR_ROOT"
        git clone -q "$PR_URL" "$PR_ROOT"
    fi
    [[ "$(git -C "$PR_ROOT" config --get remote.origin.url)" == "$PR_URL" ]] ||
        die "unexpected PR checkout remote; refusing automatic fetch"
    [[ -z "$(git -C "$PR_ROOT" status --porcelain --untracked-files=no)" ]] ||
        die "PR checkout has tracked changes; refusing to overwrite"
    git -C "$PR_ROOT" fetch -q --no-tags origin "$PR_BRANCH"
    [[ "$(git -C "$PR_ROOT" rev-parse FETCH_HEAD)" == "$PR_HEAD" ]] ||
        die "PR head changed; pin/test script must be re-reviewed. Wanted $PR_HEAD"
    git -C "$PR_ROOT" switch --detach -q "$PR_HEAD"
    [[ "$(git -C "$PR_ROOT" rev-parse HEAD)" == "$PR_HEAD" ]] ||
        die "source checkout identity mismatch"
    grep -q 'spi_hid_std_capimg_enabled' "$PR_ROOT/driver/spi-hid-core.c" ||
        die "PR activation gate absent from checked-out source"
    echo "PR SOURCE PINNED: $PR_HEAD"
}
prepare() {
    checkout_exact
    # The previous aborted first-cycle run left a SIGNED .ko in this
    # separate build worktree. Kbuild may consider it up-to-date;
    # appending another PKCS#7 signature to that existing binary would
    # destroy the one-build/one-signature provenance guarantee.
    # Clean only the transient PR driver build objects, never DKMS.
    make -C "$KDIR" M="$PR_ROOT/driver" clean
    make -C "$KDIR" M="$PR_ROOT/driver" modules
    [[ -s "$MODULE" ]] || die "PR HID .ko missing after build"
    if command -v mokutil >/dev/null && mokutil --sb-state 2>/dev/null |
         grep -qi 'SecureBoot enabled'; then
        local key=/var/lib/shim-signed/mok/MOK.priv
        local cert=/var/lib/shim-signed/mok/MOK.der
        [[ -x "$KDIR/scripts/sign-file" ]] || die "kernel signing script absent"
        local enrolled
        enrolled="$(root mokutil --test-key "$cert" 2>&1 || true)"
        grep -qi 'already enrolled' <<<"$enrolled" ||
            die "active signing MOK not enrolled; do not load"
        root "$KDIR/scripts/sign-file" sha256 "$key" "$cert" "$MODULE"
    fi
    [[ "$(modinfo -F vermagic "$MODULE" | awk '{print $1}')" == "$(uname -r)" ]] ||
        die "signed PR module targets wrong kernel"
    [[ -n "$(modinfo -F signer "$MODULE")" ]] ||
        die "unsigned PR module; refusing"
    experiment_src="$(modinfo -F srcversion "$MODULE")"
    [[ -n "$experiment_src" && "$experiment_src" != "$production_src" ]] ||
        die "PR source identity missing or indistinguishable from production Gate5"
    echo "EXPERIMENT READY: signed SHA256=$(sha "$MODULE"), srcversion=$experiment_src"
}
restore() {
    (( active == 1 )) || return 0
    local live
    live="$(field "$HID/srcversion")"
    if [[ "$live" == "$experiment_src" ]]; then
        echo "RESTORE: unload only matching PR87 experimental HID"
        root modprobe -r sl4a-spi-hid || return 1
    elif [[ -z "$live" ]]; then
        echo "RESTORE: HID absent after activation attempt; install production module"
    elif [[ "$live" != "$production_src" ]]; then
        echo "REFUSE RESTORE: unrelated HID revision $live; manual inspection required" >&2
        return 1
    fi
    root modprobe sl4a-spi-amd || return 1
    root modprobe sl4a-spi-hid || return 1
    sleep 3
    [[ "$(field "$MODE")" == 1 &&
       "$(field "$HID/srcversion")" == "$production_src" &&
       "$(binding "$CONTROLLER")" == sl4a_spi_amd_v2_multi &&
       "$(binding "$TOUCH")" == sl4a_spi_hid && -r "$STATS" ]] ||
        die "Gate5 parameter/source/bindings not verified after restore"
    active=0
    echo "RESTORE PASS: working production Gate5 bound; test touch physically"
}
on_exit() {
    local rc=$?
    trap - EXIT INT TERM
    if (( active )); then
        if ! restore; then
            echo "RECOVERY REQUIRES ATTENTION: reboot after saving work; do not stage more tests" >&2
            rc=1
        fi
    fi
    if (( rc != 0 )) && [[ -n "$session" ]]; then
        echo "INCONCLUSIVE_OR_FAILED" > "$session/result.txt" || true
    fi
    exit "$rc"
}
load_pr() {
    [[ "$(field "$HID/srcversion")" == "$production_src" ]] ||
        die "production driver not restored before PR loading"
    active=1  # arm shell EXIT rollback BEFORE unloading
    root modprobe -r sl4a-spi-hid
    root insmod "$MODULE" raw_mode=N raw_input_beta=Y \
        wire_double_opcode=1 skip_std_getfeat=1 \
        std_raw_transition=1 get_noread=0 getfeat_delay_ms=0 \
        std_liveness_ms=0 std_liveness_recover=0 wait_reset_kick_ms=0
    sleep 3
    [[ "$(field "$MODE")" == 1 &&
       "$(field "$HID/srcversion")" == "$experiment_src" &&
       "$(binding "$CONTROLLER")" == sl4a_spi_amd_v2_multi &&
       "$(binding "$TOUCH")" == sl4a_spi_hid && -r "$STATS" ]] ||
        die "PR87 module identity/bindings failed to activate"
    echo "PR87 ACTIVE: verified loaded PR srcversion $experiment_src"
}
capture() {
    # Bash expands a single `local` command before any names declared
    # in that command become available. Under `set -u`, using $protocol
    # while declaring it makes the first real capture fail immediately.
    local cycle="$1" protocol="$2"
    local out="$session/cycle-$cycle-$protocol"
    local tag="pr87-$protocol-$cycle-$(date -u +%Y%m%dT%H%M%SZ)"
    cat "$STATS" > "$session/stats-before-$cycle.txt"
    python3 "$HARNESS_ROOT/tools/hardware_evidence/guided_session.py" \
        --source-root "$PR_ROOT" --protocol "$protocol" \
        --expected-mode 1 --period p1 --case "$tag" --output "$out"
    cat "$STATS" > "$session/stats-after-$cycle.txt"
}
run_warm_three() {
    preflight
    checkout_exact
    echo "This temporarily unloads Gate5 HID for a signed PR87 test; AMD controller remains."
    echo "Gate5 restores between three guided physical touch sessions and on normal exit."
    echo "No DKMS changes, no boot override, no root-owned installer edits."
    local confirm
    printf "Type WARM to build/sign and begin the PR87 warm 3/3 test: "
    IFS= read -r confirm
    [[ "$confirm" == WARM ]] || die "no driver changed; test cancelled"
    prepare
    session="$HOME/sl4a-hardware-runs/pr87-exact-warm3-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p -m 0700 "$session"
    {
        echo "source_commit=$PR_HEAD"
        echo "kernel=$(uname -r)"
        echo "module_sha256=$(sha "$MODULE")"
        echo "module_srcversion=$experiment_src"
        echo "production_srcversion=$production_src"
        echo "test=3 warm activations with real event-gated multi-touch"
    } > "$session/provenance.txt"
    printf 'INCOMPLETE\n' > "$session/result.txt"
    trap on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    local cycle
    for cycle in 1 2 3; do
        echo "=== PR87 WARM CYCLE $cycle / 3 — signed module $(sha "$MODULE") ==="
        load_pr
        capture "$cycle" quick
        restore
        echo "WARM $cycle/3 PASSED; production Gate5 restored"
    done
    echo "PASS_3_OF_3" > "$session/result.txt"
    echo "PR87 WARM 3/3 PASS; evidence: $session"
}

# One independent exact-PR87 full gesture matrix. All gestures run
# against ONE signed module; production Gate5 is restored on normal exit,
# failure, or interrupt. No permanent configuration or reboot.
run_full_matrix() {
    preflight
    checkout_exact
    echo "The full matrix uses spoken, evdev-gated gestures on a temporary PR87 HID."
    echo "The installed Gate5 driver will be restored after the capture."
    echo "This is NOT a cold first-HID load or default-standard negative control."
    local confirm
    printf 'Type MATRIX to build/sign and run the PR87 full physical gesture matrix: '
    IFS= read -r confirm
    [[ "$confirm" == MATRIX ]] || die "no driver changed; matrix cancelled"
    prepare
    session="$HOME/sl4a-hardware-runs/pr87-exact-matrix-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p -m 0700 "$session"
    {
        echo "source_commit=$PR_HEAD"
        echo "kernel=$(uname -r)"
        echo "module_sha256=$(sha "$MODULE")"
        echo "module_srcversion=$experiment_src"
        echo "production_srcversion=$production_src"
        echo "test=one reversible PR87 full event-gated gesture matrix"
    } > "$session/provenance.txt"
    printf 'INCOMPLETE\n' > "$session/result.txt"
    trap on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    local signed_hash
    signed_hash="$(sha "$MODULE")"
    load_pr
    capture "matrix" full
    [[ "$(sha "$MODULE")" == "$signed_hash" ]] ||
        die "signed PR module file changed during the full matrix"
    [[ "$(field "$HID/srcversion")" == "$experiment_src" ]] ||
        die "experimental module identity changed during the full matrix"
    restore
    printf 'PASS_FULL_MATRIX\n' > "$session/result.txt"
    ( cd "$session"; find . -maxdepth 1 -type f ! -name SHA256SUMS.txt \
        -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS.txt )
    ( cd "$session"; sha256sum -c SHA256SUMS.txt )
    echo "PR87 FULL MATRIX PASS; source pinned, signed module stable, Gate5 restored."
    echo "MATRIX EVIDENCE: $session"
}

# Explicit negative control of the exact PR #87 module.
# This intentionally disables BOTH standard CapImg activation and beta input.
# A passive raw_observed count is allowed: observation is not publication.
load_pr_standard_negative() {
    [[ "$(field "$HID/srcversion")" == "$production_src" ]] ||
        die "production driver not restored before negative control"
    active=1  # arm EXIT rollback BEFORE unloading Gate5
    root modprobe -r sl4a-spi-hid
    root insmod "$MODULE" raw_mode=N raw_input_beta=N \
        wire_double_opcode=1 skip_std_getfeat=1 \
        std_raw_transition=0 get_noread=0 getfeat_delay_ms=0 \
        std_liveness_ms=0 std_liveness_recover=0 wait_reset_kick_ms=0
    sleep 3
    [[ "$(field "$MODE")" == 0 &&
       "$(field "$HID/parameters/raw_mode")" == N &&
       "$(field "$HID/parameters/raw_input_beta")" == N &&
       "$(field "$HID/srcversion")" == "$experiment_src" &&
       "$(binding "$CONTROLLER")" == sl4a_spi_amd_v2_multi &&
       "$(binding "$TOUCH")" == sl4a_spi_hid && -r "$STATS" ]] ||
        die "negative-control module identity/opt-out/bindings failed"
    echo "PR87 DEFAULT STANDARD ACTIVE: experimental bridge disabled; source $experiment_src"
}

run_standard_negative() {
    preflight
    checkout_exact
    echo "PR87 opt-out control: std_raw_transition=0 raw_input_beta=0 raw_mode=N."
    echo "Touchscreen multitouch is NOT expected to function in this mode."
    echo "The test verifies standard HID discovery and absence of the added MT bridge."
    echo "It does NOT infer Report 0x0c dispatch policy from missing touch reports."
    echo "Gate5 is restored on normal exit and on ordinary failures or interruptions."
    local confirm
    printf 'Type NEGATIVE to build/sign and run this reversible PR87 opt-out control: '
    IFS= read -r confirm
    [[ "$confirm" == NEGATIVE ]] || die "cancelled before any driver change"
    prepare
    session="$HOME/sl4a-hardware-runs/pr87-exact-negative-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p -m 0700 "$session"
    {
        echo "source_commit=$PR_HEAD"
        echo "kernel=$(uname -r)"
        echo "module_sha256=$(sha "$MODULE")"
        echo "module_srcversion=$experiment_src"
        echo "production_srcversion=$production_src"
        echo "negative_control=raw_mode=N raw_input_beta=N std_raw_transition=0"
    } > "$session/provenance.txt"
    printf 'INCOMPLETE\n' > "$session/result.txt"
    trap on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    local signed_hash
    signed_hash="$(sha "$MODULE")"
    load_pr_standard_negative
    cat "$STATS" > "$session/standard-stats-before.txt"
    sleep 5
    python3 "$HARNESS_ROOT/tools/hardware_evidence/pr87_standard_negative.py" \
        --expected-srcversion "$experiment_src" \
        | tee "$session/negative-control-verdict.json"
    cat "$STATS" > "$session/standard-stats-after.txt"
    [[ "$(sha "$MODULE")" == "$signed_hash" &&
       "$(field "$HID/srcversion")" == "$experiment_src" ]] ||
        die "experimental signed module changed during negative control"
    restore
    printf 'PASS_NEGATIVE_CONTROL\n' > "$session/result.txt"
    ( cd "$session"; find . -maxdepth 1 -type f ! -name SHA256SUMS.txt \
        -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS.txt )
    ( cd "$session"; sha256sum -c SHA256SUMS.txt )
    echo "PR87 NEGATIVE CONTROL PASS: opt-out, standard discovery, no added MT bridge; Gate5 restored."
    echo "NOTE: report 0x0c dispatch is protected by host production-handler regression; not physically inferred."
    echo "NEGATIVE CONTROL EVIDENCE: $session"
}

# Two real suspend cycles with ONE signed PR module continuously loaded.
# This is not a warm module reload: it audits the PM s2idle entry/exit,
# CLOCK_BOOTTIME-minus-MONOTONIC sleep gap, and post-wake actual MT events.
# Keep this separate from the earlier GET6-free mode4 run.
run_s2idle_two() {
    preflight
    checkout_exact
    [[ -r /sys/power/mem_sleep ]] || die "kernel mem_sleep policy not readable"
    local sleep_mode
    sleep_mode="$(cat /sys/power/mem_sleep)"
    [[ "$sleep_mode" == *'[s2idle]'* ]] ||
        die "actual selected sleep is not s2idle: $sleep_mode (will not modify policy)"
    command -v systemctl >/dev/null || die "systemctl not available"
    [[ -f "$HARNESS_ROOT/tools/hardware_evidence/s2idle_clock.py" &&
       -f "$HARNESS_ROOT/tools/hardware_evidence/speak_operator.py" ]] ||
        die "approved physical PM/talking helpers missing"

    echo "REAL PR87 S2IDLE 2/2: machine will physically suspend TWICE."
    echo "Save your work now. A forced reboot retains the installed Gate5 profile."
    echo "PR source is pinned; the signed test module stays loaded for both sleeps."
    echo "Two separate post-wake spoken evdev tests follow; NO permanent boot edits."
    local confirm
    printf 'Type S2IDLE to build/sign and begin actual suspend testing: '
    IFS= read -r confirm
    [[ "$confirm" == S2IDLE ]] || die "cancelled before driver modifications"

    prepare
    session="$HOME/sl4a-hardware-runs/pr87-exact-s2idle2-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p -m 0700 "$session"
    local signed_hash
    signed_hash="$(sha "$MODULE")"
    {
        echo "source_commit=$PR_HEAD"
        echo "kernel=$(uname -r)"
        echo "signed_module_sha256=$signed_hash"
        echo "module_srcversion=$experiment_src"
        echo "production_srcversion=$production_src"
        echo "selected_sleep_policy=$sleep_mode"
        echo "test=2_genuine_s2idle_gaps_postwake_evdev_pr87"
    } > "$session/provenance.txt"
    printf 'INCOMPLETE\n' > "$session/result.txt"
    trap on_exit EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM

    load_pr
    local cycle journal_since before after
    for cycle in 1 2; do
        echo "=== PR87 S2IDLE CYCLE $cycle / 2 ==="
        [[ "$(cat /sys/power/mem_sleep)" == *'[s2idle]'* ]] ||
            die "s2idle selection changed before cycle $cycle"
        [[ "$(field "$MODE")" == 1 &&
           "$(field "$HID/srcversion")" == "$experiment_src" &&
           "$(binding "$CONTROLLER")" == sl4a_spi_amd_v2_multi &&
           "$(binding "$TOUCH")" == sl4a_spi_hid && -r "$STATS" ]] ||
            die "PR87 module/bindings not healthy before suspend cycle $cycle"
        [[ "$(sha "$MODULE")" == "$signed_hash" ]] ||
            die "PR signed module file changed before cycle $cycle"
        cat "$STATS" > "$session/stats-before-sleep-$cycle.txt"
        python3 "$HARNESS_ROOT/tools/hardware_evidence/speak_operator.py" \
            "Suspend test $cycle of 2. Your computer will sleep. Wake with the power button or keyboard, unlock the screen and return to this terminal for the spoken post-wake touchscreen test."
        printf 'Type YES to initiate actual s2idle cycle %s/2: ' "$cycle"
        local cycle_confirm
        IFS= read -r cycle_confirm
        [[ "$cycle_confirm" == YES || "$cycle_confirm" == yes ]] ||
            die "cycle $cycle not confirmed, safely restoring Gate5"
        root true
        if (( EUID != 0 )); then sudo -v; fi
        journal_since="$(date '+%Y-%m-%d %H:%M:%S')"
        printf '%s\n' "$journal_since" > "$session/journal-since-$cycle.txt"
        before="$session/clock-before-$cycle.json"
        after="$session/clock-after-$cycle.json"
        python3 "$HARNESS_ROOT/tools/hardware_evidence/s2idle_clock.py" \
            --snapshot "$before"
        echo "=== REQUESTING REAL SYSTEM SUSPEND ==="
        root systemctl suspend
        echo "=== WAITING FOR REAL SUSPEND CLOCK GAP / WAKE ==="
        if ! python3 "$HARNESS_ROOT/tools/hardware_evidence/s2idle_clock.py" \
            --wait-after "$before" "$after" --timeout-seconds 75 \
            | tee "$session/clock-verdict-$cycle.txt"; then
            root journalctl -k -b --since "$journal_since" --no-pager \
                > "$session/kernel-resume-$cycle.log" || true
            die "no verified >=2s real sleep interval after cycle $cycle"
        fi
        sleep 2
        [[ "$(field "$HID/srcversion")" == "$experiment_src" &&
           "$(field "$MODE")" == 1 &&
           "$(binding "$CONTROLLER")" == sl4a_spi_amd_v2_multi &&
           "$(binding "$TOUCH")" == sl4a_spi_hid && -r "$STATS" ]] ||
            die "exact PR87 module/controller/touch did not survive sleep cycle $cycle"
        [[ "$(sha "$MODULE")" == "$signed_hash" ]] ||
            die "PR module file changed during sleep $cycle"
        cat "$STATS" > "$session/stats-after-resume-$cycle.txt"
        root journalctl -k -b --since "$journal_since" --no-pager \
            > "$session/kernel-resume-$cycle.log"
        grep -q 'PM: suspend entry (s2idle)' \
            "$session/kernel-resume-$cycle.log" ||
            die "kernel has no genuine s2idle entry marker for cycle $cycle"
        grep -q 'PM: suspend exit' "$session/kernel-resume-$cycle.log" ||
            die "kernel has no suspend exit marker for cycle $cycle"

        # Post-wake speech requires interactive HEARD confirmation;
        # display text or a successful audio-process exit is not enough.
        python3 "$HARNESS_ROOT/tools/hardware_evidence/speak_operator.py" \
            --confirm --retries 5 \
            "The laptop is awake after PR87 suspend cycle $cycle. This is the post-wake voice checkpoint. After you hear me, confirm YES in the terminal and follow the spoken one finger and two finger touchscreen tests."
        echo "=== REAL POST-WAKE TOUCH CAPTURE $cycle / 2 ==="
        capture "s2idle-$cycle" quick |
            tee "$session/capture-$cycle.log"
        [[ "$(sha "$MODULE")" == "$signed_hash" ]] ||
            die "signed module changed after gesture cycle $cycle"
        echo "=== PR87 S2IDLE CYCLE $cycle / 2 PASSED ==="
    done
    restore
    printf 'PASS_2_OF_2\n' > "$session/result.txt"
    # Capture local provenance, logs and counters, without uploading raw
    # evdev/touch traces off the user's computer.
    ( cd "$session"; find . -maxdepth 1 -type f ! -name SHA256SUMS.txt \
        -print0 | sort -z | xargs -0 -r sha256sum > SHA256SUMS.txt )
    ( cd "$session"; sha256sum -c SHA256SUMS.txt )
    echo "PR87 S2IDLE 2/2 PASS: real clock+PM gaps, postwake gestures, same signed module, Gate5 restored."
    echo "S2IDLE EVIDENCE: $session"
}

case "${1:-}" in
    preflight) preflight ;;
    warm3) run_warm_three ;;
    s2idle2) run_s2idle_two ;;
    full-matrix) run_full_matrix ;;
    standard-negative) run_standard_negative ;;
    *) echo "Usage: bash $0 {preflight|warm3|s2idle2|full-matrix|standard-negative}" >&2; exit 2 ;;
esac
