# CapImg Multitouch Pipeline

The in-kernel CapImg multitouch tracker converts the device's capacitive sensor
grid into Linux multitouch contacts. The same tracker is used by the production
MSHW0231 Gate5 standard-transport path (`raw_mode=0`) and by the legacy
diagnostic raw transport (`raw_mode=1`). Its implementation remains in the
legacy-named `driver/mshw0231-raw.c`, with constants in
`driver/mshw0231-raw-constants.h`.

The input is a **CapImg frame** — 3456 cells (72×48) on SL4 `MSHW0231`,
4056 cells (78×52) on SL3 `MSHW0162`; the grid is selected by ACPI ID at
probe (see [Architecture](Architecture)). The raster is one byte per cell,
row-major, **row stride = grid width** (no padding); the resting level is
`0xB4` (180) and a touch *lowers* the byte.

## Reference chain: the Windows detector

The reference stack splits the work differently from the Linux pipeline below: a
per-frame **detector** selects one peak, and a separate **tracker** turns the
sequence of peaks into contacts. The detector's stages:

```
frame (raster + per-frame lists)
  │
  ├─ a. Candidates — from the frame's blob list, each blob contributes
  │      itself plus its four distance-1 neighbours, deduped, in one flat
  │      list (capacity 25)
  ├─ b. Isolation gate — reject when any of the four cells at ±5 cells
  │      (cardinal axes) reads below 135; out-of-raster samples pass
  ├─ c. Score — 11×11 kernel (Σ = 1.5513) × c590 over the window
  └─ d. Publish — the highest-scoring survivor, if it reaches 0.05
         (0.04 in the alternate state); one peak per frame
```

Notes that matter when comparing with the Linux chain:

- the image the detector reads is a 288-byte-row plane where only the first
  72 bytes of each row carry the SL4 image; the raster layout of the frame
  itself is the 72-byte stride documented above;
- the frame is filled by the transport side, and the reference publishes its
  result back into the same object (peak position, flags) — the tracker reads
  it from there;
- one peak per frame means multi-contact output comes from the tracker
  (see [Multi-touch (Beta)](Multi-touch-Experimental)), never from
  the detector.

| Windows stage | Linux equivalent |
|---|---|
| a. candidates from the frame's lists | 4. peak detection, 5. CCL |
| b. ±5 isolation gate | (no direct equivalent — see below) |
| c. 11×11 kernel score | 3. signal rise + noise floor |
| d. one peak per frame | 11. MT emission (driver publishes all blobs) |

The ±5 gate has no counterpart in the Linux chain: the driver keeps a blob
when its rise passes the touch threshold and its weight passes
`blob_min_weight`, while the reference implementation additionally requires
the deflection to have decayed at five cells in all four cardinal directions.

## Processing chain

```
CapImg frame (0x0C)
  │
  ├─ 1. c590 LUT — raw byte → fixed-point signal
  ├─ 2. Baseline — per-cell ambient model (asymmetric EMA)
  ├─ 3. Signal rise + noise floor
  ├─ 4. Peak detection — local maxima
  ├─ 5. CCL flood-fill — connected components → blobs
  ├─ 6. Blob filtering/splitting + centroid/eigenvalues
  ├─ 7. Hungarian assignment — full candidate set ↔ tracked slots
  ├─ 8. Post-association duplicate/coalescing policy
  ├─ 9. Slot state machine + position EMA/deadband/stationary lock
  └─10. MT emission (input_mt, 47 slots)
```

## 1. c590 lookup table

Each raw byte is mapped to a fixed-point signal via a precomputed LUT:

```
c590[i] = max(0, 10000 − ( (i·22204 + 500) / 1000 + 6000 ))
```

(`C590_BASE=10000`, `C590_STEP_NUM=22204` ≈ 0.00222035428 per step,
`C590_STEP_DEN=1000`, `C590_OFFSET=6000`.) The table is
built once at `mshw0231_raw_init()`.

## 2. Baseline (asymmetric per-cell EMA)

Each cell tracks a resting baseline. Building it takes **30 frames on SL4 /
33 frames on SL3** (per-device `heatmap_baseline_needed`); during this window
the baseline is the per-cell **maximum** observed raw value (a touch only
lowers the raw byte).

After stabilization, tracking is asymmetric:

| Condition | Rule |
|---|---|
| `raw ≥ baseline` (finger lifted / resting) | Recover toward raw: `new = (7·base + raw)/8` — the **12.5% recovery rate** (EMA alpha 7) |
| `raw < baseline` (touch) | Do **not** chase the touch down; only a very slow decay tracks downward thermal drift, so a held finger never fades into the baseline |

## 3. Signal rise and noise floor

