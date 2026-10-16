#!/usr/bin/env python3
"""Explain one saved multi-touch release, including voice cue timing.

No root/device/driver access. Never outputs coordinates, wall-clock times,
raw event streams or personal data. This uses read-only saved evidence.
Observer monotonic clock can be compared with Python cue timestamps;
kernel event timestamps are used ONLY for kernel-event-to-event gaps.
"""
import argparse
from pathlib import Path
import sys

from release_timing_report import load, last_marker


def examine(session):
    cues, frames = load(session)
    expand = (last_marker(cues, "phase-pass", "expand")
              or last_marker(cues, "phase-pass", "quick-expand")
              or last_marker(cues, "phase-pass", "pinch-expand"))
    if expand is None:
        raise ValueError("no accepted expansion phase")
    lift_label = next(
        (label for label in ("lift", "quick-lift", "pinch-lift")
         if last_marker(cues, "phase-pass", label, after=expand) is not None),
        None)
    if lift_label is None:
        raise ValueError("no completed lift phase after expansion")
    passed = last_marker(cues, "phase-pass", lift_label, after=expand)
    near = [f for f in frames if expand - 10 <= f[0] <= expand + .1
            and len(f[1]) == 2]
    if not near:
        raise ValueError("no original two-finger frame near expansion PASS")
    pair = near[-1][1]
    frames = [f for f in frames if expand < f[0] <= passed + .1]
    first_one = first_zero = None
    prior = pair
    anomalies = set()
    for f in frames:
        t, ids, k = f
        if not ids.issubset(pair):
            anomalies.add("unexpected contact ID")
        if not ids.issubset(prior):
            anomalies.add("reappeared tracking ID")
        if first_one is None and ids < pair and len(ids) == 1:
            first_one = f
        if first_zero is None and not ids:
            first_zero = f
        prior = ids
    if first_one is None or first_zero is None:
        raise ValueError("no complete 2 -> 1 -> 0 evdev event chain")
    t1, _, k1 = first_one
    t0, _, k0 = first_zero
    if t0 < t1:
        raise ValueError("release order inconsistent")
    progress = [t for t, event, detail in cues
                if event == "gesture-progress" and
                detail.startswith(lift_label + ":One original finger remains")]
    instruction = [t for t, event, detail in cues
                   if event == "phase-instruction" and
                   detail.startswith(lift_label + ";")]
    start = [t for t, event, detail in cues
             if event == "phase-begin" and
             detail.startswith(lift_label + ";")]
    output = [
        "=== TWO-FINGER RELEASE / VOICE CUE TIMING ===",
        f"Session: {session}",
        f"Source: recorded original tracking IDs at expansion PASS",
        f"Kernel reported first release -> second: "
        + (f"{(k0-k1)*1000:.3f} ms" if k1 is not None and k0 is not None
           else "not measurable"),
        f"Independent event observer first -> second: {(t0-t1)*1000:.3f} ms",
        f"First original ID dropped: observer-relative +0.000 ms",
        f"All original IDs gone: observer-relative +{(t0-t1)*1000:.3f} ms",
    ]
    for label, events in [
        ("'Lift both fingers' instruction queued", instruction),
        ("Lift phase marked begin", start),
        ("Intermediate singleton voice progress cue logged", progress),
        ("Final gesture PASS cue", [passed])
    ]:
        for t in events[-2:]:
            delta = (t-t1)*1000
            output.append(f"{label}: {delta:+.3f} ms from first release observation")
            if label == "Intermediate singleton voice progress cue logged":
                after = (t-t0)*1000
                output.append(
                    "  voice-cue mark AFTER final 0-contact frame by "
                    f"{after:.3f} ms" if after >= 0 else
                    f"  final 0-contact frame recorded {-after:.3f} ms AFTER voice-cue mark"
                )
    if progress:
        # Auditable conclusion: progress cue is logged before TTS playback.
        # A cue AFTER the final 0-contact frame cannot have caused the
        # preceding 2->1->0 input-event interval.
        after_final = (progress[-1] - t0) * 1000
        if after_final >= 0:
            output.append(
                "TIMELINE VERDICT: the intermediate 'one finger remains' "
                "announcement was QUEUED AFTER both releases had already "
                "been recorded, by "
                f"{after_final:.3f} ms. It cannot explain the earlier "
                "first-to-last evdev release interval."
            )
        else:
            output.append(
                "TIMELINE VERDICT: the intermediate cue was logged BEFORE "
                "the final release; timing alone cannot show whether the "
                "spoken instruction affected the operator's lift."
            )
        # Cue-processing delay is NOT touchscreen latency.
        output.append(
            f"Gesture PASS recorded {(passed-t0)*1000:.3f} ms "
            "AFTER the final zero-contact input frame."
        )
    output += [
        "Tracking-ID anomalies: " + (", ".join(sorted(anomalies)) if anomalies else "none observed"),
        "The progress cue is marked BEFORE speech synthesis playback; this",
        "does not timestamp hearing or actual fingertip separation.",
        "Kernel event-to-event gaps are not physical touch release latency.",
        "Do not conclude a driver bug or physical lift time from a queued voice cue."
    ]
    for line in output:
        print(line)
    return 1 if anomalies else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path, help="individual saved cycle-*-quick capture")
    args = parser.parse_args()
    try:
        return examine(args.session.expanduser())
    except (OSError, ValueError, TypeError) as exc:
        print(f"RELEASE DETAIL INCOMPLETE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
