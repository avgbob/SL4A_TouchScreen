#!/usr/bin/env python3
"""Read-only audit of real two-finger release in a saved voiced session.

Distinguishes original pair -> original singleton -> none (valid release)
from an unexpected new contact tracking ID. Reports IDs/times, never
raw touchscreen coordinates. Does not load or change the driver.
"""
import argparse
import json
from pathlib import Path
import sys


def load(session):
    base = Path(session) / "operator"
    cues = []
    with (base / "cues.tsv").open() as file:
        next(file, None)
        for line in file:
            columns = line.rstrip("\n").split("\t", 3)
            if len(columns) != 4:
                continue
            try:
                cues.append((float(columns[1]), columns[2], columns[3]))
            except ValueError:
                continue
    frames = []
    with (base / "live-evdev.jsonl").open() as file:
        for line in file:
            try:
                frame = json.loads(line)
                if frame.get("kind") == "frame":
                    frames.append(frame)
            except (TypeError, ValueError):
                continue
    return cues, frames


def inspect(session, label="pinch-lift"):
    cues, frames = load(session)
    preceding = ("pinch-expand" if label == "pinch-lift"
                 else "quick-expand")
    previous = [(t, detail) for t, ev, detail in cues
                if ev == "phase-pass" and detail.startswith(preceding + ";")]
    if not previous:
        raise RuntimeError("preceding two-finger expansion PASS not recorded")
    earlier = previous[-1][0]
    two = [x for x in frames if earlier - .5 <= x.get("monotonic", -1) <= earlier + .1
           and len(x.get("contacts", [])) == 2]
    if not two:
        raise RuntimeError("no two-contact evdev frame near expansion PASS")
    expected = frozenset(x["id"] for x in two[-1]["contacts"])
    steps = [(t, kind, detail) for t, kind, detail in cues
             if (kind in ("phase-instruction", "phase-begin", "phase-inconclusive")
                 and detail.startswith(label + ";"))]
    if not steps:
        raise RuntimeError("release phase markers missing")
    first_instruction = next((t for t,k,_ in steps if k=="phase-instruction"), None)
    begin = next((t for t,k,_ in steps if k=="phase-begin"), None)
    inconclusive = next((t for t,k,_ in steps if k=="phase-inconclusive"), None)
    stop = inconclusive if inconclusive is not None else earlier + 35
    if stop < earlier:
        raise RuntimeError("release event markers out of order")
    sample = [x for x in frames if earlier < x.get("monotonic", -1) <= stop]
    transitions = []
    previous_ids = expected
    for x in sample:
        ids = frozenset(y["id"] for y in x.get("contacts", []))
        if ids != previous_ids:
            t = x["monotonic"] - earlier
            if not ids:
                label_kind = "EMPTY: both contacts released"
            elif ids.issubset(expected):
                if ids.issubset(previous_ids):
                    label_kind = "ORIGINAL ID subset: normal partial release"
                else:
                    label_kind = "REAPPEARANCE of previously released ID"
            else:
                label_kind = "UNEXPECTED NEW tracking ID"
            transitions.append((t, label_kind, sorted(ids)))
            previous_ids = ids

    print("=== SAVED TWO-FINGER RELEASE AUDIT ===")
    print("Session:", session)
    print("Phase:", label)
    print("Original verified pair:", sorted(expected))
    print("Voice instruction after expansion:",
          "missing" if first_instruction is None
          else f"+{first_instruction-earlier:.3f}s")
    print("Release phase began:",
          "missing" if begin is None else f"+{begin-earlier:.3f}s")
    print("Release outcome:", "INCONCLUSIVE" if inconclusive is not None
          else "no inconclusive marker")
    print("Evdev frames in window:", len(sample))
    print("Transitions (originally seen pair -> end of saved release window):")
    for time_delta, kind, ids in transitions[:14]:
        print(f"  +{time_delta:.3f}s: {kind}; IDs={ids}")
    if len(transitions) > 14:
        print(f"  ... {len(transitions)-14} later transitions omitted")
    if any("UNEXPECTED NEW" in item[1] for item in transitions):
        print("VERDICT: New tracking ID observed; needs separate driver/hand review.")
    elif any("REAPPEARANCE" in item[1] for item in transitions):
        print("VERDICT: Original ID reappeared after a partial release; review.")
    elif any("ORIGINAL ID subset" in item[1] for item in transitions):
        print("VERDICT: Normal partial original-ID release observed. "
              "Old test verifier would have falsely rejected this intermediate frame.")
    elif any("EMPTY" in item[1] for item in transitions):
        print("VERDICT: Full release with no partial-ID frame observed.")
    else:
        print("VERDICT: Incomplete trace or no change observed in release window.")
    print("No raw touchscreen coordinates were printed.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path)
    parser.add_argument("--phase", choices=("pinch-lift","quick-lift"),
                        default="pinch-lift")
    args = parser.parse_args()
    try:
        return inspect(args.session_dir, args.phase)
    except (OSError, RuntimeError, KeyError) as error:
        print("RELEASE AUDIT INCOMPLETE:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
