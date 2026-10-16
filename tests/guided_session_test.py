#!/usr/bin/env python3
"""Guard audible operator cues and evidence integration without requiring a Surface."""
import importlib.util
import io
from pathlib import Path
import tempfile
import wave

root = Path(__file__).resolve().parents[1]
path = root / "tools/hardware_evidence/guided_session.py"
src = path.read_text()
spec = importlib.util.spec_from_file_location("guided_session", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

assert all(k in module.PROTOCOLS for k in ("quick", "pinch", "contacts", "stylus", "full", "single"))
for name, steps in module.PROTOCOLS.items():
    assert steps, f"{name} has no cues"
    assert len({s[0] for s in steps}) == len(steps), "cue IDs must be unique"
    assert all(isinstance(s[2], int) and s[2] >= 5 for s in steps)
assert "Did you HEAR and UNDERSTAND the spoken words?" in src
assert "espeak-ng" in src and "def speak(self, words):" in src
assert "phase_results = live_capture(audio, marks, phases, frames, proc)" in src
assert "GestureGate(label, context)" in src
assert '"--stop-file", str(marker)' in src
assert "if guide_error:" in src
assert 'args.output.exists()' in src, "must not overwrite hardware evidence"
assert '"--capture-beta-multitouch"' in src
assert '"--capture-stylus"' in src
assert '"Event: time"' in src, "must verify input events, not just file existence"
assert 'mark(marks, "capture-ready"' in src
assert 'mark(marks, "gesture-script-end"' in src
assert "collector_exit_code" in src
assert '"sudo", "-n", "sed"' in src, "must read root-owned collector identity"
assert "selected_event_node(event_capture)" in src
assert "monitor = subprocess.Popen(" in src
assert "stop_capture(proc, args.output)" in src
# Physical failure 2026-10-16: monitor subprocess cannot be launched with
# non-interactive sudo after the collector has consumed its sudo ticket.
assert '["sudo", sys.executable, "-u",' in src, "live monitor must permit a TTY password prompt"
assert '["sudo", "-n", sys.executable, "-u",' not in src
assert 'subprocess.run(["sudo", "-v"], check=True)' in src
assert 'ready = frames.get(timeout=90)' in src
smoke = (root / "tools/hardware_evidence/verify_live_monitor.py").read_text()
assert 'MODE.read_text().strip()' in smoke
assert 'find_bridge()' in smoke and 'MSHW0231 Touchscreen' in smoke
assert 'live_capture(audio, marks' in smoke
assert '"quick-one"' in smoke
assert '["sudo", sys.executable, "-u", str(MONITOR)' in smoke
for token in ('"insmod"', '"modprobe"', '"dkms"', '"reboot"'):
    assert token not in smoke, "smoke test must not modify the kernel module"
wrapper = (root / "tools/experiments/host56-mode4.sh").read_text()
assert "qualify() {" in wrapper
assert 'trap \'restore\' EXIT' in wrapper
assert 'if [[ ! -r "$SYS" || "$(cat "$SYS")" != 1 ]]' in wrapper
assert 'capture "$protocol"' in wrapper
assert 'quick|full|contacts' in wrapper, (
    "qualification should cover untested contact-count cases without"
    " making the physical tester repeat established pinch sequences")
assert module.PROTOCOLS["full"][-7:] == [
    ("contacts-" + label, prompt, seconds)
    for label, prompt, seconds in module.PROTOCOLS["contacts"]
], "focused contact qualification must match the last seven full-test phases"
assert 'qualify) qualify "${2:-full}"' in wrapper
for dangerous in ('"modprobe"', '"insmod"', '"dkms"', '"reboot"'):
    assert dangerous not in src, f"evidence script may not change modules: {dangerous}"

with tempfile.TemporaryDirectory() as temp:
    audio = module.Audio(Path(temp), dry=True)
    for key, wav in audio.sounds.items():
        with wave.open(str(wav), "rb") as f:
            assert f.getnframes() > 1000 and f.getnchannels() == 1
    out = io.StringIO()
    original = module.safe_sleep
    module.safe_sleep = lambda *a, **kw: None  # no wall-clock wait in host CI
    try:
        module.countdown(audio, out, 5)
        module.guide(audio, out, module.PROTOCOLS["pinch"])
    finally:
        module.safe_sleep = original
    rows = out.getvalue().splitlines()
    assert len([r for r in rows if "\tphase-begin\t" in r]) == 5
    assert len([r for r in rows if "\tphase-end\t" in r]) == 5
    assert any("\tgesture-script-end\t" in r for r in rows)
print("audible guided session behavioral contract: PASS")
