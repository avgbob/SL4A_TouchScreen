# Module Parameter Contract

The installer standard profile is device-aware. MSHW0231 uses the standard HID
transport and enables the Gate5 CapImg multitouch bridge; MSHW0162 keeps the
conservative standard-HID profile. The separate legacy raw transport remains a
diagnostic/research path only. This table is the fail-closed contract over the
parameter surface; historical mode-3 experiments are not current installer
policy.

| Class | Parameters | Contract |
| --- | --- | --- |
| Standard transport boundary | `raw_mode=0` | Both installed standard profiles keep normal HID discovery/transport. On MSHW0231, Gate5 layers the qualified mode-1 CapImg transition on this transport; on MSHW0162 no heatmap transition is enabled. |
| Diagnostic | `sl4a_debug_level`, controller `debug_trace` | Logging only. Both default to zero. |
| Activation / heatmap controls | `raw_input_beta`, `skip_getfeat`, `gate3_observe_only`, `getfeat_delay_ms`, `setfeat_speed_hz`, `wire_double_opcode`, `setfeat_no_double`, `read_frame_variant`, `skip_vendor_stop`, `raw_fallback_on_reset`, `raw_pre_desc_reg0`, `raw_b1f8109_preset`, `acpi_probe_power_cycle`, `sync_timeout_ms`, `stream_watchdog_ms`, `stream_watchdog_max_retries`, `get_noread`, `raw_handshake_first_ms`, `raw_no_enable`, `raw_watchdog_teardown`, `std_raw_transition` | These controls can change feature traffic, framing, or heatmap publication. The MSHW0231 standard installer deliberately pins `raw_input_beta=1 gate3_observe_only=1 getfeat_delay_ms=0 wire_double_opcode=1 get_noread=0 std_raw_transition=1`; MSHW0162 retains only `wire_double_opcode=1`. The explicit raw profile and all other combinations remain experimental. |
| Standard-mode feature/recovery controls | `std_liveness_ms`, `std_liveness_recover`, `skip_std_getfeat`, `wait_reset_kick_ms` | The MSHW0231 Gate5 installer sets `skip_std_getfeat=1` and pins `std_liveness_ms=0 std_liveness_recover=0 wait_reset_kick_ms=0`. This prevents generic HID feature GET_REPORT traffic from competing with the qualified activation sequence without enabling speculative liveness recovery. MSHW0162 leaves these at compiled defaults. Nonzero liveness/recovery/kick values remain experimental. |
| CapImg tracker pipeline | `blob_min_weight`, `ema_alpha`, `dfa_data_offset`, `ghost_dist`, `grid_cols`, `grid_rows`, `blob_debounce`, `blob_lift_frames`, `hold_frames`, `pre_assoc_ratio`, `blob_max_distance` | Applies to decoded CapImg frames in the production SL4 multitouch path as well as the legacy diagnostic transport. Input-quality qualification is still in progress. |
| CapImg contact calibration | `invert_x`, `invert_y`, `swap_xy`, `calib_scale_x`, `calib_scale_y`, `calib_offset_x`, `calib_offset_y` | Applies to heatmap-backed contact publication. |

CapImg calibration and tracker controls are read-only after module load. Run a
new controlled profile for every parameter set; do not mutate a live touch
stream.

### Wire format of the host→device frames

`wire_double_opcode` defaults to `0`, which sends exactly what the Windows stack
puts on the bus: one `0x02` opcode, and the constant `0C EE 5B` trailer on the
short command bodies (SET_POWER, SET_FEATURE Report ID 5). Setting
`wire_double_opcode=1` restores the legacy Linux form — the opcode sent twice
(`02 02 ..`) and a zeroed trailer — for A/B experiments. Note: both installer
profiles currently set `wire_double_opcode=1`; the single-opcode form is the
code default, not the installed default.

The frames live in `driver/spi-hid-wire-frames.h`; `tests/wire_frames_test.c`
compares every frame in both modes against the reference bytes
(`captures/wintrace/surface_init.csv`, TXN 634377432 onwards) and runs in
`make -C tests test`.

`setfeat_no_double` is deprecated and kept only so existing `modprobe.d` drop-ins
keep loading. `setfeat_no_double=1` asks for the SET_FEATURE frame without the
doubled opcode, which is the default now, so it only takes effect as an override
of `wire_double_opcode=1` — and then on the SET_FEATURE frame alone. Use
`wire_double_opcode=1` to experiment with the legacy form.

### Legacy raw-transport regression triage

Four load-time-only knobs restore or bisect the raw dialect the panel last
answered on. All default to `0` and are set only for a labelled run.

- `skip_vendor_stop` skips the pre-`DESCREQ` teardown and power preamble
  (`vendor_stop`, D2, D0) in `spi_hid_vendor_init()`.
- `raw_pre_desc_reg0` skips the probe-time stream-register force and reads every
  pre-`DONE` frame from the descriptor's input register — still `0` until a
  descriptor parses, the register the panel answers on — instead of `{3, 0x0A}`.
