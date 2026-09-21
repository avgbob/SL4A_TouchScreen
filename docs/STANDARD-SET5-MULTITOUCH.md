# Standard-transport SET5 multitouch experiment

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

## Known issue

Two-finger tracking is functional but not yet fully stable when contacts move
close together. In the field capture, one slot was dropped and reacquired
several times while the other slot remained stable. This looks like
blob/contact tracking tuning rather than a transport failure.

Do not tune the tracker until the transport path has been checkpointed and
tested across cold boot and suspend/resume.

## Next validation

Before treating this as a default profile:

1. cold-boot with the SET5-only bridge configuration
2. verify the CapImg stream starts without manual module reload
3. suspend/resume and verify the bridge re-enters SET5 mode cleanly
4. reduce debug logging
5. tune contact/blob tracking only after transport stability is confirmed
