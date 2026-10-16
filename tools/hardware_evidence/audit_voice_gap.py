#!/usr/bin/env python3
"""Read-only analysis of two-finger ID continuity between spoken test phases.

No sudo, device access, module changes, or raw-coordinate printing.
Uses the original immutable guided session's cues.tsv and live-evdev.jsonl.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys


def markers(path):
    data = []
    with path.open() as source:
        next(source, None)
        for row in source:
            values = row.rstrip("\n").split("\t", 3)
            if len(values) >= 4:
                try:
                    t = float(values[1])
                except ValueError:
                    continue
                data.append((t, values[2], values[3]))
    return data


def run(folder):
    op = folder / "operator"
    marks = markers(op / "cues.tsv")
    events = []
    with (op / "live-evdev.jsonl").open() as source:
        for row in source:
            try:
                item = json.loads(row)
                if item.get("kind") == "frame":
                    events.append(item)
            except (ValueError, TypeError):
                continue

    def lookup(kind, label):
        for t, event, detail in marks:
            if event == kind and detail.startswith(label):
                return t
        raise RuntimeError(f"No {kind} marker for {label!r}")

    p = lookup("phase-pass", "quick-pinch")
    instruction = lookup("phase-instruction", "quick-expand")
    begin = lookup("phase-begin", "quick-expand")
    last_pair = [e for e in events
                 if p - 0.5 <= e.get("monotonic", -1) <= p + .1
                 and len(e.get("contacts", [])) == 2]
    if not last_pair:
        raise RuntimeError("No two-contact frame around accepted pinch")
    pair = set(contact["id"] for contact in last_pair[-1]["contacts"])
    gap = [e for e in events
           if p < e.get("monotonic", -1) <= begin]
    expanded = [e for e in events
                if e.get("monotonic", -1) >= begin]
    outcome = [(t, ev, info) for t, ev, info in marks
               if ev in ("phase-pass", "phase-inconclusive", "phase-retry")
               and ("quick-expand" in info)]
    cutoff = (outcome[-1][0] if outcome else begin + 25)
    expanded = [e for e in expanded if e.get("monotonic", -1) <= cutoff]
    print("=== VOICE-GAP TRACKING AUDIT ===")
    print("Evidence folder:", folder)
    print("Accepted pinch IDs:", sorted(pair))
    print(f"Time from pinch PASS to next instruction: {instruction - p:.2f}s")
    print(f"Time from pinch PASS to expand GO: {begin - p:.2f}s")
    print(f"Frames emitted while instructions played: {len(gap)}")
    tally = Counter()
    first_break = None
    for sample in gap + expanded:
        ids = {c.get("id") for c in sample.get("contacts", [])}
        if not ids:
            kind = "all fingers lifted/no contacts"
        elif len(ids) != 2:
            kind = f"contact-count={len(ids)}"
        elif ids != pair:
            kind = "same count, DIFFERENT tracking IDs"
        else:
            kind = "original pair intact"
        tally[kind] += 1
        if kind != "original pair intact" and first_break is None:
            first_break = (sample["monotonic"] - p, kind, sorted(ids))
    for name, amount in tally.items():
        print(f"  {name}: {amount} frames")
    if first_break:
        at, why, got = first_break
        print(f"FIRST LOSS: {at:+.3f}s after pinch PASS; {why}; IDs={got}")
        print("This proves an evdev discontinuity, but cannot alone "
              "distinguish finger lift from a driver/controller tracking reset.")
    else:
        print("No tracking loss observed in this evidence window.")
    for t, event, detail in outcome:
        print(f"  {event} at {t - p:+.2f}s: {detail}")
    if not outcome:
        print("No expand verdict marker found; session may be incomplete.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_dir", type=Path,
                        help="Previously saved local guided-session folder")
    args = parser.parse_args()
    try:
        return run(args.session_dir)
    except (OSError, RuntimeError) as e:
        print(f"EVIDENCE AUDIT INCOMPLETE: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
