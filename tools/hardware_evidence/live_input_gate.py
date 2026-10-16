#!/usr/bin/env python3
"""Read-only, non-grabbing Linux evdev monitor and physical gesture validator.

The --stream subprocess must run with read access to the selected event node.
It emits a JSON line after each EV_SYN/SYN_REPORT. The Python gate below
uses *actual* MT tracking IDs and positions; a timer alone cannot pass a test.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import time

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT = 0
ABS_X, ABS_Y, ABS_MT_SLOT = 0, 1, 47
ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 53, 54, 57
BTN_TOOL_PEN, BTN_TOUCH = 320, 330
EVENT = struct.Struct("@llHHi")
EVENT_RE = re.compile(r"^/dev/input/event[0-9]+$")


class Decoder:
    """Kernel input_event snapshots; no EVIOCGRAB or device mutation."""

    def __init__(self, source="beta"):
        self.source = source
        self.slot = 0
        self.slots = {}
        self.pos = [None, None]
        self.touch = False
        self.pen = False
        self.frames = 0

    def feed(self, typ, code, value):
        if typ == EV_ABS:
            if code == ABS_MT_SLOT:
                self.slot = value
            elif code == ABS_MT_TRACKING_ID:
                if value == -1:
                    self.slots.pop(self.slot, None)
                else:
                    self.slots[self.slot] = {"id": value, "x": None, "y": None}
            elif code in (ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
                entry = self.slots.get(self.slot)
                if entry is not None:
                    entry["x" if code == ABS_MT_POSITION_X else "y"] = value
            elif code == ABS_X:
                self.pos[0] = value
            elif code == ABS_Y:
                self.pos[1] = value
        elif typ == EV_KEY:
            if code == BTN_TOUCH:
                self.touch = bool(value)
            elif code == BTN_TOOL_PEN:
                self.pen = bool(value)
        elif typ == EV_SYN and code == SYN_REPORT:
            self.frames += 1
            if self.source == "beta":
                contacts = sorted((s.copy() for s in self.slots.values()),
                                  key=lambda s: s["id"])
            else:
                contacts = ([{"id": 1, "x": self.pos[0], "y": self.pos[1]}]
                            if self.touch else [])
            return {"kind": "frame", "monotonic": time.monotonic(),
                    "contacts": contacts, "pen": self.pen,
                    "tip": self.touch, "seq": self.frames}
        return None


def stream(source, device):
    if not EVENT_RE.fullmatch(device):
        raise RuntimeError("device must be a /dev/input/eventN node")
    event_name = Path("/sys/class/input") / Path(device).name / "device/name"
    if not event_name.is_file():
        raise RuntimeError("no matching sysfs input device")
    name = event_name.read_text().strip()
    if source == "beta" and name != "MSHW0231 Touchscreen":
        raise RuntimeError("beta monitor refused mismatched input device: " + name)
    if source == "stylus" and ("Stylus" not in name or "045E:0C19" not in name.upper()):
        raise RuntimeError("stylus monitor refused mismatched input device: " + name)
    if source == "direct" and ("045E:0C19" not in name.upper() or "Stylus" in name):
        raise RuntimeError("direct monitor refused mismatched input device: " + name)
    decoder = Decoder(source)
    print(json.dumps({"kind": "ready", "source": source,
                      "device": device, "name": name}), flush=True)
    with open(device, "rb", buffering=0) as dev:
        partial = b""
        while True:
            data = os.read(dev.fileno(), EVENT.size * 64)
            if not data:
                raise RuntimeError("event device stream closed")
            partial += data
            while len(partial) >= EVENT.size:
                buf, partial = partial[:EVENT.size], partial[EVENT.size:]
                sec, usec, typ, code, value = EVENT.unpack(buf)
                frame = decoder.feed(typ, code, value)
                if frame:
                    frame["event_sec"] = sec
                    frame["event_usec"] = usec
                    print(json.dumps(frame, separators=(",", ":")), flush=True)


def distance(contacts):
    if len(contacts) != 2 or any(c["x"] is None or c["y"] is None
                                 for c in contacts):
        return None
    return math.hypot(contacts[0]["x"] - contacts[1]["x"],
                      contacts[0]["y"] - contacts[1]["y"])


def phase_action(label):
    for prefix in ("quick-", "pinch-", "contacts-"):
        if label.startswith(prefix):
            return label[len(prefix):]
    return label


class GestureGate:
    """Incremental, no-success-by-timeout validator. Each action can retry.

    The context persists *only* the last observed two tracking IDs and their
    distance for continuous close/expand/hold gestures.
    """
    N = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

    def __init__(self, label, context):
        self.label = label
        self.action = phase_action(label)
        self.ctx = context
        self.stage = 0
        self.announced = set()
        self.good = False
        self.started = None
        self.ids = None
        self.origin = None
        self.closest = None
        self.farthest = None
        self.last_point = None
        self.last_contacts = []
        self.first_id = None
        self.counter = 0
        self.hold_since = None
        self.progress = []

    def notice(self, message):
        if message in self.announced:
            return
        self.announced.add(message)
        self.progress.append(message)

    def feed(self, frame):
        self.progress = []
        contacts = frame.get("contacts", [])
        valid = [c for c in contacts if c.get("x") is not None
                 and c.get("y") is not None]
        ids = frozenset(c["id"] for c in valid)
        self.last_contacts = valid
        d = distance(valid)
        now = frame.get("monotonic", time.monotonic())
        a = self.action

        if a in ("one", "repeat") and not self.label.startswith("contacts-"):
            if len(valid) == 1:
                point = (valid[0]["x"], valid[0]["y"])
                if self.origin is None or self.first_id != valid[0]["id"]:
                    self.origin, self.first_id = point, valid[0]["id"]
                elif math.dist(self.origin, point) >= 25:
                    if self.stage == 0:
                        self.stage = 1
                        self.notice("Movement detected. Lift your finger.")
            elif len(valid) == 0 and self.stage == 1:
                self.good = True
                self.ctx["single_completed"] = True

        elif a in self.N and self.label.startswith("contacts-"):
            target = self.N[a]
            if len(valid) == target:
                self.counter += 1
                if self.counter >= 2 and self.stage == 0:
                    self.stage = 1
                    self.notice(f"{target} fingers detected. Lift all fingers now.")
            elif len(valid) == 0 and self.stage == 1:
                self.good = True
            elif self.stage == 0:
                self.counter = 0

        elif a == "far":
            if len(valid) == 2 and d is not None and d > 100:
                self.ctx["pair"] = ids
                self.ctx["distance"] = d
                self.good = True

        elif a in ("pinch", "close", "expand"):
            pair = self.ctx.get("pair")
            if d is not None and len(valid) == 2:
                if a in ("close", "expand") and pair and ids != pair:
                    self.notice("Tracking IDs changed. This attempt is invalid.")
                    return False, self.progress
                if self.origin is None:
                    self.origin = (self.ctx.get("distance") if a == "expand"
                                   else d)
                    self.ids = ids
                    self.notice("Two fingers detected. Continue without lifting.")
                if ids != self.ids:
                    self.notice("Finger tracking IDs changed. Retry this gesture.")
                    return False, self.progress
                required = max(25, self.origin * 0.12)
                if a == "expand" and d >= self.origin + required:
                    self.good = True
                elif a in ("pinch", "close") and d <= self.origin - required:
                    self.good = True
                if self.good:
                    self.ctx["pair"] = ids
                    self.ctx["distance"] = d
            elif self.ids is not None and not self.good:
                # A finger lifted before completing continuous movement.
                self.notice("A finger lifted. Retry without lifting.")

        elif a == "hold":
            if len(valid) == 2 and ids == self.ctx.get("pair"):
                if self.hold_since is None:
                    self.hold_since = now
                    self.origin = d
                elif d is None or abs(d - self.origin) > max(35, self.origin * .10):
                    self.hold_since = now
                    self.origin = d
                elif now - self.hold_since >= 2:
                    self.good = True
            else:
                self.hold_since = None
                if len(valid):
                    self.notice("Keep the same two fingers on the glass.")

        elif a == "lift":
            expected = self.ctx.get("pair")
            if expected is not None and len(valid) == 0:
                self.good = True
                self.ctx.pop("pair", None)
                self.ctx.pop("distance", None)
            elif (expected is None and len(valid) == 0 and
                  (self.ctx.get("single_completed") or
                   self.ctx.get("pen_contact_completed"))):
                self.good = True
                self.ctx.pop("single_completed", None)
                self.ctx.pop("pen_contact_completed", None)
            elif len(valid):
                self.stage = 1

        elif a == "one-lift":
            if self.stage == 0 and len(valid) == 2:
                self.ids = ids
                self.stage = 1
                self.notice("Two fingers detected. Lift only ONE finger now.")
            elif self.stage == 1 and len(valid) == 1 and ids < self.ids:
                self.stage = 2
                self.notice("One finger remains. Lift the LAST finger now.")
            elif self.stage == 2 and len(valid) == 0:
                self.good = True

        elif a == "recontact":
            if self.stage == 0 and len(valid) == 1:
                self.first_id = next(iter(ids))
                self.stage = 1
                self.notice("First touch detected. Lift, then touch again.")
            elif self.stage == 1 and len(valid) == 0:
                self.stage = 2
            elif self.stage == 2 and len(valid) == 1:
                if next(iter(ids)) != self.first_id:
                    self.stage = 3
                    self.notice("New contact detected. Lift your finger.")
            elif self.stage == 3 and len(valid) == 0:
                self.good = True

        elif a == "hover":
            if frame.get("pen") and not frame.get("tip"):
                if self.started is None:
                    self.started = now
                elif now - self.started > .5:
                    self.good = True
            else:
                self.started = None

        elif a == "pen":
            if frame.get("pen") and frame.get("tip"):
                if self.started is None:
                    self.started = now
                elif now - self.started > .5:
                    self.good = True
                    self.ctx["pen_contact_completed"] = True
            else:
                self.started = None

        return self.good, self.progress


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stream", action="store_true")
    p.add_argument("--source", choices=("beta", "direct", "stylus"), default="beta")
    p.add_argument("--device", required=True)
    args = p.parse_args()
    if not args.stream:
        p.error("--stream is required")
    try:
        stream(args.source, args.device)
    except Exception as e:
        print("INPUT MONITOR ERROR: " + str(e), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
