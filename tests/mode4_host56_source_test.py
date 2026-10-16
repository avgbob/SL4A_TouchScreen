#!/usr/bin/env python3
"""Source contract for the MSHW0231-only 0x56 FFx6 -> SET5 experiment.

Diagnostic-only, no hardware claims: mode 1 Gate5 must remain untouched.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
core = (root / "driver/spi-hid-core.c").read_text()
hdr = (root / "driver/spi-hid-core.h").read_text()
installer = (root / "tools/sl4a-touch.sh").read_text()
frames = (root / "driver/spi-hid-wire-frames.h").read_text()

def check(condition, message):
    assert condition, message

# Existing qualified mode 1 is still installed by default; mode 4 is not.
check("std_raw_transition=1 get_noread=0" in installer,
      "Gate5 standard installer default changed")
check("std_raw_transition=4" not in installer,
      "diagnostic mode 4 may not be installed automatically")
check('std_raw_transition == 1 ||' in core and
      "usleep_range(4500, 5500)" in core,
      "qualified GET6 write-only path is missing")

# Exact match-data is captured before fallback to SL4 geometry.
check("bool std_host56_mshw0231;" in hdr,
      "per-device mode4 eligibility bit missing")
check("shid->std_host56_mshw0231 = shid->cfg == &spi_hid_cfg_sl4;" in core,
      "mode4 must require exact ACPI match data")
check("if (std_raw_transition == 4 && !shid->std_host56_mshw0231)" in core,
      "wrong-device refusal missing")
check("std_raw_transition == 4 &&" in core,
      "mode4 activation qualification missing")

# Only 0x56 FFx6 is sent, NEVER a copied host Bluetooth address.
helper_start = core.index("static int spi_hid_seq_write_host56_none(")
helper_end = core.index("/* GET_FEATURE Report ID 6", helper_start)
helper = core[helper_start:helper_end]
check("spi_hid_wire_vendor_stop(spi_hid_wire_doubled_setfeat())" in helper,
      "mode4 is not using the byte-pinned FF x6 frame")
check("spi_hid_wire_vendor_init" not in helper,
      "mode4 must not send another machine's address")
check("0x56, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF" in frames,
      "mode4 FF x6 wire fixture is missing")

# Keep the whole mode4 transaction within one sequencer-lock branch.
start = core.index("if (host56_mode4) {")
end = core.index("} else if (do_set5", start)
block = core[start:end]
first = block.find("spi_hid_seq_write_host56_none(shid)")
delay = block.find("usleep_range(37000, 40000)")
set5 = block.find("spi_hid_seq_write_setfeat(shid)")
check(0 <= first < delay < set5,
      "mode4 must send FF x6 -> wait 37-40 ms -> SET5")
check("spi_hid_seq_write_get_feature6" not in block and
      "spi_hid_getfeat6_read" not in block,
      "mode4 must not send or read GET6")
check("withholding SET5" in block,
      "a failed 0x56 must not silently degrade into SET5-only")

# Register and consume MT input only when the same exact hardware gate holds.
gate = "(std_raw_transition == 4 && shid->std_host56_mshw0231)"
check(core.count(gate) == 2,
      "mode4 input registration and DATA consumption must both be gated")
check("raw_input_beta" in core[core.index(gate):core.index(gate)+180],
      "mode4 DATA consumption must require raw_input_beta")

print("MSHW0231 mode4 host 0x56 FFx6 activation source test: PASS")
