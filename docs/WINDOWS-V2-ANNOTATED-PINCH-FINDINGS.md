# Windows V2 pinch: physical-contact annotations (2026-10-17)

The operator repeated the one-handed pinch in the guided V2 test.
This trial supplies a new and important distinction: **two fingers were
physically touching at multiple times when the test application reported
only one active Windows pointer**. Earlier statements that Windows
tracked every pinch correctly are therefore superseded.

## Aggregate findings

- 22 DOWN and 22 UP events; no unmatched IDs, duplicate DOWN,
  capture-loss messages or pointer API errors.
- Pinch stage: 780 samples at approximately 10 Hz: 550 with two
  application-visible contacts and 230 with one.
- 13 operator M-key annotations affirming two physical fingers;
  **12 recorded one active ID**; one recorded two active IDs.
- The longest continuous one-ID interval during the pinch stage
  was approximately **12.5 seconds**, with a two-finger M marker inside.
- Repeated OS-level UP and subsequent DOWN events assign different
  secondary pointer IDs during the pinch sequence.
- **15 of 19 pinch-stage UP events** occurred within approximately
  **100 screen pixels** of another active pointer's last-reported
  position. This is suggestive of close-contact suppression/merging
  or lift classification, not proof of a fixed threshold.
- The most recent Win32 pointer-frame count agreed with the active
  OS pointer count during M-marked discrepancies; both are from
  the *same* Windows pointer pipeline and do not independently
  establish what the capacitive sensor reported.

**Analysis limits:** The M annotations establish the operator's
physical-contact observation only at specific moments. Do not
interpret 230/780 as a sensor failure rate. This trial was not
synchronized with raw CapImg frames or internal HeatCore callbacks,
and the exact stage responsible for lost contacts is unresolved.
The original recordings, including screen coordinates, remain private.

**Next research step:** Capture simultaneous sensor/HeatCore and
OS pointer evidence while recording the same physical two-finger
gestures and M markers. Compare the recovered classifier and
hold/lift decision to the corresponding actual sensor peaks.
Do not modify Gate5 or the kernel driver based on these
unsynchronized observations alone.
