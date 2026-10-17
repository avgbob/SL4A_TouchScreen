# Public pinch dataset replay — PR #12 research baseline (2026-10-17)

**Status: completed, offline only.** This report concerns the
[public, privacy-hardened dataset](https://github.com/avgbob/SL4A_TouchScreen/tree/main/datasets/sl4a-amd-pinch)
from a one-hand pinch experiment. It is **not** a Windows classifier
reconstruction, Linux hardware qualification, or patch to Gate5.

## Verified dataset and reproducibility

- ZIP SHA-256 `2c77050b9356b141ff0b30acf0a99a896db86a31d43cde6922dca558174aed2a`
- Raster SHA-256 `fa4773c352178cb06fcbd686d5e021d98bae03af4ca4ccc94f93a2e3f63f71a9`.
- 8,232 frames, each 48x72 unsigned bytes (28,449,792 total raster bytes).
- Nominal 10 MHz frame-relative clock, **not formally UTC calibrated**.
- One genuine 10.106957-second sensor-sampling interruption between frames
  **1223 and 1224**, preserved and used to clear existing tracker history
  during offline replay. No invented frames were interpolated.
- Public event file has **7 OS DOWN and 7 UP** transitions and 3 deliberate
  M annotations recording two physical fingers versus one Windows pointer.
  OS- and raw-clock origins are separate; their close numerical offsets
  are **not proof of exact synchrony**.

```bash
cd userspace/surface-processor
python3 -m unittest discover -p 'test_*.py' -v
python3 pinch_dataset.py /path/to/SL4A_heatmaps_privacy_hardened.zip \
    --out pinch-baseline-report.json
```

GitHub Actions
[`Surface processor offline tests`](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/surface-processor.yml)
downloads the **exact publicly pinned ZIP**, verifies its SHA-256,
replays all frames and checks every M and two-finger control window.
The full JSON report is retained as the workflow artifact
`sl4a-public-pinch-processor-baseline`.

## Full existing processor results

| Existing PR #12 output | Frame count |
| --- | ---: |
| Two emitted contacts | 4,637 |
| One emitted contact | 3,529 |
| Zero emitted contacts | 66 |
| Two detection candidates | 4,768 |
| One detection candidate | 3,403 |
| Zero detection candidates | 61 |
| Replayed frames | **8,232** |
| Tracker clear on real >0.2s gap | **1** |

These are **experimental processor outputs**, not Windows-contact
matching scores. The first 30 input frames may already contain a
finger, limiting calibration fidelity. The prototype still applies
provisional Linux-only detection/birth policies.

## Raw connected components and peak-aware counterexample

A separate, baseline-independent detector counts 8-neighbor regions
with sensor byte below **150** and at least three cells.
On **all 8,232 frames**, that simple raw-region count was:

| Raw regions | Frames |
| ---: | ---: |
| 0 | 43 |
| 1 | 3,607 |
| 2 | 4,582 |

For each selected reference, we inspected **50 raw frames within ~0.25s**
of the provisional relative-time center. A 3x3 inverse-signal smoother
with local-peak nonmaximum suppression (minimum spacing 4 grid cells)
also provides a **second, explicitly experimental** candidate count.

| Reference window | 8-neighbor regions at byte<150 | Peak-aware candidates, smoothed-depth >=10 |
| --- | ---: | ---: |
| Far-separated fingers (~25s) | 50/50 frames show **two** | 50/50 **two** |
| M1 (~58.15s) | 50/50 frames show **one** | 50/50 **one** |
| M2 (~65.06s) | 50/50 frames show **one** | 50/50 **one** |
| M3 (~75.95s) | 50/50 frames show **one** | 50/50 **one** |
| Re-separated (~83s) | 50/50 **two** | 50/50 **two** |

Peak smoothing cutoff sensitivity (minimum inverse intensity **5,
8, 10, 12, 15, 20**) was separately swept on the same 250
reference-window frames: **every** threshold returned two peaks in
all far-apart/re-separated frames and **one** peak at every M window
frame. Other filtering parameters and time alignment remain
untested; do not conclude an unobservable physical finger from
this negative peak result alone.

Positive synthetic regression: two Gaussian lobes with **one
threshold-connected blob** are resolved by the peak-aware detector
as two distinct maxima (where components count one). Negative synthetic
regression: a genuine single Gaussian lobe remains exactly one.
This demonstrates the **capability** of peak-based splitting, but
our current **real** M windows do not provide evidence of two
separable strong peaks.

## Engineering decision

**Do not patch the kernel or raise the contact hold timer now.**
The first real failure slices do not support the hypothesis
that a trivial connected-component splitter would recover a
second strong measured peak. Candidates to investigate next:

1. Formal ETL/WPR-QPC-to-pointer-UTC time calibration before assigning
   sensor frames to precise OS UP/marker instants.
2. Weaker/subthreshold signal and two-contact temporal continuity in
   the entire **1–2 seconds before and after actual UPs**, not only
   the marked frames. Characterize when both peaks first converge
   and how long one peak remains absent.
3. Compare the **recovered** TouchPenProcessor classifier and quality
   hold/lift decisions where source semantics are actually known;
   current prototype coalescing/association constants are not
   proof of Windows emission logic.
4. Add **an explicit physical lift negative control** and independent
   release test before any history-based occlusion retention is
   considered safe; otherwise a persistent track becomes a ghost.
5. Keep this draft offline branch isolated from working Gate5,
   experimental in-tree kernel branch and upstream Syax PRs.

### Source files

- [`pinch_dataset.py`](pinch_dataset.py): strict public ZIP validation,
  sensor-gap awareness, full existing processor replay, independent
  8-connected regions and peak-aware lobe detector with limited
  time-neighborhood summaries; **no user hardware access**.
- [`test_pinch_dataset.py`](test_pinch_dataset.py):
  synthetic two-lobe splitter test, single-lobe control, archive hash,
  clock-order validation, all-zero replay contract.
- [workflow](../../.github/workflows/surface-processor.yml):
  public corpus SHA pin, quantitative expectations, JSON artifact.

Only aggregate statistics from the public dataset appear in this
report. The original private ETL/CSV and vendor payloads remain private.
