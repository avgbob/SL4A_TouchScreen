#!/usr/bin/env python3
"""Offline negative-control checks: positive, failures, and passive V0 counter."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "tools/hardware_evidence"))
from pr87_standard_negative import examine, main, recheck_saved, LEGACY_READY_ERROR


with tempfile.TemporaryDirectory(prefix="pr87-negative-") as td:
    root = Path(td)
    param = root / "module/sl4a_spi_hid/parameters"
    spi = root / "bus/spi/devices/spi-MSHW0231:00"
    inventory = root / "class/input"
    param.mkdir(parents=True)
    spi.mkdir(parents=True)
    inventory.mkdir(parents=True)
    module = root / "module/sl4a_spi_hid"
    (module / "srcversion").write_text("EXACTPR")
    for key, val in (("raw_mode", "N"), ("raw_input_beta", "N"),
                     ("std_raw_transition", "0")):
        (param / key).write_text(val)
    (spi / "ready").write_text("ready")
    (spi / "seq_state").write_text("4")
    (spi / "protocol_stats").write_text(
        "reset_rsp=1\ndevice_desc=1\nrpt_desc=1\ndata=24\n"
        "getfeat_resp=0\nframes_dropped=0\nirq_count=25\n"
        "wire_patches=0\npoll_missed=0\nraw_observed=17\n")
    def check(message):
        result = examine(root, "EXACTPR")
        assert result["verdict"] == "INCONCLUSIVE", (message, result)
        assert result["errors"], message

    passed = examine(root, "EXACTPR")
    assert passed["verdict"] == "PASS_NEGATIVE_CONTROL", passed
    assert passed["observed_passive_capimg_frames"] == 17, passed
    assert "NOT_PROVEN" in passed["report_0x0c_dispatch_policy"]
    assert main(["--sysfs-root", str(root), "--expected-srcversion", "EXACTPR"]) == 0
    (param / "raw_input_beta").write_text("Y")
    check("beta publishing enabled")
    (param / "raw_input_beta").write_text("N")
    (param / "std_raw_transition").write_text("1")
    check("standard CapImg transition enabled")
    (param / "std_raw_transition").write_text("0")
    (param / "raw_mode").write_text("Y")
    check("raw transport unexpectedly enabled")
    (param / "raw_mode").write_text("N")
    bridge = inventory / "input9"
    bridge.mkdir()
    (bridge / "name").write_text("MSHW0231 Touchscreen")
    check("experimental bridge present")
    (bridge / "name").write_text("Other Touchscreen")
    assert examine(root, "EXACTPR")["verdict"] == "PASS_NEGATIVE_CONTROL"
    check_result = examine(root, "WRONG")
    assert check_result["verdict"] == "INCONCLUSIVE"
    (spi / "ready").write_text("not ready")
    check("standard HID not ready")
    (spi / "ready").write_text("1")
    check("incorrect numeric ready alias")
    (spi / "ready").write_text("ready")
    (spi / "seq_state").write_text("5")
    check("not in SPI_HID_SEQ_DONE")
    (spi / "seq_state").write_text("4")
    (spi / "protocol_stats").write_text("device_desc=1\nrpt_desc=0\nraw_observed=0\n")
    check("missing report descriptor")
    (spi / "protocol_stats").unlink()
    check("protocol stats unavailable")
    inventory.rename(root / "class/input-missing")
    check("input inventory unavailable")

    # This snapshot reproduces the exact hardware printout: every
    # *physical* observation is good, only the original 1-vs-"ready"
    # verifier verdict was mistaken.
    snapshot = {
        "bridge_input_instances": [],
        "errors": [LEGACY_READY_ERROR],
        "expected_pr87_srcversion": "EXACTPR",
        "limitations": "Does not infer CapImg publishing from silence",
        "loaded_srcversion": "EXACTPR",
        "module_parameters": {"raw_mode": "N", "raw_input_beta": "N",
                              "std_raw_transition": "0"},
        "observed_passive_capimg_frames": 0,
        "report_0x0c_dispatch_policy":
            "NOT_PROVEN_BY_THIS_FIELD_CHECK; compiled production-handler test required",
        "standard_hid_descriptor_responses": {"device_desc": 1, "rpt_desc": 1},
        "standard_hid_ready": "ready",
        "standard_seq_state": "4",
        "verdict": "INCONCLUSIVE",
    }
    import json
    saved = root / "saved-hardware.json"
    saved.write_text(json.dumps(snapshot))
    good = recheck_saved(snapshot, "EXACTPR")
    assert good["verdict"] == "PASS_REVIEWED_SAVED_CAPTURE", good
    assert good["original_file_unchanged"] is True
    assert main(["--expected-srcversion", "EXACTPR",
                 "--review-saved-json", str(saved)]) == 0
    assert json.loads(saved.read_text()) == snapshot, "historical evidence mutated"
    for field, wrong in (
        ("bridge_input_instances", ["input9"]),
        ("standard_hid_ready", "not ready"),
        ("standard_seq_state", "5"),
        ("observed_passive_capimg_frames", None),
    ):
        trial = dict(snapshot, **{field: wrong})
        assert recheck_saved(trial, "EXACTPR")["verdict"] == "INCONCLUSIVE", field
    bad = dict(snapshot, module_parameters={"raw_mode": "Y",
                                            "raw_input_beta": "N",
                                            "std_raw_transition": "0"})
    assert recheck_saved(bad, "EXACTPR")["verdict"] == "INCONCLUSIVE"
    bad = dict(snapshot, errors=[LEGACY_READY_ERROR, "new tracking ID"])
    assert recheck_saved(bad, "EXACTPR")["verdict"] == "INCONCLUSIVE"
    bad = dict(snapshot, errors=[])
    assert recheck_saved(bad, "EXACTPR")["verdict"] == "INCONCLUSIVE", (
        "do not retrospectively certify unexplained INCONCLUSIVE verdicts")
    bad = dict(snapshot, verdict="PASS_NEGATIVE_CONTROL")
    assert recheck_saved(bad, "EXACTPR")["verdict"] == "INCONCLUSIVE", (
        "historical failure error must not pair with a claimed PASS")
    assert recheck_saved(snapshot, "WRONG")["verdict"] == "INCONCLUSIVE"
    missing = dict(snapshot)
    missing.pop("standard_hid_descriptor_responses")
    assert recheck_saved(missing, "EXACTPR")["verdict"] == "INCONCLUSIVE"
print("PR87 default-standard negative-control offline/fail-closed: PASS")
