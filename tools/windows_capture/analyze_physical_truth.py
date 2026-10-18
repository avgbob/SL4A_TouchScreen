#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Analyze operator-confirmed physical contact states in paired SL4A V3/V4 logs.

Read-only. This is NOT an independent instrument measuring fingers on glass:
state changes are user key annotations with unknown human reaction latency.
Use a conservative delay after marks and truncate before the next mark.
Corrected intervals remain in raw evidence but are excluded from metrics.
Guided V4 explicitly terminates every two-second labelled hold with UNKNOWN.
"""
from __future__ import annotations

import argparse
import csv
import json
from bisect import bisect_left
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STATES = {
    "OPERATOR_BOTH_DOWN": 2,
    "OPERATOR_BOTH_STILL_DOWN": 2,
    "OPERATOR_SECOND_RETURNED": 2,
    "OPERATOR_SECOND_INTENTIONALLY_LIFTED": 1,
    "OPERATOR_BOTH_LIFTED": 0,
}
GUIDED_STATES = {
    "OPERATOR_CONFIRM_EMPTY_START": 0,
    "OPERATOR_CONFIRM_HORIZONTAL_TWO_APART": 2,
    "OPERATOR_CONFIRM_HORIZONTAL_CLOSE_BOTH_DOWN": 2,
    "OPERATOR_CONFIRM_HORIZONTAL_LEFT_LIFTED": 1,
    "OPERATOR_CONFIRM_HORIZONTAL_RIGHT_ONLY": 1,
    "OPERATOR_CONFIRM_HORIZONTAL_LEFT_RETURNED": 2,
    "OPERATOR_CONFIRM_HORIZONTAL_RIGHT_LIFTED": 1,
    "OPERATOR_CONFIRM_HORIZONTAL_LEFT_ONLY": 1,
    "OPERATOR_CONFIRM_HORIZONTAL_RIGHT_RETURNED": 2,
    "OPERATOR_CONFIRM_HORIZONTAL_TWO_APART_AGAIN": 2,
    "OPERATOR_CONFIRM_EMPTY_BETWEEN_TRIALS": 0,
    "OPERATOR_CONFIRM_VERTICAL_TWO_APART": 2,
    "OPERATOR_CONFIRM_VERTICAL_CLOSE_LIGHT": 2,
    "OPERATOR_CONFIRM_VERTICAL_CLOSE_FIRM": 2,
    "OPERATOR_CONFIRM_VERTICAL_TOP_LIFTED": 1,
    "OPERATOR_CONFIRM_VERTICAL_BOTTOM_ONLY": 1,
    "OPERATOR_CONFIRM_VERTICAL_TOP_RETURNED": 2,
    "OPERATOR_CONFIRM_VERTICAL_TWO_APART_AGAIN": 2,
    "OPERATOR_CONFIRM_EMPTY_FINISH": 0,
}
ALL_STATES = {**STATES, **GUIDED_STATES}
INVALID = "OPERATOR_ANNOTATION_INVALIDATED"
UNKNOWN = "OPERATOR_TRANSITION_UNKNOWN"


def utc_seconds(value: str) -> float:
    if not value:
        raise ValueError("empty UTC timestamp")
    t = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise ValueError("timezone missing from UTC event")
    return t.timestamp()


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def evaluate(events: list[dict], samples: list[dict], *, guard_after=0.35,
             guard_before=0.15, min_run=0.3) -> dict:
    if guard_after < 0 or guard_before < 0 or min_run < 0:
        raise ValueError("guard intervals cannot be negative")
    marks = []
    pointer_counts = Counter()
    last_time = float('-inf')
    for row in events:
        when = utc_seconds(row.get("Utc", ""))
        if when < last_time:
            raise ValueError("events not sorted")
        last_time = when
        kind = row.get("Event", "")
        if kind == "DOWN" or kind == "UP":
            pointer_counts[kind] += 1
        if kind in ALL_STATES or kind in (INVALID, UNKNOWN):
            physical = int(row.get("OperatorPhysical", "-1"))
            expected = ALL_STATES.get(kind, -1)
            if physical != expected:
                raise ValueError(f"inconsistent operator label: {kind} physical={physical}")
            marks.append({"timestamp": when, "event": kind, "physical": physical,
                          "stage": row.get("Stage", ""),
                          "windows_at_key": int(row.get("MessageActive", "-1"))})
    if not marks:
        raise ValueError("no V3/V4 physical state markers")
    if not samples:
        raise ValueError("no periodic pointer samples")
    sampled = []
    last_time = float('-inf')
    for row in samples:
        when = utc_seconds(row.get("Utc", ""))
        if when < last_time:
            raise ValueError("samples not sorted")
        last_time = when
        count = int(row.get("MessageActive", "-1"))
        if count < 0:
            raise ValueError("missing Windows active pointer count")
        sampled.append((when, count, row.get("Stage", "")))
    samples_t = [x[0] for x in sampled]
    summaries = []
    aggregate = Counter()
    longest_by_class = Counter()
    excluded_by_correction = 0
    for idx, mark in enumerate(marks):
        if mark["event"] in (INVALID, UNKNOWN):
            continue
        next_mark = marks[idx + 1] if idx + 1 < len(marks) else None
        # X invalidates the preceding annotated interval, never rewriting raw CSV.
        if next_mark and next_mark["event"] == INVALID:
            excluded_by_correction += 1
            continue
        end = next_mark["timestamp"] if next_mark else sampled[-1][0]
        start_safe = mark["timestamp"] + guard_after
        end_safe = end - guard_before
        lo = bisect_left(samples_t, start_safe)
        hi = max(lo, bisect_left(samples_t, end_safe))
        truth = mark["physical"]
        counts = Counter(x[1] for x in sampled[lo:hi])
        mismatches = 0
        longest = 0.0
        run_start = None
        run_end = None
        last_sample = None
        all_runs = []
        for t, count, _ in sampled[lo:hi]:
            mismatch = count != truth
            if mismatch:
                mismatches += 1
                # Don't bridge gaps in samples or convert discontinuities into durations.
                if run_start is None or (last_sample is not None and t - last_sample > .25):
                    if run_start is not None:
                        all_runs.append(max(0.0, (run_end or run_start) - run_start))
                    run_start = t
                run_end = t
            elif run_start is not None:
                all_runs.append(max(0.0, (run_end or run_start) - run_start))
                run_start = None
                run_end = None
            last_sample = t
        if run_start is not None:
            all_runs.append(max(0.0, (run_end or run_start) - run_start))
        longest = max(all_runs, default=0.)
        classification = {0: "ghost_after_all_lifted", 1: "ghost_or_lost_when_one_physical",
                          2: "missing_second_while_both_physical"}[truth]
        # One physically down: report whether Windows showed 0 OR 2 separately.
        if truth == 1:
            classification = "one_finger_control"
        summaries.append({
            "event": mark["event"], "stage": mark["stage"], "physical": truth,
            "seconds_between_marks": round(end-mark["timestamp"], 3),
            "seconds_in_conservative_window": round(max(0, end_safe-start_safe), 3),
            "samples_evaluated": hi-lo, "windows_count_histogram": dict(sorted(counts.items())),
            "windows_mismatch_samples": mismatches,
            "longest_continuous_mismatch_seconds_approx": round(longest, 3),
            "sustained_mismatch_at_least_min_run": longest >= min_run,
            "classification": classification,
        })
        aggregate["samples_evaluated"] += hi-lo
        aggregate["mismatch_samples"] += mismatches
        if longest >= min_run:
            aggregate["intervals_with_sustained_mismatch"] += 1
            longest_by_class[classification] = max(longest_by_class[classification],longest)
        if truth == 2:
            aggregate["two_physical_one_windows_samples"] += counts.get(1,0)
            aggregate["two_physical_zero_windows_samples"] += counts.get(0,0)
        elif truth == 0:
            aggregate["zero_physical_nonzero_windows_samples"] += sum(v for k,v in counts.items() if k)
        else:
            aggregate["one_physical_zero_windows_samples"] += counts.get(0,0)
            aggregate["one_physical_two_plus_windows_samples"] += sum(v for k,v in counts.items() if k>1)
    return {
        "status": "HUMAN_ANNOTATED_PHYSICAL_STATES_NOT_INDEPENDENT_SENSOR_TRUTH",
        "guard_after_seconds": guard_after, "guard_before_seconds": guard_before,
        "minimum_sustained_run_seconds": min_run,
        "operator_markers": sum(m["event"] not in (INVALID, UNKNOWN) for m in marks),
        "transition_boundaries": sum(m["event"] == UNKNOWN for m in marks),
        "raw_annotation_events": len(marks),
        "corrected_intervals_excluded": excluded_by_correction,
        "os_event_lifetimes": dict(pointer_counts), "stage_intervals": summaries,
        "totals": dict(aggregate),
        "longest_mismatch_seconds_by_class": {k:round(v,3) for k,v in longest_by_class.items()},
        "warnings": [
            "An operator keypress is not the exact moment a finger physically lifts/lands.",
            "The sensor and OS timebases require an independent clock map for frame-exact claims.",
            "V3 labels can remain stale; V4 ends each labelled hold with an explicit unknown transition.",
            "The OS pointer counts are Windows application-visible, not raw controller contact identities.",
            "No external finger video or synchronized hardware switch was captured.",
        ],
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--samples", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--guard-after", type=float, default=0.35)
    p.add_argument("--guard-before", type=float, default=0.15)
    args = p.parse_args(argv)
    result = evaluate(read_csv(args.events), read_csv(args.samples),
                      guard_after=args.guard_after, guard_before=args.guard_before)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status": result["status"], "operator_markers":result["operator_markers"],
        "intervals":len(result["stage_intervals"]), "mismatch_sample_totals":result["totals"],
        "report":str(args.output)},indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