- `rise = c590[baseline] − c590[raw]` (touch lowers raw, so rise is positive)
- Cells with absolute c590 < **400** are suppressed (noise floor, 0.04 in the
  reference's fixed-point units)
- A cell is touched when `rise ≥ 200` (`HEATMAP_TOUCH_MIN_RISE`)

## 4. Peak detection

A true **local-maximum scan** over the full neighborhood
(`HEATMAP_PEAK_RADIUS = 2`): a cell is a peak when no neighbor within radius 2
is strictly higher; equal signals (flat-topped plateaus) settle by raster
order and contribute exactly **one** peak per equal-signal region, anchored
to the cell nearest the region's centre — the peak has to stay near the blob
centroid, or a wide saturated plateau's only peak falls outside the
velocity-rejection radius and the whole contact is silently dropped. In a
tapered blob only the true center qualifies. One peak per equal-signal region
keeps a single blob from exhausting the shared **peak budget**
(`HEATMAP_MAX_PEAKS`, 20), which is kept ≥ `HEATMAP_MAX_BLOBS` so the budget
can never starve a committable blob.

## 5. CCL flood-fill

4-connected BFS over touched cells (`raw_ccl_flood_fill()`, queue `HEATMAP_MAX_CELLS` = 4300).
Each connected component becomes a blob candidate, gated by:

| Filter | Threshold |
|---|---|
| Pixel count | ≥ 2 (`HEATMAP_MIN_BLOB_PIXELS`) |
| Max rise | ≥ 200 |
| Signal weight | ≥ 1000 (`blob_min_weight`, module param) |
| Velocity rejection | centroid within **6 cells** of a detected peak (`HEATMAP_VELOCITY_REJECT_RADIUS`; a 6-cell radius corresponds to the reference's **36.0 = 6²** squared-distance constant in its association/coalescing layers) |

## 6. Blob filtering, splitting, centroid and weight

Overlapping components (for example two close fingers) are split when they
contain ≥ 2 peaks (`HEATMAP_SPLIT_MIN_PEAKS`) separated by ≥ 4 cells
(`HEATMAP_SPLIT_MIN_DIST`), with splitting radius 2.

Before assignment, each surviving blob carries its grid centroid, weighted
signal, raw pre-penalty weight, and shape/eigenvalue data. Weight EMA is fixed
at the reference value:

```text
weight = (old·7 + new)/8
```

(`HEATMAP_WEIGHT_EMA_ALPHA = 7`, independent of `ema_alpha`.)

## 7. Hungarian assignment

The complete candidate set is matched to tracked slots with a Kuhn–Munkres
augmenting-path solver (`raw_hungarian_match()`). This ordering is important:
close candidates are **not destructively merged before assignment**.

Cost model (×`HUNGARIAN_COST_SCALE` = 100):

| Cost | Value | Meaning |
|---|---:|---|
| In-range | 10 | Preferred valid assignment |
| Empty slot | 1000 | Leaving a slot empty |
| Out-of-range | 1500 | Forcing a doomed match (must stay > EMPTY) |
| Continuity bonus | 5 | Keep two actively-tracked fingers from swapping mid-gesture |
| Jump-reject margin | 200 | Reject implausible jumps |

Association radius multipliers (×`blob_max_distance`, stored ×10 as
`ASSOC_RADIUS_*`): 1×2.2, 2×1.0, 3×2.8, 4×3.4, 5+×4.0.

## 8. Post-association duplicate/coalescing

`raw_post_assoc_coalesce()` applies the `ghost_dist` radius **after**
Hungarian assignment. This replaced the older pre-association merge ordering
that collapsed legitimate close two-finger frames on the tested MSHW0231.

Current policy:

- two candidates assigned to two different established tracks are both kept,
  even when they are inside `ghost_dist`;
- an established track normally wins over a nearby candidate assigned to a
  non-established slot;
- a tightly bounded sequential close-birth grace can preserve the second
  contact while the first track is still very young;
- if neither candidate has established continuity, the higher pre-penalty raw
  weight is retained and the weaker ambiguous duplicate is suppressed.

Suppression clears the candidate's assignment; it does not delete the blob
record, so diagnostics retain both the pre- and post-association view.

## 9. Slot state, position smoothing, deadband and stationary lock

The slot state machine owns Linux tracking IDs and handles debounce,
lift-pending/occlusion continuity, reacquisition and final release.

- **Position EMA**: `new = (old·α + gx)/(α+1)` with α = `ema_alpha`
  module parameter (default **2**; lower = more responsive, more jitter)
- **Deadband**: `HEATMAP_DEADBAND_THRESHOLD = 20` (fixed-point units)
- **Stationary lock**: after `HEATMAP_STATIONARY_FRAMES = 2` in place, the
  contact is locked against tiny jitter
- Hold-state recovery weight: 4000 (`HEATMAP_HOLD_RECOVERY_WEIGHT`)

## 10. MT emission

Tracked slots are published through the Linux input subsystem multitouch
protocol (`input_mt_init_slots` with **47 slots**, `HEATMAP_MAX_SLOTS`),
including `TOUCH_MAJOR/MINOR/ORIENTATION` from per-blob eigenvalues. Missed
contacts are released according to the slot/lift state machine.

## Parameter mapping

| Stage | Module parameter | Default |
|---|---|---|
| Weight gate | `blob_min_weight` | 1000 |
| New-touch debounce | `blob_debounce` | 3 |
| Lift after missed frames | `blob_lift_frames` | 3 |
| Post-association duplicate/coalescing radius | `ghost_dist` | 6 |
| Association base | `blob_max_distance` | 3 |
| Pre-association filter | `pre_assoc_ratio` | 0 (disabled) |
| Position smoothing | `ema_alpha` | 2 |
| Grid geometry | `grid_cols` / `grid_rows` | per-device (72×48 / 78×52) |

Everything is host-side signal processing on raw sensor data: no firmware
calibration, no Mahalanobis classifier, no per-cycle gain adaptation (both
require device firmware access). See [Config Table](Config-Table) for the
provenance of these values.
