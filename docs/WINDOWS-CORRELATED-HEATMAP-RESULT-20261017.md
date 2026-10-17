# Windows correlated pinch: the sensor raster at physical two-finger mismatches

**Date:** 2026-10-17. **Evidence level:** one same-session Windows WPR
SPI/CapImg collection, Windows application-facing Win32 pointer V2,
and three operator M annotations of TWO physical fingers. This is
**source-backed exploratory signal analysis**, not an exact
TouchPenProcessor classification replay and not production kernel
qualification.

## Original source provenance and measured coverage

- Capture run: `SL4A-Correlated-20261017-183111` on the user's SL4 AMD
  in Windows; original WPR session and V2 pointer test overlap.
- ETL: **221,773,824 bytes**, SHA-256
  `23ee9ad0df5703458a15bd4741acdb910041f84edeef908cce73f0775c7acb30`.
- CSV export: **656,619,526 bytes**, SHA-256
  `56c9f4b3b9ee7fe526667de208dce59f8a150f7372448a218783e11075502131`.
- V2 `pointer/events.csv`: SHA-256
  `530c574a1aae4b07c8d611d32ea2ddf4962fc8da1c78997f0b6665c9a2c7a474`.
- WPR CSV parses **16,608 complete SPB transactions** with no
  reported transfer parser errors or unfinished activities.
- Strict validated `0x0C` CapImg frames: **8,232**, each a
  **4,304-byte full V0 body** with a **72 x 48 x 8-bit =
  3,456-byte raster** and additional metadata/vendor sections.
- **Zero Surface TouchAndPen events** in the `tracerpt` source
  as decoded by the audit. The processing-stage classifier output is
  **not available** from this session, even though raw input is.
- The original V2 pointer session reports **7 DOWN/7 UP**, zero orphan
  UP/duplicate DOWN/API errors, max two simultaneous IDs, 4 new
  DOWN/UP pairs in the pinch stage. Three M annotations each recorded
  **OS ID 82 alone** with native pointer-frame count 1.

## Investigative signal analysis

The extractor preserves both the raw frame ordering and a
`clock_100ns_raw` number. The relative first-to-last raw sensor
frame span, **92.350645 seconds** when the header clock is scaled
to 10MHz, agrees closely with the relative first-to-last OS
contact lifetime (first DOWN 22:31:35.653 UTC; last UP
22:33:07.814 UTC = **92.161 seconds**).

A **single 10.107-second sensor-frame gap** occurs at raw frame index
1223, fitting the gap between OS contact 80 UP at
22:31:47.671 and OS contact 81 DOWN at 22:31:57.928.
The sensor's transition from two substantial far-apart blobs
to one blob near OS UPs and back to two near new DOWNs also
matches at the scale of tens to hundreds of milliseconds.

**Timing caution:** Absolute `Clock-Time` to UTC was NOT
independently calibrated using source ETL clock metadata.
An approximate comparison provisionally anchors raw frame 0 to
the first OS DOWN. This aligns the no-touch gap and multiple
contact births/releases, but cannot justify claiming an exact
frame-to-M synchronization or a millisecond causal latency.

### Defined research heuristic (NOT Microsoft's actual classifier)

For a single raster, mark grid cells with value strictly less than
a chosen threshold. Group them by **8-neighbor connected components**,
and only count a region if it occupies **at least three grid cells**.
Repeat at thresholds **125, 135, 150, and 165** on the original byte
samples; the large majority of background cells are about 180.
These are sensitivity-check thresholds, **not calibrated
CapImg C590 classes nor hardware touch-decision cutoffs**.
A single connected region can still contain multiple local peaks,
merged fingertips, or history-derivable contact tracks.

- At approximate raw elapsed **24.5 seconds**, in the
  two-finger **far-separated** hold, there are **two spatially
  distinct regions** under all four thresholds, near grid
  centroids (42,9) and (37,38) at threshold 135.
