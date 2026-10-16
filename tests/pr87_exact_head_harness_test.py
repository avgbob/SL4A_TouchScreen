#!/usr/bin/env python3
"""Source and safety contracts for PR87 warm physical campaign (no /sys writes)."""
from pathlib import Path
import subprocess

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
