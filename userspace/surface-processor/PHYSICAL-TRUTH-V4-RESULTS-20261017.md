# SL4A guided V4 physical-truth result (2026-10-17)

## Scope and integrity

This is a sanitized aggregate report from the private guided V4 evidence bundle
with SHA-256:

`e490793616d6668419887ae609289b4bc348a2adddd6a38b3c6d415e7ee21ab7`

The capture contains 17,018 strictly decoded V0 `0x0c` CapImg frames,
34,297 complete SPB transactions with no unfinished transaction or parser
error, balanced Windows pointer lifetimes (14 DOWN / 14 UP), no capture loss,
and all 19 guided holds.  No hold was corrected or invalidated.  Private
heatmaps, screen coordinates and absolute timestamps are not published here.

The operator confirmations are human observations, not an instrumented finger
fixture.  V4 reduces ambiguity by accepting only SPACE, automatically holding
each confirmed state for two seconds, and marking every transition UNKNOWN.

## Direct monotonic-clock alignment

The frame `clock_100ns_raw` values and the pointer logger's
`StopwatchTicks` are directly comparable in this session.  The first sensor
frame precedes the first Windows DOWN by about 18 ms.  The raw stream's single
10.208-second pause brackets the all-fingers-up interval between the horizontal
and vertical trials; the first frame after that pause precedes the next Windows
DOWN by about 1.8 ms.  Nearest raw frames for all in-coverage V4 confirmations
are within 6.2 ms.

This establishes the shared boot-relative QPC scale for this run without
converting it to UTC.  It does not establish a universal conversion rule for
unrelated ETL files.

## Windows physical-state result

The conservative analysis discards the first 350 ms and final 150 ms of every
two-second labelled hold.  Empty and one-finger controls had no sustained
Windows count error.  Two intervals did:

| Guided hold | Physical | Windows samples | Longest mismatch |
| --- | ---: | --- | ---: |
| Horizontal close, both still down | 2 | 14/14 showed 1 | 1.436 s |
| Vertical top finger returned close | 2 | 8 showed 1, then 6 showed 2 | 0.788 s |

The second result includes repeated Windows birth/lift churn before a stable
new pointer appeared.  Far-separated two-finger controls returned to two
Windows pointers in both orientations.

## Frame-aligned sensor result

The following is an exploratory sensor-region proxy, not Microsoft's contact
classifier: byte values below 125/135/150/165 are grouped with 8-neighbour
connectivity and regions smaller than three cells are discarded.

| Hold | Windows | Raw-region observation |
| --- | --- | --- |
| Horizontal two apart | 2 | 2 regions in all 155 frames at all four thresholds |
| Horizontal close failure | 1 | 1 region in all 160 frames at all four thresholds |
| Vertical close light, established tracks | 2 | 1 region in all 150 frames at threshold 150; threshold 165 alternated 1/2 |
| Vertical close firm, established tracks | 2 | 1 region in all 153 frames at threshold 150; threshold 165 was 1 in 118 frames and 2 in 35 |
| Vertical top deliberately lifted | 1 | 1 region in all 157 frames at all four thresholds |
| Vertical top returned close | 1 then 2 | 1 region in all 153 frames at all four thresholds |
| Vertical two apart again | 2 | 2 regions in all 159 frames at all four thresholds |

This proves that a thresholded region count is insufficient in both directions:
Windows can maintain two established pointers through one connected sensor
region, and can eventually birth a returned pointer while the same proxy still
contains one region.

## V3 morphology rule falsified

The prior V3 trial suggested retiring an internal shadow after simultaneous
relative collapse in threshold-150 mass and major weighted variance.  V4
contains the opposite controlled result:

| Conservative hold median | Physical | Mass | Major variance |
| --- | ---: | ---: | ---: |
| Vertical close firm, both down | 2 | 155 | 0.393 |
| Top deliberately lifted | 1 | 217 | 0.433 |
| Bottom-only control | 1 | 231 | 0.577 |
| Top returned close | 2 | 246 | 0.568 |