- Operator M1, **22:32:33.798 UTC**, estimated raw frame 4809
  (~58.143s): only one substantial component near grid (39,25)
  at all four thresholds. The surrounding ±0.25-second
  window contains about **50/50 frames with exactly one
  region** at each of 125/135/150/165.
- M2, **22:32:40.715 UTC**, estimated raw frame 5502
  (~65.064s): one component near (39,25), also
  **50/50 frames with exactly one region** at all four
  thresholds over ±0.25 seconds.
- M3, **22:32:51.605 UTC**, estimated raw frame 6592
  (~75.953s): one dominant component near (37,23);
  **50/50 frames with exactly one region** at thresholds
  150 and 165 over ±0.25 seconds. At lower
  threshold 125, some frames have *no* three-cell qualified
  region, not two; threshold 135 likewise occasionally
  yields no qualifying region. Isolated small subthreshold
  cells can occur within or immediately adjacent to the
  region and must not be prematurely dismissed as noise.
- After re-separation, raw and OS streams both return to
  two well-separated regions/IDs (example at estimated raw
  83.0s, centroids ~[48,15], [23,29]).

Thus **the downstream Windows one-ID observation coincides with
only one qualified distinct CapImg signal region at all three
operator-marked moments**, compared with two clear CapImg
regions when the same two fingers are held far apart.

This makes a simplistic "two clean separate raw sensor peaks
were ignored solely at OS pointer egress" hypothesis less
plausible than **peak proximity/overlap or upstream
suppression / insufficient raw separation**.

**It does not establish the root cause.** At close spacing,
two physical fingertip responses might merge into one
raster region. The intact structure could contain multiple
minima that a model with history could demerge. Firmware
and acquisition effects are also plausible. This analysis
does not prove that Windows HeatCore, TouchPenProcessor,
sensor hardware or Linux tracker specifically *caused*
the raw signal to have one dominant component.

### Next technically decisive work

1. Derive the **actual** TouchPenProcessor peak/centroid/quality
   conditions from already-recovered historic 0C19 function bodies
   and map those to input heatmap frames. Do not substitute the
   provisional connected-component heuristic for Windows logic.
2. Verify raw WPR-clock to UTC mapping using ETL session clock
   metadata and correlated input transitions before making
   exact per-frame claims.
3. Replay the recovered continuous raw raster sequence around
   M1–M3 (including 1–2 seconds before and after) through a
   source-grounded offline classifier/association model. Test
   whether one merged region should maintain **two prior tracks**,
   and whether a model should lift one or hold it temporarily.
4. Distinguish persistent contact during close-finger
   occlusion from false "ghost" contact after genuine
   physical lift. **No unqualified hold-timer patch** is safe.
5. Leave production Gate5, in-tree kernel experiment and Syax
   upstream PRs unchanged pending physical qualification.

## Public release recommendation

The full `capimg-frames.hex` is **not raster-only**. It contains
4,304-byte bodies with **3,456-byte raster plus additional
header/vendor payload**. Publishing the raw ZIP also publishes
time-stamped Windows screen X/Y pointer traces and WPR host
metadata; the ETL can contain arbitrary unrelated OS events.

A suitable public reproducibility dataset should instead isolate:
- The **72x48 raster bytes only**, extracted from strict V0 0x0C
  section decoding (without the other V0/vendor sections).
- A sequence ID and **relative elapsed millisecond/10MHz clock**
  values, not host absolute wall time; retain cadence and gaps.
- User's generic gesture-stage labels and confirmed two-finger
  M offsets, anonymized OS contact IDs and optionally mapped
  screen coordinates only after dropping screen origin / scale.
- SHA256 references to the **unpublished originals** for
  verification without redistributing unrelated Windows traces.
- A clear statement that it is research evidence
  from a single SL4, not a Windows OS source-code oracle.

The coarse raster is not a camera image or a conventional
fingerprint record; a deliberately staged pinch is a
low-sensitivity public dataset. Nonetheless the array can
encode device-specific baseline patterns/relative touch
position and should be **opt-in** for publication.
No private raw trace files are committed with this report.
