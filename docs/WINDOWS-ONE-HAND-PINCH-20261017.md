# Windows one-hand pinch test: second OS-visible contact reference (2026-10-17)

> **Corrected guided V2 evidence:** The operator identified the sole accidental M press as the one showing two correct pointers at 19:48:15.5399695Z, leaving **12/12 intentional M annotations showing one OS pointer** during confirmed physical two-finger contact. A second guided trial reproduced this in **5/5** additional marked moments. Full follow-up: [WINDOWS-V2-REPEAT-PINCH-20261017.md](WINDOWS-V2-REPEAT-PINCH-20261017.md). The unsynchronized initial 10.92-second two-ID sequence cannot establish correctness during all close pinches.


> **Operator correction — IMPORTANT:** After reviewing the first one-handed test, the user explicitly reported the live window showed **"1" active ID during more than one physical two-finger pinch**. The earlier analysis can prove that **one 10.92-second segment** kept two OS pointer IDs; it **cannot** prove that every physical pinch was captured with two IDs. Sequential ID lifetimes elsewhere in the recording are therefore **suspicious but inconclusive** until instrumented, not casually attributed to deliberate lifting. The operator observation takes precedence over the previous assumption of full test success. Use the new four-stage [V2 pointer diagnostic](../tools/windows_capture/README.md) with the explicit **M** "two fingers physically on glass now" marker, native frame counts and stage timelines. **No driver parity claim is justified yet.**


**Status:** real, successfully captured Windows `WM_POINTER*` messages.
The operator explicitly describes this session as a **one-hand pinch test**.
This document reports **OS application-facing input only**, not synchronized
Surface CapImg frames and not the private Windows HeatCore internal tracker.

## Input file and reproducibility

- Uploaded file: `sl4a-os-pointer-20261017-152803.csv` (retained privately; **not copied into public GitHub**).
- SHA-256: `826a1e62f8e0a6dbb5654407e897997e6b493f64990f218f1ec2a91347114048`.
- 760,904 bytes; CSV has 8,947 data rows and 8 named columns.
- UTC event range: **2026-10-17 19:28:06.744385 through 19:29:03.336757**, elapsed **56.592372 seconds**.
- 8,883 `UPDATE`, **16 `ENTER`**, **16 `DOWN`**, **16 `UP`**, **16 `LEAVE`**, no `CAPTURE_CHANGED`.
- 16 unique pointer IDs **1431–1446**; every record `PointerType=2` (touch).
- No blank fields, timestamps monotonic, `StopwatchTicks` monotonic; all
  8,947 WParam low 16-bit values match the logged pointer ID.
- For **every** ID, event sequence is `ENTER -> DOWN -> UPDATE* -> UP -> LEAVE`
  with precisely one DOWN and UP. **No orphan UP or duplicate DOWN**.
- Maximum **2 concurrent Windows OS pointer IDs**; final active count **0**.
- There are **12 distinct intervals** during which two IDs overlap.
  Sixteen pointer IDs do **not** mean 16 different physical fingers:
  Windows allocates another ID for each new contact life.

## Main controlled pinch segment: uninterrupted IDs 1440 and 1441

| Metric | Observed |
| --- | --- |
| First ID | `1440`: DOWN at t=33.335 s, UP t=46.101 s |
| Second ID | `1441`: DOWN t=33.376 s, UP t=44.296 s |
| IDs simultaneously held | **10.920 s** |
| Nearest-sample 2D separation, min | **50.09 screen pixels** |
| Nearest-sample 2D separation, max | **880.30 screen pixels** |
| Separation span | **830.21 screen pixels** |
| Matched samples used | **1,093** |
| Samples separated <=75 px | **272** (~2.72 s at ~100 samples/s, not a frame-exact duration) |
| Source of ID continuity | No UP for either pointer during their common 10.920 s interval |

Separation calculated as
`sqrt((ScreenX_1440-ScreenX_1441)^2+(ScreenY_1440-ScreenY_1441)^2)`.
Each timestamp from ID 1440 was matched to its **nearest** ID 1441
event within **25 milliseconds** (`pandas.merge_asof`), so the values
are approximate paired positions rather than necessarily simultaneous
sensor coordinates. Screen pixels are **not calibrated physical distance
or heatmap-grid cells**.

