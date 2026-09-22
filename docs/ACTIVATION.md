# Raw Mode Activation (SET_FEATURE ID5)

The MSHW0231 touch controller has an observed activation sequence for heatmap
experiments. SET_FEATURE ID5 alone has produced CapImg traffic on the targeted
SL4 AMD unit and the SET5-only standard-transport bridge survived a corrected
cold boot, but that result is not portable/release evidence; see
`docs/EVIDENCE.md` before treating it as a protocol contract.
The Surface Laptop 3 AMD controller (`MSHW0162`) uses the same V0 transport
and the same sequence.

## Activation Sequence

### 1. Vendor Initialization

Before the SET_FEATURE command, the driver sends the vendor-initialization
write — command register `0x000003`, 18 bytes:

```
02 00 00 03 C2 00 03 0A 00 56 BD 0C EE 5B 44 4C 00 00
```

`C2` is the header byte (version | length), not a register; the payload is
report ID `0x56` followed by the six-byte device key. This matches the Windows
touch initialization trace (`captures/wintrace/surface_init.csv`); the frame is
built by `spi_hid_wire_vendor_init()` and pinned byte for byte by
`tests/wire_frames_test.c`.

### 2. SET_FEATURE Handshake

With `skip_getfeat=0`, the legacy path waits for the Windows-like ~3.6 s gap
(measured; the original protocol doc cited ~5.9 s) between RPT_DESC and
GET_FEATURE before sending the activation command. The
experimental raw profile uses `skip_getfeat=1` and takes the direct vendor-init
path instead. Neither mode skips the Report ID 6 configuration read, which
Windows performs between RPT_DESC and SET_FEATURE ID5 and which the driver now
logs without acting on its values.

```
Host → Device:
  Report Type: Feature (0x03)
  Report ID:   5
  Value:       0x01 (observed raw-mode request)
```

The SET_FEATURE frame is a standard HID feature report with:
- Report type = 0x03 (SET_REPORT / Feature)
- Feature report ID = 5
- Data byte = 0x01 (observed request value)

### 3. Mode Change

SET_FEATURE ID5=01 is part of the observed activation sequence. The current
driver recognizes byte-indexed CapImg frames of roughly 4304 bytes, while older
documentation described a 16-bit 6912-byte raster. This discrepancy is tracked
in `docs/EVIDENCE.md`; do not use either layout as a new protocol contract
without a labelled replay fixture.

## Linux Driver Implementation

### `skip_getfeat=1` (Experimental Raw Profile)

The driver uses a direct vendor-init path:
1. Write vendor-init command (0xC2 opcode)
2. After a short stabilization delay, write GET_FEATURE Report ID 6 and keep/log
   the reply (Windows order; diagnostic only, a failed read does not stop here)
3. Write SET_FEATURE ID5=01
4. Observe subsequent reports; targeted SL4 streaming has been demonstrated,
   but broader lifecycle/hardware reliability remains unqualified

### `std_raw_transition=3` (Experimental Standard-Transport Beta Bridge)

After normal HID-over-SPI descriptor discovery, mode 3 performs the SET_FEATURE
ID5 write without the Report-6 GET step and routes subsequent CapImg `0x0c`
frames into the beta heatmap multitouch input path when `raw_input_beta=1`.
The targeted SL4 AMD qualification profile used `raw_mode=0`,
`raw_input_beta=1`, `skip_std_getfeat=1`, and `std_raw_transition=3`.
This bridge is manual/experimental and is not written by the installer.

### `skip_getfeat=0` (Legacy)

The original GET_FEATURE-based path:
1. Wait for device descriptor available
2. Read report descriptor
3. Wait ~3.6 s (Windows GET_FEATURE delay, measured; original doc cited ~5.9 s)
4. Send GET_FEATURE → device returns current ID5 state
5. Send SET_FEATURE ID5=01 → observe whether a stream follows

The `skip_getfeat=1` raw-transport path is selected by
`sl4a-touch.sh install --raw`. The standard installer profile remains
standard HID/single-touch; the standard-transport beta bridge above is an
explicit manual qualification profile rather than an installer default.

## Debug Validation

There is no `raw_enabled` parameter. Inspect the SPI HID device's `ready`,
`protocol_stats`, `baseline_status`, and `heatmap_debug` sysfs attributes as
described in `docs/TESTING.md`.

## References

- `tools/surface_tracker.py` — Python oracle with raw mode validation
- `docs/HIDSPI_PROTOCOL.md` — Full HID-over-SPI protocol reference
- Windows `surface_init.csv` trace — Transaction #267 (vendor-init)
