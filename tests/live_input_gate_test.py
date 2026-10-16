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

# Physical 2026-10-16 pinch-lift regression: a real lift usually reports
# both original fingers -> ONE original finger -> none. This MUST PASS.
sequential = GestureGate("pinch-lift", {"pair": frozenset((41, 42))})
assert not send(sequential, [], 0), "no initial pair must not pass"
assert not send(sequential, [(41, 100, 100), (42, 900, 100)], 1)
assert not send(sequential, [(41, 100, 100)], 2), (
    "one original finger during lift is valid but not complete")
assert send(sequential, [], 3), "both original fingers now lifted"

# live_capture prearms the release from the preceding verified pair;
# releasing one contact while a voice instruction plays must be accepted.
prearmed = GestureGate("quick-lift", {"pair": frozenset((51, 52))})
prearmed.stage = 1
assert not send(prearmed, [(52, 900, 100)], 1)
assert send(prearmed, [], 2)

# Reject an unexpected *new* tracking ID, and reappearance of an old
# released ID, even if the eventual contact count reaches zero.
unexpected = GestureGate("pinch-lift", {"pair": frozenset((61, 62))})
unexpected.stage = 1
assert not send(unexpected, [(61, 100, 100), (99, 900, 100)], 1)
assert unexpected.failed_reason
assert not send(unexpected, [], 2), "invalid lift remains invalid"
reappear = GestureGate("pinch-lift", {"pair": frozenset((71, 72))})
reappear.stage = 1
assert not send(reappear, [(71, 100, 100)], 1)
assert not send(reappear, [(71, 100, 100), (72, 900, 100)], 2)
assert reappear.failed_reason
assert not send(reappear, [], 3)

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

# The *remaining seven* hardware cases must verify stable counts and
# sequential original-ID release; do not accept a fleeting phantom count.
five = GestureGate("contacts-five", {})
ids5 = [(i, i * 80, 150) for i in range(1, 6)]
assert not send(five, ids5, 1)
assert not send(five, [(i + 30, i * 80, 150) for i in range(1, 6)], 2), (
    "a replaced set of IDs must restart the count confirmation")
assert not send(five, ids5, 3)
assert five.stage == 0
assert not send(five, ids5, 4)
assert five.stage == 1
assert not send(five, ids5[:4], 5), "partial original release cannot PASS"
assert not send(five, ids5[:2], 6)
assert send(five, [], 7), "normal 5 -> 4 -> 2 -> 0 release must PASS"

unexpected_count = GestureGate("contacts-three", {})
assert not send(unexpected_count, ids5[:3], 1)
assert not send(unexpected_count, ids5[:3], 2)
assert not send(unexpected_count, [(1,80,150),(2,160,150),(99,240,150)], 3)
assert unexpected_count.failed_reason
assert not send(unexpected_count, [], 4), "unexpected ID cannot resurrect"

reappear_count = GestureGate("contacts-two", {})
assert not send(reappear_count, ids5[:2], 1)
assert not send(reappear_count, ids5[:2], 2)
assert not send(reappear_count, ids5[:1], 3)
assert not send(reappear_count, ids5[:2], 4)
assert reappear_count.failed_reason

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
