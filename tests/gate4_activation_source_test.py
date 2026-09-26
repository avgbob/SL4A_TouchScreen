#!/usr/bin/env python3

from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
core = (root / "driver/spi-hid-core.c").read_text()

failures = []

def require(cond, msg):
    if not cond:
        failures.append(msg)

# Locate the documented Gate-4 activation block.
marker = "Gate 4 hardware result:"
require(marker in core, "Gate-4 hardware-result block missing")

if marker in core:
    start = core.index(marker)

    # Keep the window deliberately local to the standard transition.
    end = core.find("if (do_set5", start)
    require(end > start, "cannot locate SET5 following Gate-4 GET6 block")

    if end > start:
        block = core[start:end]

        require(
            "std_raw_transition == 1" in block,
            "mode-1 write-only branch missing",
        )

        require(
            "spi_hid_seq_write_get_feature6(shid)" in block,
            "mode-1 GET6 write missing",
        )

        require(
            "usleep_range(4500, 5500)" in block,
            "qualified ~5 ms GET6->SET5 delay missing",
        )

        require(
            "spi_hid_getfeat6_read(shid)" in block,
            "full-read diagnostic fallback missing",
        )

        p_mode = block.find("std_raw_transition == 1")
        p_write = block.find("spi_hid_seq_write_get_feature6(shid)")
        p_delay = block.find("usleep_range(4500, 5500)")
        p_full = block.find("spi_hid_getfeat6_read(shid)")

        require(
            p_mode < p_write < p_delay < p_full,
            "Gate-4 ordering changed: expected mode1 -> GET6 write -> delay -> "
            "full-read fallback",
        )

# SET5 must still be the proven sequencer helper.
require(
    "spi_hid_seq_write_setfeat(shid)" in core,
    "sequencer SET5 helper call missing",
)

# Generic HID ID5=1 must still delegate to that helper.
require(
    "HID SET_REPORT ID5=1 delegated to sequencer SET5" in core,
    "ID5 delegation marker missing",
)

# Regression rule: mode1 itself must never consume the GET6 reply.
needle = "if (std_raw_transition == 1)"
if needle in core:
    pos = core.index(needle)
    mode1 = core[pos:core.find("} else {", pos)]

    require(
        "spi_hid_getfeat6_read" not in mode1,
        "mode1 consumes GET6 response again",
    )

if failures:
    for f in failures:
        print("FAIL:", f)
    print(f"gate4 activation source test: {len(failures)} failure(s)")
    sys.exit(1)

print("gate4 activation source test: PASS")
