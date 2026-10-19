# DLL Config Table Reference

> **2026-10-17 correction:** The DLL constants are recovered static values. The `Linux Equivalent` column and any finger-count multiplier interpretation below are **Linux approximations, NOT verified Windows radius policy**; consult the specific `FUN_180607a20` branches in [decomp/SURFACE_TRACKER_DECOMP.md](decomp/SURFACE_TRACKER_DECOMP.md) and [RESEARCH-CONTRADICTIONS.md](RESEARCH-CONTRADICTIONS.md) D16 before using them.\n\nComplete configuration table extracted from `TouchPenProcessor0C19.dll`
data segment at virtual address `0x1808E0460` (file offset `0x8DF060`,
section `.data`, product ID 0x0C19).

## Association Radii (offset +0x8DC to +0x8EC)

Maximum distance a tracked contact can move between frames, scaled by
the number of currently tracked fingers. Used in the Hungarian cost
matrix: `effective_radius = blob_max_distance × multiplier[n_fingers]`.

| Offset | DLL Value | Usage | Linux Equivalent |
|--------|-----------|-------|-----------------|
| +0x8DC | 0.545009 | Normal radius (2 fingers) | `blob_max_distance=3` |
| +0x8E0 | 1.218098 | Single-track continuity | 3 × 2.2 = 6.6 cells (ratio 1.218/0.545 ≈ 2.23; `ASSOC_RADIUS_1_FINGER=22`) |
| +0x8E4 | 1.549246 | 3-finger radius | 3 × 2.8 = 8.4 cells (ratio 2.84; `ASSOC_RADIUS_3_FINGERS=28`) |
| +0x8E8 | 1.845492 | 4-finger radius | 3 × 3.4 = 10.2 cells (ratio 3.39; `ASSOC_RADIUS_4_FINGERS=34`) |
| +0x8EC | 2.161228 | 5+ finger radius | 3 × 4.0 = 12.0 cells (ratio 3.97; `ASSOC_RADIUS_5_FINGERS=40`) |

The multiplier is the **ratio** to the +0x8DC normal radius, rounded to the
driver's per-mille constants — not the raw DLL value applied directly
(`driver/mshw0231-raw.c:874-889`).

## Edge Contact Weights (offset +0x8D0, +0x8D4)

Blob signal weight compensation at panel edges, where partial contact
with fewer TX/RX lines reduces measured capacitance.

| Offset | DLL Value | Applied To |
|--------|-----------|------------|
| +0x8D0 | 0.966512 | Top, left, right edges |
| +0x8D4 | 0.228140 | Bottom edge |

Applied to individual cell weights during CCL flood-fill. The bottom
edge has a much stronger penalty because the bottom bezel blocks
most of the electric field.

## Coalescing / Ghost Rejection (offset +0xC98)

| Offset | DLL Value | Description | Linux Equivalent |
|--------|-----------|-------------|-----------------|
| +0xC98 | 36.0 | Distance² threshold used by close-contact coalescing policy | `ghost_dist=6` (√36), applied after Hungarian association |

Linux previously used `ghost_dist` as a destructive pre-association
blob merge. The merged tracker fix no longer does that: Hungarian sees the
complete candidate set first, then the six-cell threshold is applied by the
post-association close-contact policy so two distinct established tracks can
survive a pinch.

## Pre-Association Filter (offset +0x8C0, +0x8C4)

Rejects blob candidates whose signal weight is below a fraction of
the strongest candidate's weight.

| Offset | DLL Value | Description |
|--------|-----------|-------------|
| +0x8C0 | 0.611209 | Primary pre-assoc ratio threshold |
| +0x8C4 | **0.7553579807** | Secondary ratio threshold |

Disabled in Linux (`pre_assoc_ratio=0`). Without verified Windows candidate
classification and frame-threshold metadata handling, this filter is
potentially too aggressive for multi-finger scenarios.

## Initial CCL threshold schedule (offset +0xECC)

