#!/usr/bin/env python3
"""Behavioral mock: every voiced transition preserves live input continuity."""
import io
from pathlib import Path
import queue
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "tools/hardware_evidence"))
from guided_session import live_capture


class Collector:
    def poll(self):
        return None


class FakeVoice:
    def __init__(self, events, broken=False, sequential_release=False):
        self.events = events
        self.broken = broken
        self.sequential_release = sequential_release
        self.speech = []
        self.go_count = 0
        self.seq = 0

    def put(self, touches):
        self.seq += 1
        self.events.put({"kind": "frame", "seq": self.seq,
                         "monotonic": time.monotonic(),
                         "contacts": [{"id": id_, "x": x, "y": y}
                                      for id_, x, y in touches],
                         "tip": bool(touches), "pen": False})

    def speak(self, message):
        self.speech.append(message)
        if message == "Go.":
            self.go_count += 1
            if self.go_count == 1:
                def one():
                    self.put([(1, 100, 100)])
                    self.put([(1, 200, 100)])
                    self.put([])
                threading.Timer(.03, one).start()
            elif self.go_count == 2:
                def pinch():
                    self.put([(11, 100, 200), (12, 900, 200)])
                    self.put([(11, 300, 200), (12, 600, 200)])
                threading.Timer(.03, pinch).start()
        elif message == "Now move those SAME two fingers apart.":
            if self.broken:
                # A physical finger lift while the instruction plays
                # invalidates this pair, even if new contacts appear later.
                self.put([])
                self.put([(21, 100, 200), (22, 950, 200)])
            else:
                self.put([(11, 300, 200), (12, 600, 200)])
                self.put([(11, 100, 200), (12, 950, 200)])
        elif message == "Lift both fingers now.":
            if self.sequential_release:
                self.put([(11, 100, 200)])  # real 2->1 transient
            self.put([])

    def play(self, cue):
        assert cue in ("go", "end")


phases = [
    ("quick-one", "Move one finger, then lift.", 8),
    ("quick-pinch", "Pinch with two fingers.", 8),
    ("quick-expand", "Expand same two fingers.", 8),
    ("quick-lift", "Lift both fingers.", 5),
]

events = queue.Queue()
voice = FakeVoice(events)
markers = io.StringIO()
res = live_capture(voice, markers, phases, events, Collector())
assert [entry[0] for entry in res] == [v[0] for v in phases]
assert all(entry[1] == "PASS" for entry in res)
assert voice.go_count == 2, (
    "the expand/lift continuation must skip full spoken countdown")
assert voice.speech.count("5") == 2
assert "Now move those SAME two fingers apart." in voice.speech
assert "Lift both fingers now." in voice.speech
assert markers.getvalue().count("\tphase-pass\t") == 4

# Physical-session sequence 2 -> 1 -> 0: do not speak a stale
# "Lift it now" instruction after the operator already lifted both,
# but retain the intermediate original-ID status in timestamped cues.
events = queue.Queue()
voice = FakeVoice(events, sequential_release=True)
markers = io.StringIO()
res = live_capture(voice, markers, phases, events, Collector())
assert len(res) == 4 and all(r[1] == "PASS" for r in res)
assert "One original finger remains. Lift it now." not in voice.speech, (
    "a queued transient 2->1 observation must not become a late command")
assert "quick-lift:One original finger remains. Lift it now." in markers.getvalue(), (
    "retain the exact intermediate evdev status for later forensic review")
assert "\tphase-pass\tquick-lift;" in markers.getvalue(), (
    "only original-pair zero contacts can complete release")


# Regression: slow spoken progress must not block the gate from consuming
# the next event frame. The capture may wait for audio at the boundary,
# but the pinch PASS timestamp must precede completion of slow speech.
class SlowProgressVoice(FakeVoice):
    def __init__(self, events):
        super().__init__(events)
        self.progress_start = None
        self.progress_end = None

    def speak(self, message):
        if message == "Go." and self.go_count == 1:
            self.speech.append(message)
            self.go_count += 1
            def spaced_pinch():
                self.put([(11, 100, 200), (12, 900, 200)])
                threading.Timer(.085, lambda: self.put(
                    [(11, 300, 200), (12, 600, 200)])).start()
            threading.Timer(.03, spaced_pinch).start()
        elif message == "Two fingers detected. Continue without lifting.":
            self.progress_start = time.monotonic()
            time.sleep(.35)
            self.progress_end = time.monotonic()
            super().speak(message)
        else:
            super().speak(message)

events = queue.Queue()
voice = SlowProgressVoice(events)
markers = io.StringIO()
res = live_capture(voice, markers, phases[:2], events, Collector())
assert all(r[1] == "PASS" for r in res)
pinch_pass = [float(line.split("\t")[1])
              for line in markers.getvalue().splitlines()
              if "\tphase-pass\tquick-pinch;" in line]
assert len(pinch_pass) == 1 and voice.progress_start is not None
assert voice.progress_start <= pinch_pass[0] < voice.progress_end, (
    "slow reactive TTS blocked live event processing until voice playback ended")
assert "Two fingers detected. Continue without lifting." in voice.speech

events = queue.Queue()
voice = FakeVoice(events, broken=True)
markers = io.StringIO()
try:
    live_capture(voice, markers, phases[:3], events, Collector())
except RuntimeError as exc:
    assert "tracking" in str(exc).lower(), str(exc)
    assert "INCONCLUSIVE" in str(exc)
else:
    raise AssertionError("lost IDs during the voiced transition produced a false PASS")
assert voice.go_count == 2
assert markers.getvalue().count("\tphase-pass\t") == 2
assert "\tphase-inconclusive\tquick-expand" in markers.getvalue()
assert not any("Detected. Test passed." in v for v in voice.speech[-4:])
print("spoken contact-chain transitions and irreversible ID loss: PASS")
