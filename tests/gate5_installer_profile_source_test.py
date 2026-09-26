#!/usr/bin/env python3
"""Pin the device-specific Gate5 installer profile.

MSHW0231 must get the exact field-qualified mode-1 profile while MSHW0162
retains the conservative standard-HID fallback.
"""

from pathlib import Path

src = Path("tools/sl4a-touch.sh").read_text()

start = src.find('info "Step 5: Writing the $PROFILE profile')
end = src.find('pass "Created $MODPROBE_CONF"', start)
assert start >= 0 and end > start, "installer profile block not found"
block = src[start:end]

gate = 'if acpi_device_present "MSHW0231"; then'
assert gate in block, "Gate5 installer profile is not scoped to MSHW0231"

qualified = (
    "options sl4a_spi_hid "
    "raw_mode=N "
    "raw_input_beta=Y "
    "wire_double_opcode=1 "
    "gate3_observe_only=1 "
    "skip_std_getfeat=1 "
    "std_raw_transition=1 "
    "get_noread=0 "
    "getfeat_delay_ms=0 "
    "std_liveness_ms=0 "
    "std_liveness_recover=0 "
    "wait_reset_kick_ms=0"
)
assert qualified in block, "MSHW0231 profile drifted from Gate5 qualification"

split = block.split("\n\t\telse\n", 1)
assert len(split) == 2, "expected explicit MSHW0231/fallback split"
fallback = split[1]

assert "# SL4A_TouchScreen standard HID profile (Surface Laptop 3 AMD)" in fallback
assert "options sl4a_spi_hid raw_mode=N wire_double_opcode=1" in fallback

for forbidden in ("raw_input_beta=Y", "std_raw_transition=1", "skip_std_getfeat=1"):
    assert forbidden not in fallback, f"SL3 fallback unexpectedly enables {forbidden}"

print("gate5 installer profile source test: PASS")