| Offset | DLL Value | Description | Linux Equivalent |
|--------|-----------|-------------|-----------------|
| +0xECC | 0.04 | Lower clamp for the per-frame signal threshold | No direct equivalent |

`FUN_180600820` selects a signal threshold from the 20-entry schedule beginning
at `+0xee0`, using the maximum u16 value from frame metadata
`+0xb6c1/+0xb6c2`, then clamps the selection to `+0xecc` (0.04) through
`+0xed0` (0.12). `FUN_180604ab0` converts that signal threshold to a raw-byte
gate and scans the staged grid directly. This is not a per-pixel baseline
subtraction. See [WINDOWS-FRAME-SETUP-20261019.md](WINDOWS-FRAME-SETUP-20261019.md).

## Hold Policy (offset +0x8D8)

| Offset | DLL Value | Description |
|--------|-----------|-------------|
| +0x8D8 | 0xB3 (enabled) | Enable hold state for brief contact loss |

Disabled in Linux (`hold_frames=0`). Windows hold (FUN_180606370) is
a complex quality-gated policy: it only applies to tracks with
duration ≤ 2 frames, pixel count in bounds, eigenratio < 4.0, and
signal > 0.095. Our simplified implementation caused scrolling to
"brake" on finger lift.

## Touch Detection Threshold (offset +0x958)

| Offset | DLL Value | Description |
|--------|-----------|-------------|
| +0x958 | 0.17 | Touch detection as fraction of peak signal |

Not directly used in Linux. It belongs to a later detector path and must not be
substituted for the initial CCL threshold selected by `FUN_180600820`.

## Static versus runtime data: corrected by August MSI audit

The August 2026 Microsoft MSI mining report (docs/SL4_MSI_Mining_Report.md)
re-checked the actual 0x0C19 static image. **Not all of these ranges are
zero-filled runtime calibration data.** Avoid using guessed matrix types or
assuming SurfaceSystemTelemetryDriver is their producer.

| Offset range | Static image observation | What is still unknown |
|---|---|---|
| +0xD40 .. +0xD78 | Structured **nonzero byte/index** data with 0xFF sentinels; **not** a 10×11 floating-point Mahalanobis matrix | Meaning and consuming xrefs |
| +0xE20 .. +0xE48 | Statically zero | Runtime producer and exact purpose |
| +0xE60 .. +0xE98 | Statically zero | Runtime producer and exact purpose |
| +0xEA0 .. +0xEC0 | Statically zero | Noise/adaptation fields and producer |
| +0xECC .. +0xF80 | Structured **static** frame/initial-CCL configuration | Meanings outside the now-recovered threshold schedule |

At +0xECC: lower/upper clamps 0.04/0.12, another 0.06 field, the
small-component peak gate 0.055, integer count 20, then pairs of thresholds
0.025..0.120 and cutoffs 41..944. `FUN_180600820` consumes this schedule; its
loop uses cutoffs through 867 and selects the final 0.120 entry thereafter.
The 15-inch 0x0C18 table differs and is not covered by the 0C19 result.

The old description of +0xD40 as an all-zero runtime Mahalanobis
float matrix and +0xED0 as runtime-only regional sensitivity are
**retracted**. The classifier function FUN_180601690 still requires
decompilation and empirical Windows comparison.

+0x8C4 is verified **0.7553579807**; an earlier documented value
0.754732 was a transcription error. See the exact DLL hash and
cross-product comparison in docs/SL4_MSI_Mining_Report.md.

## Data Type Notes

The individually identified values in these ranges are IEEE 754
single-precision floats; the `+0xedc` count and threshold cutoffs are u32. Do
not blanket-type every intervening byte as float. The hold flag at +0x8D8 is a
byte interpreted as boolean
(0xB3 is a non-zero "enabled" value, though the exact interpretation may
depend on the pipeline logic at FUN_180606370).

The base address `0x1808E0460` was identified via Ghidra cross-reference
analysis of FUN_180600c40 (CCL initialize), which references this table
for per-cycle configuration.
