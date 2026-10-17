# Windows V2 pinch: physical-contact annotations (2026-10-17)

The operator repeated the one-handed pinch in the guided V2 test.
**Operator correction (subsequent message): one of the 13 M keypresses was incorrect; the operator has not identified which timestamp.** Preserve the raw event log exactly, but do NOT treat all 13 annotations as validated physical-contact evidence. The corrected count is **12 intentional marks**; of those, **11 or 12** had one Windows pointer depending on whether the accidental keypress was among the 12 one-pointer records or the single two-pointer record. Which marker to exclude remains unknown.
This trial supplies a new and important distinction: **two fingers were
physically touching at multiple times when the test application reported
only one active Windows pointer**. Earlier statements that Windows
tracked every pinch correctly are therefore superseded.

## Aggregate findings

- 22 DOWN and 22 UP events; no unmatched IDs, duplicate DOWN,
  capture-loss messages or pointer API errors.
- Pinch stage: 780 samples at approximately 10 Hz: 550 with two
  application-visible contacts and 230 with one.
- **13 raw M-key annotations**: **12 recorded one active ID** and one recorded two active IDs. The operator later identified **one accidental keypress** (timestamp unspecified), so **12 marks are intentional**, including **11–12 one-ID mismatches**. The exact corrected numerator is currently unresolved.
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

**Analysis limits:** The **12 intentional** M annotations establish the operator's
physical-contact observation only at specific moments; the thirteenth
keypress was accidental and its exact event has not been identified. Do not
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
