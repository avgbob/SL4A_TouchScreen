#!/usr/bin/env python3

from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
core = (root / "driver/spi-hid-core.c").read_text()

failures = []

def require(cond, msg):
    if not cond:
        failures.append(msg)

eligibility = """\
(std_raw_transition == 1 ||
\t\t       std_raw_transition == 3)"""

eligibility_probe = """\
(std_raw_transition == 1 ||
\t      std_raw_transition == 3)"""

require(
    eligibility in core,
    "mode1/mode3 beta input DATA-path eligibility missing"
)

require(
    eligibility_probe in core,
    "mode1/mode3 beta input probe eligibility missing"
)

require(
    core.count("std_raw_transition == 1") >= 3,
    "expected Gate4 activation plus two Gate5 mode1 eligibility sites"
)

# Mode 2 is GET6 diagnostic-only and must not become a beta-input mode.
probe_start = core.find(
    "Create the heatmap-backed MT input device only when it can receive"
)

if probe_start >= 0:
    probe_end = core.find("mshw0231_raw_init(shid);", probe_start)

    require(
        probe_end > probe_start,
        "could not isolate heatmap input registration block"
    )

    if probe_end > probe_start:
        block = core[probe_start:probe_end]

        require(
            "std_raw_transition == 2" not in block,
            "mode2 incorrectly enabled for beta input registration"
        )

# CapImg input consumption must still require raw_input_beta.
data_marker = "body[7] == 0x0C && shid->touch_input"

require(
    data_marker in core,
    "CapImg beta-input consumption gate missing"
)

pos = core.find(data_marker)

if pos >= 0:
    block = core[max(0, pos - 350):pos + 100]

    require(
        "raw_input_beta" in block,
        "CapImg beta input no longer gated by raw_input_beta"
    )

if failures:
    for failure in failures:
        print("FAIL:", failure)

    print(
        f"gate5 mode1 input source test: "
        f"{len(failures)} failure(s)"
    )
    sys.exit(1)

print("gate5 mode1 input source test: PASS")
