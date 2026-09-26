# Standard-transport SET5 multitouch experiment

> **Historical record — preserved intentionally.** This document describes the
> mode-3 SET5-only experiment that unlocked CapImg on 2026-09-21. It is not the
> current MSHW0231 installer contract. Gate5 later qualified
> `std_raw_transition=1` (write-only GET6 -> 4.5-5.5 ms -> SET5) together with
> the HID-registration DATA-drain fix. See `docs/GATE5-QUALIFICATION.md`.

Status: **field-tested on one Surface Laptop 4 AMD (MSHW0231)** on 2026-09-21.

This branch keeps normal HID-over-SPI discovery/transport, suppresses the generic
standard-mode feature GET_REPORT path, sends only SET_FEATURE report ID 5 with
value 1 after descriptor discovery, and routes the resulting CapImg report
`0x0c` frames through the existing heatmap/contact pipeline.

It does **not** enable the driver's `raw_mode=Y` transport.

## Why this branch exists

A field A/B test isolated the two commands in the existing
`std_raw_transition` sequence:

- mode 2: GET6 only
- mode 3: SET5 only

On the tested panel, GET6-only caused a controller reset/re-enumeration. Standard
report `0x40` touch recovered afterward, but no CapImg stream was observed.

SET5-only did not add a reset and immediately produced standard-path
`0x0c` CapImg bodies when the panel was touched. The measured bodies were
4302 bytes and arrived at roughly the expected touch-frame cadence.

That gives the tested path:

```text
normal HID-over-SPI discovery
        |
skip standard feature GET_REPORT traffic
        |
SET_FEATURE report 5 = 1
        |
0x0c CapImg stream
        |
existing heatmap decoder/tracker
        |
Linux MT slots
```

## Known-good field parameters

The successful live run used:

```text
raw_mode=N
raw_input_beta=Y
wire_double_opcode=1
skip_std_getfeat=1
std_raw_transition=3
get_noread=1
getfeat_delay_ms=0
std_liveness_ms=0
std_liveness_recover=0
```

`sl4a_debug_level=2` was used for evidence collection. It is not required for
the data path.

## Field evidence

### SET5-only transport test

With `raw_input_beta=N` and `std_raw_transition=3`:

- discovery remained at one device/report descriptor exchange
- no additional controller reset was observed during the test
- `raw_observed` climbed while touching the panel
- standard-path logs reported `cid=0x0c len=4302`
- `frames_dropped=0`

This proved that SET5 alone can switch this panel into the CapImg stream without
using the raw-mode transport.

### Standard-transport MT bridge test

With `raw_input_beta=Y` and `std_raw_transition=3`, the driver created
`MSHW0231 Touchscreen` with direct-touch MT capabilities including:

- `ABS_MT_SLOT`
- `ABS_MT_TRACKING_ID`
- `ABS_MT_POSITION_X`
- `ABS_MT_POSITION_Y`

A 12-second two-finger capture ended with:

```text
reset_rsp=2
device_desc=1
rpt_desc=1
data=1144
frames_dropped=0
irq_count=1148
raw_observed=1130
```

Event counts from that capture were:

```text
MT_SLOT:        1056
TRACKING_ID:    17
MT_POSITION_X:  1292
MT_POSITION_Y:  1238
```

Parsing the tracking-ID lifecycle showed a maximum of **2 simultaneous active
contacts**. Firefox on Wayland successfully performed touchscreen pinch-to-zoom
with the same loaded module.

## Tracker status

The original close-contact failure has now been localized to tracker ordering,
not transport. A captured two-finger spacing run showed two valid candidates
being destructively collapsed by the old pre-Hungarian ghost merge whenever
their centroids crossed below the six-cell threshold.

The follow-on tracker branch moves close-contact suppression after Hungarian
association and preserves candidates backed by two distinct established tracks.
That ordering has deterministic host coverage in
`tests/tracker_coalescing_host_test.c`.

This is still not full Windows-equivalent classification: two contacts first
created already very close remain an unresolved candidate-classification case.
See `docs/TRACKER-REORDER.md`.

## Qualification status

The corrected persistent SET5-only beta-bridge profile has now passed a true
cold boot: the expected `MSHW0231 Touchscreen` node returned, the bridge
registered, and the mode-3 SET5 transition ran without a manual reload.

This does not make the profile a release default. Suspend/resume and the broader
hardware matrix were not completed before physical testing stopped, and debug
logging still should be reduced for a production-oriented profile. Tracker
tuning should remain separate from transport stability; the targeted
established-contact pinch fix is merged, while close-start classification is a
different unresolved tracker problem.
