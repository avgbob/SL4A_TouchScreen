#!/usr/bin/env python3
"""Offline, read-only regression: actual saved evdev + cues shape, no device."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "tools/hardware_evidence"))
from release_timing_report import analyze, candidates, report


def fixture(root, name, frames, phase="quick", result=True):
    session = root / name / "cycle-1-quick"
    op = session / "operator"
    op.mkdir(parents=True)
    points = [
        ("100.50", "phase-pass", phase + "-expand;attempt=1"),
        ("100.60", "phase-instruction", phase + "-lift;attempt=1"),
        ("100.65", "phase-begin", phase + "-lift;attempt=1"),
        ("100.82", "gesture-progress",
         phase + "-lift:One original finger remains. Lift it now."),
        ("101.90", "phase-pass" if result else "phase-inconclusive",
         phase + "-lift;attempt=1;last_frame=12"),
    ]
    (op / "cues.tsv").write_text(
        "utc\tmonotonic_seconds\tevent\tdetail\n" +
        "".join("now\t{}\t{}\t{}\n".format(*p) for p in points))
    contents = []
    for mono, kernel, ids in frames:
        contents.append({"kind": "frame", "monotonic": mono,
                         "event_sec": int(kernel),
                         "event_usec": round((kernel % 1) * 1e6),
                         "contacts": [{"id": i, "x": 5, "y": 10}
                                      for i in ids]})
    (op / "live-evdev.jsonl").write_text(
        "\n".join(json.dumps(row) for row in contents) + "\n")
    return session


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    good = fixture(root, "pr87-exact-warm3-a", [
        (100.49, 5000.49, [11, 12]),
        (100.70, 5000.70, [11, 12]),
        (100.82, 5000.82, [11]),
        (100.84, 5000.84, []),
    ])
    row, = analyze(good)
    assert row["phase"] == "quick-lift" and row["status"] == "SEQUENTIAL_RELEASE", row
    assert abs(row["kernel_gap_ms"] - 20.0) < .001, row
    assert abs(row["observer_gap_ms"] - 20.0) < .001
    assert row["intermediate_announced"]

    slow = fixture(root, "pr87-exact-s2idle2-b", [
        (100.49, 6000.49, [21, 22]),
        (100.82, 6000.82, [22]),
        (101.05, 6001.05, []),
    ])
    row, = analyze(slow)
    assert abs(row["kernel_gap_ms"] - 230.0) < .001

    direct = fixture(root, "mode4-quick-c", [
        (100.49, 7000.49, [31, 32]),
        (100.85, 7000.85, []),
    ])
    row, = analyze(direct)
    assert row["status"] == "DIRECT_RELEASE" and row["kernel_gap_ms"] is None

    abnormal = fixture(root, "pr87-exact-warm3-d", [
        (100.49, 8000.49, [41, 42]),
        (100.81, 8000.81, [41, 99]),  # replacement invalid
        (100.83, 8000.83, [41]),
        (100.86, 8000.86, []),
    ])
    row, = analyze(abnormal)
    assert row["status"] == "TRACKING_ANOMALY"
    assert "NEW_ID" in row["violations"]

    # JSONL source must be MONOTONIC, otherwise do not invent intervals.
    broken = fixture(root, "pr87-exact-warm3-e", [
        (100.49, 9000.49, [51, 52]),
        (100.81, 9000.81, [51]),
        (100.80, 9000.82, []),
    ])
    try:
        analyze(broken)
    except ValueError as exc:
        assert "non-monotonic" in str(exc)
    else:
        raise AssertionError("bad timestamp could yield misleading PASS")

    # No zero-contact observation is never a complete finger release.
    no_release = fixture(root, "pr87-exact-warm3-f", [
        (100.49, 10000.49, [61, 62]),
        (100.83, 10000.83, [61]),
    ])
    row, = analyze(no_release)
    assert row["status"] == "INCOMPLETE"

    assert len(candidates(root)) == 6
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = report([root], threshold=100)
    text = out.getvalue()
    assert code == 1  # incomplete and anomaly flag manual review
    assert "20.000 ms (kernel)" in text
    assert "230.000 ms (kernel)  [REVIEW_GAP]" in text
    assert "TRACKING_ANOMALY" in text
    assert "INCOMPLETE" in text
    assert "DIRECT_RELEASE" in text
    assert "Measured sequential gaps" in text
    assert '"x"' not in text and '"y"' not in text
    assert "event_usec" not in text
    assert "normal physical finger-off" not in text.lower()

print("PR87/mode4 automatic release timing and strict anomaly screening: PASS")
