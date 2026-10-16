#!/usr/bin/env python3
"""Offline negative-control checks: positive, failures, and passive V0 counter."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                       "tools/hardware_evidence"))
from pr87_standard_negative import examine, main


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
    (spi / "ready").write_text("1")
    (spi / "seq_state").write_text("5")
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
    (spi / "ready").write_text("0")
    check("standard HID not ready")
    (spi / "ready").write_text("1")
    (spi / "protocol_stats").write_text("device_desc=1\nrpt_desc=0\nraw_observed=0\n")
    check("missing report descriptor")
    (spi / "protocol_stats").unlink()
    check("protocol stats unavailable")
    inventory.rename(root / "class/input-missing")
    check("input inventory unavailable")
print("PR87 default-standard negative-control offline/fail-closed: PASS")
