#!/usr/bin/env python3
"""Pin the device-specific Gate5 installer profile.

MSHW0231 must get the exact field-qualified mode-1 profile while MSHW0162
retains the conservative standard-HID fallback.
"""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = (root / "tools" / "sl4a-touch.sh").read_text()

start = src.find('info "Step 5: Writing the $PROFILE profile')
end = src.find('pass "Created $MODPROBE_CONF"', start)
assert start >= 0 and end > start, "installer profile block not found"
block = src[start:end]

gate = 'if acpi_device_present "MSHW0231"; then'
gate_pos = block.find(gate)
assert gate_pos >= 0, "Gate5 installer profile is not scoped to MSHW0231"

device_block = block[gate_pos:]
device_end = device_block.find("\n\t\tfi")
assert device_end > 0, "MSHW0231 profile conditional is not closed"
device_block = device_block[:device_end]

split = device_block.split("\n\t\telse\n", 1)
assert len(split) == 2, "expected explicit MSHW0231/fallback split"
sl4_branch, fallback = split

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
assert qualified in sl4_branch, "MSHW0231 profile drifted from Gate5 qualification"

assert "# SL4A_TouchScreen standard HID profile (Surface Laptop 3 AMD)" in fallback
assert "options sl4a_spi_hid raw_mode=N wire_double_opcode=1" in fallback

for forbidden in ("raw_input_beta=Y", "std_raw_transition=1", "skip_std_getfeat=1"):
    assert forbidden not in fallback, f"SL3 fallback unexpectedly enables {forbidden}"

print("gate5 installer profile source test: PASS")
