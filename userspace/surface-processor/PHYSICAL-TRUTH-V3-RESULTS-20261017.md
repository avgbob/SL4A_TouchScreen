# SL4A V3 physical lift versus close-contact result (2026-10-17)

## Scope and integrity

This is a sanitized aggregate report from the private V3 evidence bundle with
SHA-256:

`f8526b7085b8260abc4261419b70a26ecd24ad4f4dbee80ccb0f721e49c44cd8`

The capture contains 13,095 complete V0 `0x0c` CapImg frames, balanced Windows
pointer lifetimes (5 DOWN / 5 UP), no capture loss, no native pointer API
failure, and an explicitly marked deliberate one-finger lift and return.

The operator reported one accidental `N` keypress at
`2026-10-18T01:07:10.7217309Z` in stage 4. It is retained in the raw evidence
but excluded here. It incorrectly labels the interval until the valid `L`
marker at `01:07:22.8591878Z`; it did not alter pointer or CapImg capture.

Human key annotations remain less exact than video or an instrumented contact
fixture. No private heatmaps or pointer logs are published in this repository.

## Clock result

The WPR `Clock-Time` values and the observer's `Stopwatch.GetTimestamp()` values
are the same approximately 10 MHz boot-relative QPC timebase in this capture.
Pointer-event UTC versus Stopwatch deltas estimate 9,999,947 ticks/second over
155.576 seconds. Nearest raw-frame differences at in-coverage operator and
pointer transitions are normally below 6 ms.

This removes the earlier behavioral-offset approximation for this V3 session.
It does not establish a universal UTC conversion for unrelated recordings.

## Controlled discrimination result

Immediately before the deliberate physical lift, Windows continued reporting
two pointers through a continuous 2.804-second interval in which the simple
threshold-150 sensor analysis produced only one connected region. The
exploratory smoothed-peak detector produced one peak for 17.803 seconds.

The raw region nevertheless changed sharply at the Windows UP event:

| Aggregate over conservative windows | Merged two before lift | One after lift |
| --- | ---: | ---: |
| Frames | 265 | 266 |
| Pixels below 150, median | 8 | 7 |
| Threshold-depth mass, median | 332 | 266 |
| Major weighted variance, median | 2.714 | 0.927 |
| Bounding width | 3 | 4 |
| Bounding height | 5 | 2 (median) |

The 100 ms bin containing the Windows UP changed from median mass about 320 and
major variance 2.86 immediately before UP to mass about 228 and variance 0.58.
This is evidence that a morphology/history gate can distinguish this real lift
from the preceding merged two-finger state even though both look like one
connected component.

## Return control and its limit

After the operator marked the second finger returned, Windows continued showing
one pointer for about 9.58 seconds before a new DOWN. In the conservative
9.087-second raw window before that DOWN, all 909 frames contained one
threshold-150 region and one smoothed peak.

That interval is important negative evidence: a tracker with only one existing
track cannot safely invent a newly returned second finger when the sensor offers
no separable second region or peak. The interval's median mass (301) was above
the clean one-finger control (275), but this single trial cannot separate finger
count from fingertip, pressure, orientation, and position. It is insufficient
for a global second-finger birth rule.

## Engineering consequence

The evidence supports a narrower experiment than a fixed hold timer:

1. Start an internal shadow only after a previously visible 2-to-1 merge.
2. Preserve that known identity while the surviving region's morphology remains
   consistent with the merged state.
3. Retire the shadow promptly after a sustained relative collapse in region
   mass and major variance, as observed at the deliberate lift.
4. Do not create a second contact from a one-track state solely because a region
   becomes modestly stronger; the return control shows why that would be unsafe.

This does **not** yet authorize automatic Linux contact emission. Thresholds
must be normalized against each track's own history and tested on the earlier
8,232-frame corpus plus additional lift orders/orientations. Production Gate5,
the experimental kernel, and upstream PR #87 remain unchanged.
