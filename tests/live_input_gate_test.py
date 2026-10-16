#!/usr/bin/env python3
"""Behavioral tests: never advance a hardware phase on time or node registration."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/hardware_evidence"))
from live_input_gate import (
    Decoder, GestureGate, EV_ABS, EV_SYN, EV_KEY,
    ABS_MT_SLOT, ABS_MT_TRACKING_ID, ABS_MT_POSITION_X,
    ABS_MT_POSITION_Y, SYN_REPORT, BTN_TOUCH, BTN_TOOL_PEN,
)


def frame(points, t=0, pen=False, tip=False):
    return {"kind": "frame", "monotonic": t,
            "contacts": [{"id": k, "x": x, "y": y}
                         for k, x, y in points],
            "pen": pen, "tip": tip}


def send(gate, points, t=0, pen=False, tip=False):
    return gate.feed(frame(points, t, pen, tip))[0]


# Decode the exact EV_ABS/EV_SYN Linux API, including release.
d = Decoder()
assert d.feed(EV_ABS, ABS_MT_SLOT, 0) is None
d.feed(EV_ABS, ABS_MT_TRACKING_ID, 51)
d.feed(EV_ABS, ABS_MT_POSITION_X, 300)
d.feed(EV_ABS, ABS_MT_POSITION_Y, 450)
assert d.feed(EV_SYN, SYN_REPORT, 0)["contacts"] == [
    {"id": 51, "x": 300, "y": 450}]
d.feed(EV_ABS, ABS_MT_TRACKING_ID, -1)
assert d.feed(EV_SYN, SYN_REPORT, 0)["contacts"] == []

ctx = {}
one = GestureGate("quick-one", ctx)
assert not send(one, [], 1)
assert not send(one, [(1, 150, 150)], 2)
assert not send(one, [(1, 153, 150)], 3)  # no movement
assert not send(one, [(1, 210, 150)], 4)  # moved, but not released
assert send(one, [], 5)
assert ctx["single_completed"]

pinch = GestureGate("quick-pinch", ctx)
assert not send(pinch, [(11, 100, 100)], 6)  # one finger != two
assert not send(pinch, [(11, 100, 100), (12, 1000, 100)], 7)
assert not send(pinch, [(11, 120, 100), (12, 970, 100)], 8)
assert send(pinch, [(11, 275, 100), (12, 675, 100)], 9)
assert ctx["pair"] == frozenset((11, 12))

expand = GestureGate("quick-expand", ctx)
assert not send(expand, [(11, 275, 100), (12, 675, 100)], 10)
assert not send(expand, [(11, 100, 100), (13, 800, 100)], 11)  # ID change
assert expand.failed_reason, "lost contact IDs must hard-veto the attempt"
assert not send(expand, [(11, 100, 100), (12, 900, 100)], 12), (
    "a failed continuation must not be resurrected")
expand = GestureGate("quick-expand", ctx)  # only for independent gate unit coverage
assert not send(expand, [(11, 275, 100), (12, 675, 100)], 11.5)
assert send(expand, [(11, 100, 100), (12, 900, 100)], 12)
lift = GestureGate("quick-lift", ctx)
assert not send(lift, [], 12.5), "early lift must not pass merely because pair was stored"
assert not send(lift, [(11, 100, 100), (12, 900, 100)], 13)
assert send(lift, [], 14), "must see SAME pair down then released"

# Dedicated continuity hold, and no pass on changed tracking IDs.
g = GestureGate("pinch-far", ctx)
assert send(g, [(15, 100, 100), (16, 1100, 100)], 15)
# Starting release with the last stored pair but no fresh DOWN frame is
# never a PASS, even if the operator lifted during spoken instructions.
early = GestureGate("pinch-lift", ctx)
assert not send(early, [], 15.5)

g = GestureGate("pinch-close", ctx)
assert not send(g, [(15, 100, 100), (16, 1100, 100)], 16)
assert send(g, [(15, 350, 100), (16, 780, 100)], 17)
g = GestureGate("pinch-hold", ctx)
assert not send(g, [(15, 350, 100), (16, 780, 100)], 18)
assert not send(g, [(15, 350, 100), (17, 780, 100)], 19)
assert g.failed_reason, "a hold phase cannot ignore changed IDs"
assert not send(g, [(15, 350, 100), (16, 780, 100)], 20)
# New gate after explicit operator restart can succeed with continuous IDs.
g = GestureGate("pinch-hold", ctx)
assert not send(g, [(15, 350, 100), (16, 780, 100)], 20)
assert send(g, [(15, 350, 100), (16, 780, 100)], 22.5)

# Contact count must be observed, then *every finger* released.
for word, n in [("one",1), ("two",2), ("three",3), ("four",4), ("five",5)]:
    test = GestureGate("contacts-"+word, {})
    coords = [(i, 50*i, 20) for i in range(1, n+1)]
    assert not send(test, coords, 0)
    assert not send(test, coords, 1)
    assert send(test, [], 2)

ctx2 = {}
one_lift = GestureGate("contacts-one-lift", ctx2)
assert not send(one_lift, [(21, 100, 100), (22, 300, 100)], 1)
assert not send(one_lift, [(21, 120, 100)], 2)
assert send(one_lift, [], 3)

recontact = GestureGate("contacts-recontact", {})
assert not send(recontact, [(31, 10, 10)], 1)
assert not send(recontact, [], 2)
assert not send(recontact, [(31, 10, 10)], 3)  # old ID is not new contact
assert not send(recontact, [(32, 10, 10)], 4)
assert send(recontact, [], 5)

pctx = {}
hover = GestureGate("hover", pctx)
assert not send(hover, [], 0, pen=True, tip=False)
assert send(hover, [], 1, pen=True, tip=False)
pen = GestureGate("pen", pctx)
assert not send(pen, [], 2, pen=True, tip=True)
assert send(pen, [], 3, pen=True, tip=True)
pen_lift = GestureGate("lift", pctx)
assert send(pen_lift, [], 4, pen=False, tip=False)

print("live evdev decode and 1–5 finger / gesture verification: PASS")
