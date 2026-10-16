#!/usr/bin/env python3
"""Live evdev + voice smoke test on the ALREADY-LOADED SL4 driver.

No module build/reload, no DKMS, no suspend, and no evidence collector.
The same privileged read-only monitor is used by the full qualification
runner; this proves sudo, event-device selection, spoken cues and a real
one-finger movement/release BEFORE another long physical session.
"""
import datetime as dt
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

from guided_session import (
    Audio, MODE, live_capture, mark, read_live_events,
)

HERE = Path(__file__).resolve().parent
MONITOR = HERE / "live_input_gate.py"


class NoCollector:
    """No recorder to terminate in this read-only smoke check."""
    def poll(self):
        return None


def find_bridge():
    found = []
    for entry in Path("/sys/class/input").glob("event*/device/name"):
        try:
            if entry.read_text().strip() == "MSHW0231 Touchscreen":
                node = Path("/dev/input") / entry.parent.parent.name
                if node.exists():
                    found.append(str(node))
        except OSError:
            pass
    if len(found) != 1:
        raise RuntimeError(
            "Expected exactly one MSHW0231 Touchscreen evdev node; "
            f"found {found}. Driver/device may not be ready.")
    return found[0]


def run():
    mode = MODE.read_text().strip() if MODE.exists() else "UNLOADED"
    print(f"VOICE/LIVE MONITOR SMOKE TEST — loaded mode {mode}")
    print("No modules or boot configuration will be changed.")
    if mode not in ("1", "4"):
        raise RuntimeError("Use the installed Gate5 (mode 1) or running mode 4")
    node = find_bridge()
    with tempfile.TemporaryDirectory(prefix="sl4a-voice-check-") as work:
        folder = Path(work)
        audio = Audio(folder)
        audio.preflight()
        print(f"Checking real input on {node}. Sudo authentication is BEFORE touch.")
        subprocess.run(["sudo", "-v"], check=True)
        # Interactive sudo is intentional. If this terminal has an unusually
        # short credential TTL, authentication can be completed before cues.
        with (folder/"monitor.stderr").open("w") as err:
            monitor = subprocess.Popen(
                ["sudo", sys.executable, "-u", str(MONITOR),
                 "--stream", "--source", "beta", "--device", node],
                stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)
            events = queue.Queue(maxsize=4096)
            capture = folder / "monitor.jsonl"
            reader = threading.Thread(target=read_live_events,
                                      args=(monitor, events, capture),
                                      daemon=True)
            reader.start()
            try:
                try:
                    ready = events.get(timeout=90)
                except queue.Empty as exc:
                    raise RuntimeError("read-only monitor did not become ready") from exc
                if ready.get("kind") != "ready" or ready.get("device") != node:
                    raise RuntimeError("evdev monitor refused startup: " + str(ready))
                print("LIVE EVENT MONITOR READY.")
                with (folder/"markers.tsv").open("w") as marks:
                    marks.write("utc\tmonotonic_seconds\tevent\tdetail\n")
                    mark(marks, "monitor-ready", f"mode={mode};node={node}")
                    audio.speak("The touchscreen monitor is ready. "
                                "This is only a one finger check. "
                                "No driver changes will be made.")
                    result = live_capture(audio, marks, [
                        ("quick-one",
                         "Touch with one finger, move it slowly, then lift.",
                         8),
                    ], events, NoCollector())
                if len(result) != 1 or result[0][1] != "PASS":
                    raise RuntimeError("one-finger live event gate did not pass")
                print("MONITOR SMOKE CHECK: PASS — live events, spoken cues, "
                      "movement and release recognized.")
                return 0
            finally:
                monitor.terminate()
                try:
                    monitor.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    monitor.kill()
                    monitor.wait()
                # Preserve a startup error on-screen; do not accidentally
                # lose actionable sudo/sysfs errors in TemporaryDirectory.
                err.flush()
                detail = (folder/"monitor.stderr").read_text(
                    errors="replace").strip()
                if detail:
                    print("Monitor stderr:", detail[-2500:], file=sys.stderr)


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (RuntimeError, OSError, subprocess.CalledProcessError,
            KeyboardInterrupt) as exc:
        print("MONITOR SMOKE CHECK: FAIL — " + str(exc), file=sys.stderr)
        sys.exit(1)