After the genuine lift, both morphology fields increased instead of
collapsing.  The current diagnostic shadow replay consequently kept a shadow
through all 157 raw frames of the deliberate-lift hold.  If that shadow had
been emitted as a contact, it would have created exactly the ghost finger the
guardrail is intended to prevent.

The full replay remained safe because shadows are internal only: 17,018 frames,
11 diagnostic occlusions, 9 proposed reassociations, zero reused identities,
zero shadow-emitted contacts, and zero morphology releases.  Its threshold-150
prototype also showed only one visible candidate throughout several holds in
which Windows correctly showed two, so it is not a Windows-output oracle.

## Engineering consequence

1. Do not promote the V3 mass/variance ratios into the kernel, userspace output,
   or an unconditional hold timer.
2. Keep the shadow overlay diagnostic-only.  It may remember an ambiguity, but
   it cannot safely decide physical presence or emit a second contact.
3. Treat established-track continuity and close second-finger birth as distinct
   problems.  V4 shows Windows behaving asymmetrically between them.
4. The next useful work is a source-grounded temporal feature replay of the
   recovered candidate/classification/hold routines (`FUN_180600c40`,
   `FUN_180601690`, `FUN_180606370`) against these labelled intervals.  Simple
   connected-region and two-field morphology rules are exhausted.
5. No new hardware capture is needed until that richer replay produces a
   falsifiable prediction.  Production Gate5, the experimental kernel branch
   and upstream #87 remain unchanged.

## Frame-aligned oracle and measured comparison baseline

`windows_pointer_oracle.py` now reconstructs an OS-visible Windows pointer
snapshot for every one of the 17,018 raw frames. It verifies the original CSV
hash, monotonic clocks, balanced lifetimes, all guided holds and no active
pointer at exit. The coordinate-bearing JSONL remains private.

A general affine fit from 1,123 conservative one-pointer/one-region samples to
the threshold-150 sensor proxy measured:

```text
sensor_x =  0.031084500254 * screen_x + 0.000659324595 * screen_y - 0.327983122275
sensor_y = -0.000026187660 * screen_x + 0.031591444533 * screen_y - 0.229208157638
```

Training RMSE was 0.183 sensor cells. On 1,000 independent two-pointer/two-
region frames (2,000 assigned contacts), median error was 0.294 cells, p95
0.695, RMSE 0.409 and maximum 0.819. This is a measured coordinate transform
to a connected-region centroid **proxy**, not proof that the proxy is the
Windows detector or classifier coordinate.

The unchanged default research processor was then replayed over all 17,018
frames and compared with complete frame coverage. In the 2,484 conservative
guided-hold frames it matched Windows **contact count** in 1,611 frames. This
64.8551% count-only result is not a parity score. The failures locate the work:

- horizontal returned-left: prototype produced zero/one where Windows had two;
- horizontal returned-right: prototype stayed one for all 150 frames while
  Windows had two;
- vertical close light: prototype stayed one for all 150 while Windows had two;
- vertical close firm: prototype reached two in only 34/153 frames;
- vertical returned top: prototype stayed one through all 67 frames after
  Windows returned to two;
- two horizontal one-finger controls also exposed long prototype zero-contact
  intervals from provisional baseline/birth behavior.

Across all frames and a 2.5-cell match gate, 19,797 Windows contacts matched,
7,553 were missed and none were counted as extra; mean matched-coordinate error
was 0.293 cells. These numbers describe this prototype/configuration and this
capture only. They do not prove zero ghost risk outside the labelled controls.

Reproduce the private aggregate replay without exporting heatmaps:

```text
python3 physical_truth_shadow_replay.py /path/to/V4-run \
  --output /tmp/shadow-physical-truth-v4.json
python3 windows_pointer_oracle.py /path/to/V4-run \
  --output /tmp/windows-pointer-oracle.jsonl
python3 v4_oracle_contract.py /tmp/windows-pointer-oracle.jsonl.summary.json
```

The replay now reports V4 confirmation markers and conservative guided-hold
histograms.  Empty holds correctly report no raw frames because this CapImg
stream pauses when no touch is active.
