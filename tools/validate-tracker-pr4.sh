#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0
#
# Validate the tracker/post-association-coalescing branch without installing
# or loading either kernel module. Safe to run from a detached validation
# worktree: it only builds/tests files under that worktree.
#
# Usage:
#   ./tools/validate-tracker-pr4.sh
#
# Optional:
#   KDIR=/lib/modules/$(uname -r)/build ./tools/validate-tracker-pr4.sh

set -u
set -o pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
KDIR="${KDIR:-/lib/modules/$(uname -r)/build}"
FAIL=0

section() {
    printf '\n===== %s =====\n' "$1"
}

run() {
    printf '+'
    printf ' %q' "$@"
    printf '\n'
    "$@"
    rc=$?
    if [ "$rc" -ne 0 ]; then
        printf 'FAILED rc=%d: ' "$rc" >&2
        printf '%q ' "$@" >&2
        printf '\n' >&2
        FAIL=1
    fi
    return 0
}

section "PROVENANCE"
git -C "$ROOT" status --short --branch || true
git -C "$ROOT" log -1 --oneline --decorate || true
printf 'kernel: %s\n' "$(uname -r)"
printf 'KDIR:   %s\n' "$KDIR"

section "SOURCE ORDER PIN"
if grep -q 'raw_ghost_merge(' "$ROOT/driver/mshw0231-raw.c"; then
    echo "FAIL: raw_ghost_merge() still exists in production driver source"
    FAIL=1
else
    echo "PASS: destructive pre-association raw_ghost_merge() absent"
fi

python3 - "$ROOT/driver/mshw0231-raw.c" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text()
body = text.split("static void mshw0231_raw_process_samples", 1)[1]
a = body.find("raw_hungarian_match(")
b = body.find("raw_post_assoc_coalesce(")
c = body.find("raw_update_slots(")
print(f"hungarian={a} postassoc={b} slot_update={c}")
if not (0 <= a < b < c):
    raise SystemExit("FAIL: expected Hungarian -> post-association coalescing -> slot update")
print("PASS: production pipeline order pinned")
PY
if [ "$?" -ne 0 ]; then
    FAIL=1
fi

section "ROOTLESS TEST SHIMS"
# tests/hunt_sandbox_test.sh deliberately exercises code paths that normally
# re-exec through sudo. GitHub-hosted runners allow passwordless sudo, but a
# developer laptop should never need credentials (or real root) for this
# synthetic test. Put a no-elevation sudo shim in PATH: commands still resolve
# against the sandbox's own modprobe/dkms/etc stubs, and any accidental write
# outside the sandbox remains unprivileged and therefore fails safely.
SHIM_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sl4a-pr4-shim.XXXXXX")"
trap 'rm -rf "$SHIM_DIR"' EXIT
cat > "$SHIM_DIR/sudo" <<'EOS'
#!/usr/bin/env bash
set -u
while [ "$#" -gt 0 ]; do
    case "$1" in
        -n|-E|-H|-S) shift ;;
        --) shift; break ;;
        *) break ;;
    esac
done
exec "$@"
EOS
chmod +x "$SHIM_DIR/sudo"
export PATH="$SHIM_DIR:$PATH"
echo "PASS: host tests will use a rootless sudo shim (no password prompt)"

section "HOST TESTS"
run make -C "$ROOT/tests" clean
run make -C "$ROOT/tests" test

section "SANITIZER HOST TESTS"
run make -C "$ROOT/tests" clean
run make -C "$ROOT/tests" SANITIZE=1 test

section "KERNEL MODULE BUILD"
if [ ! -f "$KDIR/Makefile" ]; then
    echo "FAIL: kernel build tree not found at $KDIR"
    FAIL=1
else
    run make -C "$KDIR" M="$ROOT/driver" clean
    run make -C "$KDIR" M="$ROOT/driver" modules

    section "BUILT MODULES"
    for ko in "$ROOT/driver/sl4a-spi-amd.ko" "$ROOT/driver/sl4a-spi-hid.ko"; do
        if [ -s "$ko" ]; then
            ls -lh "$ko"
            modinfo "$ko" | grep -E '^(filename|srcversion|vermagic):' || true
        else
            echo "FAIL: missing $ko"
            FAIL=1
        fi
    done
fi

section "RESULT"
if [ "$FAIL" -ne 0 ]; then
    echo "VALIDATION FAILED"
    exit 1
fi

echo "VALIDATION PASSED"
echo "No module was installed or loaded."
