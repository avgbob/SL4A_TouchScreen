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

# Emulate the exact hardware failure: systemctl returns before real sleep.
# A zero-gap initial poll must NOT produce a false negative; later genuine
# suspend time causes the same wait to succeed.
import tempfile
import json
with tempfile.TemporaryDirectory() as folder:
    destination = Path(folder) / "after.json"
    sequence = iter([
        {"monotonic": 100.1, "boottime": 100.1},
        {"monotonic": 101.1, "boottime": 101.1},
        {"monotonic": 101.2, "boottime": 105.7},
    ])
    tick = [0.0]
    def clock():
        tick[0] += .1
        return tick[0]
    assert module.wait_for_resume(
        baseline, destination, minimum=2.0, timeout=5,
        reader=lambda: next(sequence), clock=clock,
        sleeper=lambda _: None)
    assert module.sleep_seconds(
        baseline, json.loads(destination.read_text())) > 2

    # A completely non-suspending command must still fail closed.
    def no_sleep():
        return {"monotonic": 103.0, "boottime": 103.0}
    tick[0] = 0.0
    assert not module.wait_for_resume(
        baseline, destination, minimum=2.0, timeout=.6,
        reader=no_sleep, clock=clock, sleeper=lambda _: None)

wrapper = (root / "tools/experiments/host56-mode4.sh").read_text()
assert "qualify_s2idle_two() {" in wrapper
assert 'qualify-s2idle2) qualify_s2idle_two ;;' in wrapper
assert 'for cycle in 1 2; do' in wrapper
assert '"$sleep_mode" == *\'[s2idle]\'*' in wrapper
assert '"$ROOT/tools/hardware_evidence/s2idle_clock.py"' in wrapper
assert '"$ROOT/tools/hardware_evidence/speak_operator.py"' in wrapper
assert 'as_root systemctl suspend' in wrapper
assert '--wait-after "$before" "$after" --timeout-seconds 75' in wrapper, (
    "must not read the sleep clocks immediately after systemctl returns")
assert "SUSPEND REQUESTED; WAITING FOR VERIFIED WAKE" in wrapper
assert '--confirm --retries 5' in wrapper, (
    "postwake audio must be heard, not merely sent to audio player")
assert 'kernel-resume-$cycle.log' in wrapper, (
    "retain kernel log when a suspend interval remains inconclusive")
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
assert "audio.speak(message)" in audio
assert 'if confirm:' in audio
assert 'response.upper() != "YES"' in audio
assert "Speech could not be played after waking" in audio
for token in ("insmod", "modprobe", "systemctl"):
    assert token not in audio, "speech helper must never mutate hardware"
print("s2idle clock proof, operator permission and rollback contracts: PASS")