- `raw_fallback_on_reset` gives up to the hardcoded fallback descriptors on the
  first poller `RESET_RSP` instead of draining the reset and retrying.
- `raw_b1f8109_preset` is the one-switch restore of that whole dialect: doubled
  writes on every frame (`02 02 ..`), the pre-`DONE` register-0 reads, the poller
  give-up, and no `STOP` frame (D2/D0 unchanged). It turns those behaviors on
  regardless of their own knobs, so it is not combined with the three above.

### Read-approval shape

`read_frame_variant` (driver default `1`, LEGACY) selects the read-approval frame:
`1` = the five-byte Linux field-qualified form (`0B <reg3> FF`, register in the address field); `0` = the Windows-captured nine/ten-byte reference shape (register at offset 7 and, for body reads, request type/content ID); `2` = both. The Gate-3 raw checkpoint explicitly overrides the driver default with `read_frame_variant=0`. Older Linux field results showing variant 0 silent remain valid measurements of that older stack; they do not turn variant 1 into a Windows observation.

Header-read length is separate from the approval shape: pre-DONE header reads
are nine bytes in both modes (`spi_hid_hdr_len()`), sixteen only for the raw
DONE stream. A sixteen-byte pre-DONE read over-clocks the bare answers and
stalls discovery the same way a wrong approval does.

### Gate-3 ACPI lifecycle

On `gate3-arch-A`, `acpi_probe_power_cycle` is deprecated and ignored. Gate 2
replaced the old experimental `_PS3->_PS0` probe cycle with an observed contract:
activation is `_PS0->_RST`, suspend/deactivation is `_PS3`, and resume is
`_PS0->_RST` followed by rediscovery.

### Feature reads

`skip_getfeat` defaults to `0` on `gate3-arch-A`. The Gate-2 golden trace
established the raw post-RDESC sequence as `SET_FEATURE 0x56 -> GET_FEATURE ID6
(+ reply) -> SET_FEATURE ID5=1`, so the installer's Gate-3 raw profile explicitly
sets `skip_getfeat=N`. Setting it to `1` is now a legacy A/B override rather than
the reference path.

The ID6 reply is retained in `struct spi_hid_getfeat6` and logged as hex plus
IEEE-754 values at debug level 2; nothing acts on those values yet.

`gate3_observe_only` defaults to `1` and is explicitly set by the Gate-3 raw
profile. If the first checkpoint handshake stalls, the watchdog and generic
error handler record the state but do not inject the older D2/D0/retry/fallback
traffic, preserving the first failure for comparison with Windows. In this mode
ID5 is also withheld unless the immediately preceding ID6 response validates as
content ID 6 with the observed 122-byte total content length.

`raw_no_enable` defaults to `1` on Gate 3. This suppresses the historical
second `SET_FEATURE 0x56` when the sequencer reaches `DONE`; Windows sends 0x56
once, before GET6.

`getfeat_delay_ms` remains `0`. Gate 3 uses the directly observed T2 timing
neighborhoods in the inline golden path rather than the older multi-second
settle hypothesis.

`sync_timeout_ms` defaults to `6000` and bounds every synchronous request
this driver issues — feature queries; descriptor geometry is learned through
the DESCREQ sequencer path, not through synchronous requests. Probe clamps
the read-only value into `[100, 60000]`: a negative value would wrap
`msecs_to_jiffies()` into the far future and a `0` would turn every missed
response into an instant timeout. 6000 ms covers the measured ~3.6 s
settle plus the ~5.9 s documented worst case; the pre-fix hardcoded 1000 ms
timed out on a cold-boot feature query and killed the touchscreen (issue
#4). A feature-query timeout is non-fatal — the input stream is IRQ-driven
and independent of feature queries.

### Frame-age gates (open item)

The Windows PSDB record carries **two** frame-age gates: `+0x1fb = 3` and
`+0x1fc = 5`. We implement the `3` as `blob_debounce` (both count frames before a
new contact is published); the `5` has **no counterpart**. Its semantics are not
established — it could be a release/hold bound or a second age test — so it is
recorded here as an open item rather than guessed into a knob. `hold_frames`
therefore keeps its default of `0`; do not raise it to `5` until the Windows
meaning of `+0x1fc` is decoded. See `docs/WINDOWS-ALIGNMENT.md`.

## Per-device defaults (selected by ACPI ID at probe)

The probe logs a `device config:` line in dmesg with the active geometry.
`grid_cols`/`grid_rows` are set from this config when they are left at 0:

| Device | ACPI ID | Grid | CapImg raster samples | Baseline frames | Baseline recovery EMA alpha |
| --- | --- | --- | --- | --- | --- |
| Surface Laptop 4 AMD | `MSHW0231` | 72×48 | 3456 | 30 | 7 |
| Surface Laptop 3 AMD | `MSHW0162` | 78×52 | 4056 | 33 | 7 |

The baseline recovery alpha (7 on both devices) is the Windows-documented
12.5% recovery rate: `new = (7·base + raw)/8`. The `ema_alpha` parameter is
position smoothing only and is unrelated (default 2).
