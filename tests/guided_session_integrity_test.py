#!/usr/bin/env python3
"""Exercise the real audit decisions without a physical touchscreen."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
path = root / "tools/hardware_evidence/guided_session.py"
spec = importlib.util.spec_from_file_location("guided_session_audit", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

before = "reset_rsp=1\nframes_dropped=0\ndata=7\nraw_observed=6\n"
after = "reset_rsp=1\nframes_dropped=0\ndata=35\nraw_observed=33\n"
assert module.verify_counters(before, after, "beta") == {
    "delta_reset_rsp": 0, "delta_frames_dropped": 0,
    "delta_data": 28, "delta_raw_observed": 27,
}
def rejected(a,b,source="beta"):
    try:
        module.verify_counters(a,b,source)
    except RuntimeError:
        return
    raise AssertionError("unsafe counter transition was accepted")
rejected(before, after.replace("reset_rsp=1", "reset_rsp=2"))
rejected(before, after.replace("frames_dropped=0", "frames_dropped=1"))
rejected(before, after.replace("raw_observed=33", "raw_observed=6"))
rejected(before, after.replace("data=35", "data=7"))
rejected(before, "reset_rsp=1\nframes_dropped=0\ndata=35\n")
# Conservative single-touch control is not required to have CapImg.
module.verify_counters(before, before, "direct")

with tempfile.TemporaryDirectory() as td:
    folder = Path(td)
    op = folder / "operator"
    op.mkdir()
    (op / "run-metadata.txt").write_text("live_mode=4\n")
    (op / "cues.tsv").write_text("utc\tevent\n")
    (folder / "session-status.txt").write_text("status=completed\n")
    module.finalize_manifest(folder)
    manifest = folder / "SHA256SUMS.txt"
    lines = manifest.read_text().splitlines()
    assert len(lines) == 3
    assert any("operator/run-metadata.txt" in line for line in lines)
    assert any("operator/cues.tsv" in line for line in lines)
    assert any("session-status.txt" in line for line in lines)
    p = subprocess.run(["sha256sum", "-c", str(manifest)],
                       cwd=folder, capture_output=True)
    assert p.returncode == 0
    (op / "cues.tsv").write_text("TAMPERED")
    p = subprocess.run(["sha256sum", "-c", str(manifest)],
                       cwd=folder, capture_output=True)
    assert p.returncode != 0

src = path.read_text()
assert 'parser.add_argument("--expected-mode"' in src
assert "verify_run_integrity(args.expected_mode, built)" in src
assert 'check["module_sha256"] != verified_identity["module_sha256"]' in src
assert 'props["integrity_and_counters"] = "FAIL: "' in src
assert "finalize_manifest(args.output)" in src
print("guided evidence integrity/counter behavior test: PASS")
