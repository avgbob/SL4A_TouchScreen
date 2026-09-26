# Gate5 Qualification — Surface Laptop 4 AMD / MSHW0231

Status: **promoted to the MSHW0231 standard installer profile after a
single-unit field qualification on 2026-09-26.**

This document is the current Gate5 contract. Earlier Gate3/Gate4 freeze and
mode-3 documents remain in the repository as historical evidence and are not
rewritten to pretend they described the final sequence.

## Scope

Qualified target:

- Microsoft Surface Laptop 4 AMD;
- touchscreen ACPI `MSHW0231`, HID VID/PID `045e:0c19`;
- AMD FCH SPI controller `AMDI0060`;
- field kernel `7.0.0-31-generic`;
- hardware checkpoint commit `58f023102679ab0156ce95210abe7e3e3e6ac412`.

This is not an E1/broad compatibility claim. It is one physical SL4 field unit.

## What Gate5 Does Differently

The driver does not choose between "normal HID" and "raw multitouch" as two
mutually exclusive startup modes on MSHW0231. It uses normal HID-over-SPI
discovery first, keeps the HID device registered, then switches the panel into
the CapImg stream and publishes beta multitouch alongside the standard
transport.

```text
ACPI _PS0 -> _RST
        |
RESET_RSP -> DEVICE_DESC -> 936-byte RDESC
        |
write GET_FEATURE report 6
        |
(no synchronous GET6 body read in this activation path)
        |
wait 4.5-5.5 ms
        |
SET_FEATURE report 5 = 1
        |
DONE
        |
0x0c CapImg frames
        |
beta heatmap tracker
        |
MSHW0231 Touchscreen MT input
```

The installer parameters that pin this behavior are:

```text
raw_mode=N
raw_input_beta=Y
wire_double_opcode=1
gate3_observe_only=1
skip_std_getfeat=1
std_raw_transition=1
get_noread=0
getfeat_delay_ms=0
std_liveness_ms=0
std_liveness_recover=0
wait_reset_kick_ms=0
```

`get_noread=0` is retained explicitly because it is the general helper's
default; mode 1 itself takes the dedicated write-only GET6 branch and then
waits `usleep_range(4500, 5500)` before SET5.

## Why Mode 1 Won

The activation matrix isolated two different failure classes.

- SET5-only (mode 3) proved that SET5 can enter CapImg and was essential
  historical evidence.
- GET6 write -> ~5 ms -> SET5 also entered CapImg.
- Full GET6 read -> SET5 caused a controller reset on the field unit.
- Warm SET5-only reloads could still reset roughly 0.52 s after activation,
  proving GET6 was not the root cause of that repeatability failure.

The warm-reset trace exposed a separate race: the first CapImg DATA header
could arrive while `hid_add_device()` was still registering the HID device.
The old handler consumed the header, noticed `hid_creating`, and returned
without draining the ~4304-byte body. The controller then reset about half a
second later.

Gate5 commit `58f0231` changes that rule: once a DATA header is consumed, the
body is drained/processed even while HID creation is active, but publication
through `hid_input_report()` remains suppressed until registration completes.

## Field Qualification Result

| Case | Result |
| --- | --- |
| Warm reload + real touch #1 | PASS |
| Warm reload + real touch #2 | PASS |
| Warm reload + real touch #3 | PASS |
| True cold power-on + real touch | PASS |
| s2idle resume + real touch #1 | PASS |
| s2idle resume + real touch #2 | PASS |
| Observed frame drops in these captures | 0 |
| Unexpected post-DONE resets in these captures | 0 |

The cold-boot capture reached RESET_RSP, DEVICE_DESC, the byte-identical
936-byte RDESC, `mode=1 GET6=1 SET5=1`, and real MT input. Resume explicitly
uses `_PS3` on suspend and `_PS0 -> _RST` on resume, then rediscovers the
descriptors and reruns mode 1.

## Installer Policy

- `MSHW0231` / Surface Laptop 4 AMD: Gate5 profile above.
- `MSHW0162` / Surface Laptop 3 AMD: retain
  `raw_mode=N wire_double_opcode=1`.
- `--raw`: remain an explicit experimental profile on either supported ACPI
  ID.
- mode 3: retained for historical reproduction/diagnostics, not default.

## Historical Checkpoints Kept

The promotion does not delete prior states:

- `gate4-qualified-2026-09-26` -> Gate4 commit `38feff21...`;
- `gate5-qualified-2026-09-26` -> hardware checkpoint `58f02310...`;
- `history/main-pre-gate5-2026-09-26` -> pre-promotion main at Gate4;
- `gate4-id5-delegate` and `gate5-hardware-qualification` branches remain
  available.

The old `docs/STANDARD-SET5-MULTITOUCH.md`,
`docs/HARDWARE_QUALIFICATION_TRACKER.md` and `docs/FREEZE.md` are retained
with supersession notes rather than rewritten as if their earlier conclusions
never existed.

## Remaining Limits

Gate5 does **not** establish:

- the same activation behavior on MSHW0162;
- pen/stylus correctness;
- palm rejection;
- full one-through-five-finger qualification;
- long mixed-input stress;
- Windows-equivalent contact classification;
- broad firmware/kernel/distribution compatibility.

Those require separate evidence and, for a compatibility claim, the repository's
E1 evidence procedure.
