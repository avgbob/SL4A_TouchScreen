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
    local cycle="$1" protocol="$2" out="$session/cycle-$cycle-$protocol"
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
case "${1:-}" in
    preflight) preflight ;;
    warm3) run_warm_three ;;
    *) echo "Usage: bash $0 {preflight|warm3}" >&2; exit 2 ;;
esac
