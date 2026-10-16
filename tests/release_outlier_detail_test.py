#!/usr/bin/env python3
"""Exact persisted guided cue and evdev shapes for voice-lag outlier analysis."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/hardware_evidence"))
from release_outlier_detail import examine


def fixture(root, event_frames, cue_relative=0.100):
    directory = root / "cycle-2-quick" / "operator"
    directory.mkdir(parents=True, exist_ok=True)
    cue = 100.80 + cue_relative
    (directory / "cues.tsv").write_text(
        "utc\tmonotonic_seconds\tevent\tdetail\n"
        "now\t100.45\tphase-pass\texpand;attempt=1\n"
        "now\t100.50\tphase-instruction\tlift;attempt=1\n"
        "now\t100.55\tphase-begin\tlift;attempt=1\n"
        f"now\t{cue}\tgesture-progress\tlift:One original finger remains. Lift it now.\n"
        "now\t101.80\tphase-pass\tlift;attempt=1\n")
    rows = []
    for clock, kernel, ids in event_frames:
        rows.append({"kind": "frame", "monotonic": clock,
                     "event_sec": int(kernel),
                     "event_usec": round((kernel % 1) * 1e6),
                     "contacts": [{"id": id_, "x": 200, "y": 330} for id_ in ids]})
    (directory / "live-evdev.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n")
    return directory.parent


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    outlier = fixture(root, [
        (100.44, 5000.44, [10, 11]),
        (100.80, 5000.80, [10]),
        (101.225775, 5001.225775, []),
    ], cue_relative=0.6)
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        assert examine(outlier) == 0
    out = captured.getvalue()
    assert "425.775 ms" in out
    assert "voice-cue mark AFTER final 0-contact frame by 174.225 ms" in out
    assert "Tracking-ID anomalies: none observed" in out
    assert "physical touch release latency" in out
    assert '"x"' not in out and '"y"' not in out
    assert "[10, 11]" not in out, "don't reveal touch tracking IDs/coordinates"

    # Intermediate cue precedes final zero-contact, not proof of user wait.
    alt = root / "other"
    early = fixture(alt, [
        (100.44, 6000.44, [20, 21]),
        (100.80, 6000.80, [20]),
        (101.225775, 6001.225775, []),
    ], cue_relative=.05)
    saved = io.StringIO()
    with contextlib.redirect_stdout(saved):
        assert examine(early) == 0
    assert "final 0-contact frame recorded 375.775 ms AFTER voice-cue mark" in saved.getvalue()

    # Missing final release is not silently treated as valid.
    incomplete = fixture(root / "missing", [
        (100.44, 7000.44, [30, 31]),
        (100.80, 7000.80, [30]),
    ])
    try:
        examine(incomplete)
    except ValueError as error:
        assert "no complete 2 -> 1 -> 0" in str(error)
    else:
        raise AssertionError("missing final contact release was accepted")
print("read-only release interval and voice cue clock analysis: PASS")
