#!/usr/bin/env python3
"""Read-only release-timing report across existing SL4A guided captures.

One command audits the already saved quick/pinch gesture recordings.
Reports Linux event release intervals, not physical finger-off latency.
Does not modify modules, files, evdev, permissions, or boot configuration.
Does not output finger coordinates or raw gesture history.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import statistics
import sys


PAIRS = {"quick-lift": "quick-expand", "pinch-lift": "pinch-expand"}


def load(session):
    op = session / "operator"
    cues_path, evdev_path = op / "cues.tsv", op / "live-evdev.jsonl"
    if not cues_path.is_file() or not evdev_path.is_file():
        raise ValueError("missing operator/cues.tsv or operator/live-evdev.jsonl")
    cues = []
    for row in cues_path.read_text().splitlines()[1:]:
        columns = row.split("\t", 3)
        if len(columns) == 4:
            try:
                cues.append((float(columns[1]), columns[2], columns[3]))
            except ValueError:
                pass
    frames = []
    with evdev_path.open() as reader:
        for lineno, row in enumerate(reader, 1):
            try:
                frame = json.loads(row)
            except ValueError as exc:
                raise ValueError(f"invalid JSONL at line {lineno}") from exc
            if frame.get("kind") != "frame":
                continue
            try:
                t = float(frame["monotonic"])
                ids = frozenset(int(c["id"]) for c in frame["contacts"])
                # event_sec/usec originate at kernel evdev SYN_REPORT, more
                # direct than Python observer processing time. Use as a
                # paired check, never presume a clock source across boots.
                kt = (int(frame["event_sec"]) +
                      int(frame["event_usec"]) / 1e6
                      if "event_sec" in frame and "event_usec" in frame
                      else None)
            except (KeyError, ValueError, TypeError) as exc:
                raise ValueError(f"invalid frame at line {lineno}") from exc
            if not math.isfinite(t) or (kt is not None and not math.isfinite(kt)):
                raise ValueError("non-finite timestamp")
            frames.append((t, ids, kt))
    if not frames:
        raise ValueError("no evdev SYN_REPORT frames in capture")
    if any(b[0] < a[0] for a, b in zip(frames, frames[1:])):
        raise ValueError("non-monotonic observer clock in event stream")
    return cues, frames


def last_marker(cues, kind, label, after=None):
    found = [t for t, event, detail in cues
             if event == kind and detail.startswith(label + ";")
             and (after is None or t >= after)]
    return found[-1] if found else None


def analyze(session):
    cues, frames = load(session)
    results = []
    for lift_label, expand_label in PAIRS.items():
        expand = last_marker(cues, "phase-pass", expand_label)
        if expand is None:
            continue
        lift = last_marker(cues, "phase-pass", lift_label, after=expand)
        inconclusive = last_marker(cues, "phase-inconclusive", lift_label,
                                   after=expand)
        if lift is None and inconclusive is None:
            results.append({"phase": lift_label, "status": "MISSING_LIFT_VERDICT"})
            continue
        stop = min(lift, inconclusive) if lift is not None and inconclusive is not None else (
            lift if lift is not None else inconclusive)
        pair_frames = [f for f in frames if expand - 10 <= f[0] <= expand + .1
                       and len(f[1]) == 2]
        if not pair_frames:
            results.append({"phase": lift_label, "status": "MISSING_PAIR_FRAME"})
            continue
        pair = pair_frames[-1][1]
        window = [f for f in frames if expand < f[0] <= stop + .1]
        previous = pair
        partial_time = complete_time = None
        partial_kernel = complete_kernel = None
        violations = []
        for t, ids, kt in window:
            if ids == previous:
                continue
            if not ids.issubset(pair):
                violations.append("NEW_ID")
            if not ids.issubset(previous):
                violations.append("REAPPEARED_ID")
            if partial_time is None and len(ids) == 1 and ids < pair:
                partial_time, partial_kernel = t, kt
            if complete_time is None and not ids:
                complete_time, complete_kernel = t, kt
            previous = ids
        status = ("TRACKING_ANOMALY" if violations else
                  "INCOMPLETE" if lift is None or complete_time is None else
                  "SEQUENTIAL_RELEASE" if partial_time is not None else
                  "DIRECT_RELEASE")
        observer_gap = ((complete_time - partial_time) * 1000
                        if partial_time is not None and complete_time is not None else None)
        kernel_gap = ((complete_kernel - partial_kernel) * 1000
                      if partial_kernel is not None and complete_kernel is not None else None)
        # Should not give a bogus 0ms if the first intermediate event was
        # never observed, or invent human finger-lift timestamps.
        results.append({"phase": lift_label, "status": status,
                        "observer_gap_ms": observer_gap,
                        "kernel_gap_ms": kernel_gap,
                        "violations": sorted(set(violations)),
                        "intermediate_announced": any(
                            e == "gesture-progress" and
                            detail.startswith(lift_label + ":One original finger remains")
                            for _, e, detail in cues)})
    return results


def candidates(root):
    root = root.expanduser()
    if root.is_dir() and (root / "operator/live-evdev.jsonl").is_file():
        return [root]
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    return sorted({p.parent.parent for p in root.rglob("operator/live-evdev.jsonl")
                   if ("pr87-" in str(p) or "mode4-" in str(p))})


def report(roots, threshold=100.0, output=None):
    rows = []
    for root in roots:
        for session in candidates(root):
            try:
                measures = analyze(session)
                for entry in measures:
                    entry["session"] = str(session)
                    rows.append(entry)
            except (OSError, ValueError) as exc:
                rows.append({"session": str(session), "phase": "-",
                             "status": f"UNREADABLE: {exc}"})
    lines = ["=== SAVED TWO-FINGER RELEASE TIMING (READ-ONLY) ===",
             "Linux input release interval (first tracked ID gone -> second gone).",
             "This is NOT physical finger-off latency or proof of driver correctness.",
             "Threshold is a REVIEW CUE, not a pass/fail specification.",
             ""]
    numeric = []
    counts = Counter()
    for row in rows:
        status = row["status"]
        counts[status] += 1
        gap = row.get("kernel_gap_ms")
        source = "kernel"
        if gap is None:
            gap, source = row.get("observer_gap_ms"), "observer"
        if gap is not None:
            numeric.append(gap)
            result = f"{gap:.3f} ms ({source})"
            if gap >= threshold:
                result += "  [REVIEW_GAP]"
        else:
            result = "not measurable"
        note = "intermediate voice recorded" if row.get("intermediate_announced") else ""
        if row.get("violations"):
            note = ",".join(row["violations"])
        lines.append(f"{row['session']}: {row['phase']} | {status} | "
                     f"first->last={result} {note}")
    lines.append("")
    lines.append(f"Analyzed {len(rows)} release-phase result(s). " +
                 ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    if numeric:
        vals = sorted(numeric)
        lines.append(f"Measured sequential gaps: n={len(vals)}, "
                     f"median={statistics.median(vals):.3f} ms, "
                     f"p95-nearest-rank={vals[math.ceil(.95 * len(vals))-1]:.3f} ms, "
                     f"maximum={vals[-1]:.3f} ms")
    lines.append("Do not share raw traces if only aggregate metrics are needed.")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if output is not None:
        output.write_text(text)
        print(f"Summary written to: {output}")
    return 1 if not rows or any(
        r["status"].startswith(("UNREADABLE", "MISSING", "INCOMPLETE",
                                "TRACKING_ANOMALY")) for r in rows) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help=(
        "Existing session directories or enclosing hardware-runs directory. "
        "Defaults to ~/sl4a-hardware-runs (PR87 and mode4 only)."))
    parser.add_argument("--review-ms", type=float, default=100.0,
                        help="screening gap threshold, not failure limit (default 100)")
    parser.add_argument("--output", type=Path, help="optional text report destination")
    args = parser.parse_args()
    if not math.isfinite(args.review_ms) or args.review_ms < 0:
        parser.error("--review-ms must be nonnegative and finite")
    try:
        return report(args.paths or [Path("~/sl4a-hardware-runs")],
                      args.review_ms, args.output)
    except (OSError, ValueError) as exc:
        print(f"RELEASE REPORT INCOMPLETE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