A 21-sample (~0.2-second) centered median filter of separation reveals
five large opening peaks and five closing troughs **without either ID
being released**:

| Sequence | Opening peak, time since capture / separation px | Closing trough, time / separation px |
| ---: | --- | --- |
| 1 | ~34.04 s / 847 px | ~34.80 s / 63 px |
| 2 | ~35.84 s / 872 px | ~36.49 s / 63 px |
| 3 | ~37.53 s / 727 px | ~39.45 s / 62 px |
| 4 | ~40.21 s / 713 px | ~41.07 s / 57 px |
| 5 | ~41.88 s / 721 px | ~42.74 s / 51 px |

The final raw nearest-sample minimum is 50.09 px at capture t=42.785 s.
**Both OS pointer IDs remain active for approximately 1.51 further
seconds** before 1441's UP at t=44.296 s (1440 later UP at t=46.101).
This is positive reference evidence of **one-handed pinch open/close
input with sustained OS contact identities through multiple close approaches**.

## Other repeated one-handed pinch intervals

- Contact `1431` continuously active **23.436 s** (t=0..23.436);
  it overlaps **seven** sequential IDs `1432–1438`, one at a time.
  New secondary contacts follow previous UP events by
  **1.022, 0.444, 0.343, 0.420, 0.103, 0.545 seconds**.
- Contact `1443` continuously active **8.159 s**
  (t=48.402..56.561), overlapping `1442`, then `1444`,
  `1445`, and `1446`.
- The closest paired event separation in the *whole session* was
  approximately **31.0 pixels** for pair `1443/1445` near the second
  contact's release at t=55.595 s; this alone is not proof of
  sustainable contact separation through close-range interaction.
- Pair `1431/1437` came within **38.6 px** at ~18.84 s and
  remained jointly active another **~1.92 s** before `1437` UP.
- The `1440/1441` uninterrupted segment is by far the strongest
  contact-continuity and pinch geometry reference here.

**Interpretation boundary:** The sequential new IDs in the other
segments might correspond to deliberately lifting/replacing one
finger, or the device deciding to terminate/restart a continuous
physical finger. **Only the operator (or video/independent physical
ground truth) can distinguish those scenarios.** Do NOT infer that
these ID changes constitute a Windows tracking defect, or that all
eight consecutive contacts are the same physical finger.

## Comparison to preceding Windows pointer recording

The earlier separately uploaded `sl4a-os-pointer-20261017-152502.csv`
was **6,230 events, five balanced DOWN/UP contacts, maximum two
simultaneous OS pointers**. A final staggered lift preserved the
remaining pointer for ~2.914 s after the first UP.
This new file is **8,947 events, 16 balanced contact lifetimes,
12 overlapping two-ID intervals** and adds a much stronger **10.920-s
five-cycle pinch reference**, with two unchanged IDs during large
opening/closing movements.

## Why this matters for Linux SL4A multi-touch

* A Windows-equivalent contact tracker should ideally preserve
  **stable application-level contact IDs throughout repeated pinches**,
  even when the two contact locations approach to roughly 50 screen
  pixels **in this recorded display coordinate system**. It should
  emit independent, balanced lift events. These are *outcome criteria*
  for comparison; do not hardcode 50 px as a Linux track merge threshold.
* The HeatCore 26100.9278 static audit establishes two reporter paths
  and mask/copy of contact flags but does **not** yet prove exactly
  which private track state maps to these OS IDs. Avoid conflating
  this `WM_POINTER` ID with a CapImg blob label, 0x34 plugin field,
  or 0x21 HID ContactID.
* Neither this CSV nor the earlier CSV was collected simultaneously
  with the 1,422 archived sensor frames; therefore **Windows-vs-Linux
  contact classification on an identical raw sensor frame remains
  unmeasured**.
* Production Gate5 and upstream PR #87/#88 must not be modified
  merely on the strength of an unsynchronized pointer trace.

## Suggested offline comparator metrics

For a *future aligned, same-gesture* Windows/SL4A comparison:
preserved two-pointer identity duration, approach/minimum distance,
continuous finger-update coverage, ID churn, overlapping lifetime,
time-to-lift and balanced DOWN/UP, then (only with simultaneous raw
frame capture) blob/classifier-to-OS-contact correlation.
The present recording by itself is sufficient to benchmark
**Windows OS pointer continuity and pinch behavior**, not the
private classification pipeline.
