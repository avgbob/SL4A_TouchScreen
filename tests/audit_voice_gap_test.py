#!/usr/bin/env python3
"""Synthetic audit of an interrupted two-finger voice handoff."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "tools/hardware_evidence"))
from audit_voice_gap import run

with tempfile.TemporaryDirectory() as td:
    session = Path(td)
    op = session / "operator"
    op.mkdir()
    (op / "cues.tsv").write_text(
        "utc\tmonotonic_seconds\tevent\tdetail\n"
        "t\t100.00\tphase-pass\tquick-pinch;attempt=1;last_frame=20\n"
        "t\t102.00\tphase-instruction\tquick-expand;attempt=1\n"
        "t\t110.00\tphase-begin\tquick-expand;attempt=1\n"
        "t\t116.00\tphase-inconclusive\tquick-expand;attempt=1\n"
    )
    def event(t, ids):
        return {"kind": "frame", "monotonic": t, "seq": 1,
                "contacts": [{"id": i, "x": i * 20, "y": 10} for i in ids]}
    rows = [
        event(99.99, [11, 12]),
        event(101.00, [11, 12]),
        event(108.30, []),
        event(110.20, [21, 22]),
    ]
    (op / "live-evdev.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert run(session) == 0
    o = output.getvalue()
    assert "Accepted pinch IDs: [11, 12]" in o
    assert "Time from pinch PASS to expand GO: 10.00s" in o
    assert "FIRST LOSS: +8.300s after pinch PASS" in o
    assert "all fingers lifted" in o
    assert "frame" in o
    # No coordinates, user secrets or raw event history in the summary.
    assert '"x":' not in o
    assert '"y":' not in o
print("read-only voice-gap tracking audit: PASS")
