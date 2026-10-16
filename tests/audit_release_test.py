#!/usr/bin/env python3
"""Regression for read-only release audit: valid singleton vs new ID."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "tools/hardware_evidence"))
from audit_release import inspect


def fixture(session, events):
    folder = session / "operator"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "cues.tsv").write_text(
        "utc\tmonotonic_seconds\tevent\tdetail\n"
        "t\t100.0\tphase-pass\tpinch-expand;attempt=1\n"
        "t\t100.5\tphase-instruction\tpinch-lift;attempt=1\n"
        "t\t100.6\tphase-begin\tpinch-lift;attempt=1\n"
        "t\t105.0\tphase-inconclusive\tpinch-lift;attempt=1\n")
    rows = [{"kind":"frame","monotonic":t,"contacts":[
        {"id":contact,"x":100,"y":100} for contact in ids]}
        for t, ids in events]
    (folder/"live-evdev.jsonl").write_text(
        "".join(json.dumps(row)+"\n" for row in rows))


with tempfile.TemporaryDirectory() as root:
    valid = Path(root)/"valid"
    fixture(valid, [(100.0,[1,2]),(100.7,[1,2]),
                    (100.9,[1]), (101.1,[])])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert inspect(valid)==0
    assert "Normal partial original-ID release observed" in output.getvalue()
    assert "UNEXPECTED NEW" not in output.getvalue()
    assert '"x":' not in output.getvalue()

    changed = Path(root)/"changed"
    fixture(changed, [(100.0,[1,2]),(100.7,[1,2]),
                      (100.9,[1,9]),(101.1,[])])
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert inspect(changed)==0
    assert "New tracking ID observed" in output.getvalue()
    assert "UNEXPECTED NEW" in output.getvalue()
print("saved release audit differentiates valid sequential lift and new ID: PASS")
