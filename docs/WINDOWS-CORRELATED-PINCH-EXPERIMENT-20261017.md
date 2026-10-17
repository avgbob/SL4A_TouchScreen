# Windows correlated raw-sensor + OS pointer pinch experiment

**Purpose (2026-10-17):** The surface's Windows OS pointer layer
repeatedly reported only one finger during operator-confirmed
two-physical-finger close pinches: 12/12 deliberate M observations in
the first V2 trial plus 5/5 in a second guided V2 trial. **23/27** of
the secondary UPs in those trials were at <=100 *reported screen pixels*
from the other contact. This is not a sensor-classifier root cause.
The single 0x0C heatmap signal was NOT captured at matching UTC times.

## Ready-to-run instrumentation (Windows; research only)

- [`tools/windows_capture/capture_pinch_correlated.ps1`](../tools/windows_capture/capture_pinch_correlated.ps1)
  runs existing `touch_boot.wprp` WPR profile and
  [guided V2 pointer recorder](../tools/windows_capture/capture_os_pointer_contacts_v2.ps1)
  **concurrently**, and stops WPR in a protected finally block.
  It does not reboot, switch the touchscreen's PnP state, send HID
  control commands, replace Windows drivers, or cancel other WPR
  sessions. An already-running/conflicting WPR trace must be allowed
  to finish before this experiment.
- The original WPR ETL and **tracerpt CSV** are retained under a
  unique `Desktop\SL4A-Correlated-YYYYMMDD-HHMMSS` directory.
  Its `pointer\` subfolder contains the V2 `SUMMARY.txt`,
  `events.csv`, `samples.csv` files and operator M timestamps.
  A `manifest.json` provides hashes and sizes; `coordinator-markers.tsv`
  records UTC trace start/stop/export phase boundaries.
- The [offline coverage audit](../tools/windows_capture/analyze_correlated_pinch.py)
  checks both actual contact/annotation lifetimes **and** for
  recovered *complete, decodable* 4304-byte V0 input 0x0C CapImg
  bodies (72x48 heatmap). It reports
  `RAW_CAPTURE_MISSING_OR_NOT_DECODED` rather than inventing a
  sensor reference. The public CI test builds a fully synthetic
  structurally valid heatmap and confirms raw-negative detection.
- Windows PowerShell 5.1 parser and V2 C# selftests plus the
  correlated collector's asset/GUID selftest are run on GitHub
  Windows Actions. **Not hardware-qualified on this Surface yet**.

## User procedure (one repeat is enough if all trace coverage checks pass)

On the **Surface running Windows**, open **Windows PowerShell as
Administrator**; paste the full setup + capture command in
[Windows capture README](../tools/windows_capture/README.md).
Expect Windows UAC/admin permission. Do not run WPR sessions
for other tasks concurrently. Ensure >=2 GB free space.

The dark V2 screen is the touch target. Press SPACE to start and
advance. At each stage:

1. ONE FINGER: touch/drag/lift to establish the baseline.
2. TWO APART: place thumb and index finger wide apart and hold
   *simultaneously* at least five seconds. **Do not lift at the end**;
   use the other hand to press SPACE.
3. PINCH: move **the same two continuously touching fingers** slowly
   toward one another; pause with fingertips close but visually
   distinct; separate again; repeat three times. If the big
   **active ID count says 1 while both fingers are physically down**,
   press **M** once for that discrepancy. Hold positions for a
   moment at M where practical (no pressure on panel). Record
   visually whether a fingertip physically lifted by mistake.
   Use SPACE to advance, ideally with both fingers still down.
4. STAGGERED LIFT: lift just one finger, hold the other for three
   seconds, then lift it. Press SPACE to finish (or ESC to preserve
   a partial attempt). The coordinator automatically stops WPR
   and preserves ETL. CSV export is attempted afterward; it
   may be large.

No microphone/video camera is used; full-window raw pointer X/Y
are nevertheless potentially sensitive. **Do not publish raw traces
on a public GitHub repository.** They may contain peripheral system
events collected by WPR.

## Evidence gates and decision logic

**Gate A — recorder:** report includes `DOWN`, `UP`, and physical
M markers with correct UTC time and stage. V2 OS message IDs are
NOT raw touch controller track IDs.

**Gate B — Windows ETW WPR:** WPR starts/stops cleanly and original
`pinch-runtime.etl` exists with nonzero length. If `tracerpt`
export fails, do not repeat the gesture; retain ETL and export
offline with the existing helper.

**Gate C — raw heatmaps recovered:** parse tracerpt's SPB provider
transfers by Activity ID and FromDevice direction, reconstruct
4304-byte body (`CE 10 0C`) after the optional 5-byte prefix, then
strictly decode CapImg raster and vendor section. **WPR providers
being present proves NOTHING about raw bytes in the trace**; if
`decoded_complete_0c_frames=0`, this gate is OPEN and no
sensor-vs-software blame can be established.

**Gate D — synchrony:** align ETL event timestamps against pointer
event UTC on the **same Windows session**. Tracerpt `-rts`
`Clock-Time` might be QPC, not UTC; **do not equate them by
parsing the numbers as wall clock**. Use Windows ETL metadata
and explicit clock mapping before frame-by-frame matching M presses.

**Gate E — classification:** at independently matched M events,
check number/distance/shape of actual raw peaks (not OS pointer
positions), feed corresponding frames to offline recovered
TouchPenProcessor stages, and compare candidate/track/final
Windows output. Possible outcomes:
- Only one distinguishable raw peak: sensor resolution, hardware
  processing or physical touch geometry may underlie the problem.
- Two distinguishable raw peaks, one published pointer: an upstream
  software/firmware or reporting decision is implicated, but
  *which component* remains to be traced.
- Two raw peaks and two emitted contacts, only one observed in test
  window: investigate pointer reporting/window semantics.

Neither a raw bitmap nor a historical decomp function alone
settles whether `FUN_180601690` classification or
`FUN_180606370` quality-gated lift is culpable.
No changes to production Gate5, upstream PR #87, or the separate
in-tree kernel branch are authorized by this experiment.

## Retained expected outputs

```text
Desktop/SL4A-Correlated-YYYYMMDD-HHMMSS/
  coordinator-markers.tsv
  capture-profile.wprp
  wpr-start.log  wpr-stop.log  wpr-profiles.log
  pinch-runtime.etl
  pinch-runtime.csv            # if tracerpt export works
  tracerpt.log                  # if export attempted
  manifest.json
  pointer/
    events.csv
    samples.csv
    SUMMARY.txt
```

First upload `pointer/` + `manifest.json` + `coordinator-markers.tsv`
and `tracerpt.log` if necessary. Upload
`pinch-runtime.csv` if feasible; preserve the original ETL
locally for any richer time alignment / provider metadata.
