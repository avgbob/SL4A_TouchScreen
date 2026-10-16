#!/usr/bin/env python3
"""No-device contracts for gated real s2idle qualification."""
import sys
from pathlib import Path
import importlib.util

root = Path(__file__).resolve().parents[1]
path = root / "tools/hardware_evidence/s2idle_clock.py"
spec = importlib.util.spec_from_file_location("s2idle_clock", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

baseline = {"monotonic": 100.0, "boottime": 100.0}
assert module.sleep_seconds(
    baseline, {"monotonic": 103.0, "boottime": 103.5}) == 0.5, (
    "no-op sleep must be below minimum suspend threshold")
assert module.sleep_seconds(
    baseline, {"monotonic": 104.0, "boottime": 115.0}) == 11.0
try:
    module.sleep_seconds(
        baseline, {"monotonic": 99, "boottime": 105})
except ValueError:
    pass
else:
    raise AssertionError("reboot / invalid clock must not be accepted")

wrapper = (root / "tools/experiments/host56-mode4.sh").read_text()
assert "qualify_s2idle_two() {" in wrapper
assert 'qualify-s2idle2) qualify_s2idle_two ;;' in wrapper
assert 'for cycle in 1 2; do' in wrapper
assert '"$sleep_mode" == *\'[s2idle]\'*' in wrapper
assert '"$ROOT/tools/hardware_evidence/s2idle_clock.py"' in wrapper
assert '"$ROOT/tools/hardware_evidence/speak_operator.py"' in wrapper
assert 'as_root systemctl suspend' in wrapper
assert 'PM: suspend entry (s2idle)' in wrapper
assert 'PM: suspend exit' in wrapper
assert 'capture quick' in wrapper
assert "trap 'restore' EXIT" in wrapper
assert '[[ -r "$SYS" && "$(cat "$SYS")" == 1 ]]' in wrapper
assert 'sha256sum -c SHA256SUMS.txt' in wrapper
assert 'IFS= read -r confirm' in wrapper, (
    "system suspension requires explicit YES operator confirmation")
audio = (root / "tools/hardware_evidence/speak_operator.py").read_text()
assert "from guided_session import Audio" in audio
assert "Audio(Path(folder)).speak" in audio
for token in ("insmod", "modprobe", "systemctl"):
    assert token not in audio, "speech helper must never mutate hardware"
print("s2idle clock proof, operator permission and rollback contracts: PASS")
