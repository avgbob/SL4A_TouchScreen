#!/usr/bin/env python3
"""Source and safety contracts for PR87 warm physical campaign (no /sys writes)."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
harness = (root / "tools/experiments/pr87-exact-head.sh").read_text()
guide = (root / "tools/hardware_evidence/guided_session.py").read_text()

assert subprocess.run(["bash", "-n", str(root / "tools/experiments/pr87-exact-head.sh")]).returncode == 0
assert 'PR_HEAD=18f0fe79623e6de4fdf1ae493f82a7048397386a' in harness
assert 'git -C "$PR_ROOT" rev-parse FETCH_HEAD' in harness
assert 'git -C "$PR_ROOT" switch --detach -q "$PR_HEAD"' in harness
assert 'status --porcelain --untracked-files=no' in harness
assert 'raw_mode=N raw_input_beta=Y' in harness
assert 'std_raw_transition=1' in harness
assert 'skip_std_getfeat=1' in harness
assert 'root "$KDIR/scripts/sign-file" sha256' in harness
assert 'modinfo -F srcversion "$MODULE"' in harness
assert 'field "$HID/srcversion"' in harness
assert 'experiment_src" != "$production_src"' in harness
assert 'root modprobe -r sl4a-spi-hid' in harness
assert 'root modprobe sl4a-spi-amd' in harness
assert 'root modprobe sl4a-spi-hid' in harness
assert 'binding "$CONTROLLER"' in harness and 'binding "$TOUCH"' in harness
assert 'trap on_exit EXIT' in harness
assert harness.index('trap on_exit EXIT') < harness.index('        load_pr\n        capture')
assert harness.index('active=1  # arm shell EXIT rollback BEFORE unloading') < harness.index('    root modprobe -r sl4a-spi-hid', harness.index('load_pr() {'))
assert 'python3 "$HARNESS_ROOT/tools/hardware_evidence/guided_session.py"' in harness
assert '--source-root "$PR_ROOT"' in harness
assert '--expected-mode 1' in harness
assert '--protocol "$protocol"' in harness
assert 'sha256sum' in harness
assert 'PASS_3_OF_3' in harness

# Execute the REAL capture() shell body, not just a source grep.
# The first Surface run loaded exact PR87 correctly but stopped here:
#   line 146: protocol: unbound variable
# because "local cycle=... protocol=... out=...$protocol" refers to
# protocol before local assigns it under set -u. Simulate with a shell
# stub for python3, an ordinary temporary stats file and no hardware.
cap = harness.split("capture() {\\n", 1)[1].split("\\n}\\nrun_warm_three()", 1)[0]
real_capture = "capture() {\\n" + cap + "\\n}\\n"
with tempfile.TemporaryDirectory(prefix="pr87-capture-regression-") as td:
    td = Path(td)
    (td / "stats.txt").write_text("reset_rsp=1\\nframes_dropped=0\\ndata=25\\nraw_observed=25\\n")
    runner = (
        "set -Eeuo pipefail\\n"
        'session="$1"\\nSTATS="$2"\\nPR_ROOT="$3"\\n'
        'HARNESS_ROOT="$4"\\n'
        'python3() { printf "%s\\\\n" "$@" > "$session/collector-argv.txt"; }\\n'
        + real_capture + "\\n"
        + 'capture "1" "quick"\\n'
    )
    check = subprocess.run(
        ["bash", "-c", runner, "capture-regression", str(td),
         str(td / "stats.txt"), str(td / "driver"), str(td / "harness")],
        capture_output=True, text=True,
    )
    assert check.returncode == 0, (
        "real capture() failed in nounset shell: " + check.stderr)
    assert (td / "stats-before-1.txt").read_text() == (td / "stats.txt").read_text()
    assert (td / "stats-after-1.txt").read_text() == (td / "stats.txt").read_text()
    argv = (td / "collector-argv.txt").read_text()
    assert "--protocol\\nquick\\n" in argv
    assert "--expected-mode\\n1\\n" in argv
    assert "--source-root\\n" + str(td / "driver") + "\\n" in argv
    assert "--output\\n" + str(td / "cycle-1-quick") + "\\n" in argv

for bad in ('dkms install', 'update-initramfs', 'grub-install', 'mokutil --import'):
    assert bad not in harness

assert 'parser.add_argument("--source-root", type=Path' in guide
assert 'SOURCE_ROOT = args.source_root.expanduser().resolve()' in guide
assert 'built = SOURCE_ROOT / "driver/sl4a-spi-hid.ko"' in guide
assert '["git", "-C", str(SOURCE_ROOT), "rev-parse", "HEAD"]' in guide
assert '["git", "-C", str(SOURCE_ROOT), "status", "--porcelain"' in guide
assert '"evidence_harness_root": str(ROOT)' in guide
assert '"driver_source_root": str(SOURCE_ROOT)' in guide
assert 'COLLECTOR = ROOT / "tools/hardware_evidence/run_blinded_session.sh"' in guide
assert '--capture-beta-multitouch' in guide

print("PR87 exact SHA / signed source / spoken evdev / Gate5 rollback contracts: PASS")
