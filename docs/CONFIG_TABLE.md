# DLL Config Table Reference

> **2026-10-17 correction:** The DLL constants are recovered static values. The `Linux Equivalent` column and any finger-count multiplier interpretation below are **Linux approximations, NOT verified Windows radius policy**; consult the specific `FUN_180607a20` branches in [decomp/SURFACE_TRACKER_DECOMP.md](decomp/SURFACE_TRACKER_DECOMP.md) and [RESEARCH-CONTRADICTIONS.md](RESEARCH-CONTRADICTIONS.md) D16 before using them.\n\nComplete configuration table extracted from `TouchPenProcessor0C19.dll`
data segment at virtual address `0x1808E0460` (file offset `0x8DF060`,
section `.rdata`, product ID 0x0C19).

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

Disabled in Linux (`pre_assoc_ratio=0`). Without verified Windows candidate classification and gain handling, this filter is potentially too aggressive
for multi-finger scenarios.

## Noise Floor (offset +0xECC)

| Offset | DLL Value | Description | Linux Equivalent |
|--------|-----------|-------------|-----------------|
| +0xECC | 0.04 | Signal fraction below which cells are noise | c590 < 400 suppressed |

0.04 × 10000 (c590 max range) = 400. Cells with absolute c590 value
below this threshold are treated as noise in baseline subtraction.

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

Not directly used in Linux. This threshold applies after per-cycle
gain adaptation (FUN_180600820), which adjusts global signal gain
based on noise floor measurements. Without the gain pipeline, this
threshold is meaningless as a standalone value.

## Static versus runtime data: corrected by August MSI audit

The August 2026 Microsoft MSI mining report (docs/SL4_MSI_Mining_Report.md)
re-checked the actual 0x0C19 static image. **Not all of these ranges are
zero-filled runtime calibration data.** Avoid using guessed matrix types or
assuming SurfaceSystemTelemetryDriver is their producer.

| Offset range | Static image observation | What is still unknown |
|---|---|---|
| +0xD40 .. +0xD78 | Structured **nonzero byte/index** data with 0xFF sentinels; **not** a 10×11 floating-point Mahalanobis matrix | Meaning and consuming xrefs |
| +0xE20 .. +0xE48 | Statically zero | Runtime producer and exact purpose |
| +0xE60 .. +0xE98 | Statically zero | Runtime producer and per-cycle gain interpretation |
| +0xEA0 .. +0xEC0 | Statically zero | Noise/adaptation fields and producer |
| +0xED0 onward | Structured **static** floats, count and 20-entry quadratic lookup | Which detector path consumes it |

At +0xED0: floats 0.12, 0.06, 0.055, integer 20, then
pairs x (0.025..0.120 in increments of 0.005) and approximately
round(65536 * x²) (41..944). The 15-inch 0x0C18 table differs
in at least the preceding +0xED8 parameter.

The old description of +0xD40 as an all-zero runtime Mahalanobis
float matrix and +0xED0 as runtime-only regional sensitivity are
**retracted**. The classifier function FUN_180601690 still requires
decompilation and empirical Windows comparison.

+0x8C4 is verified **0.7553579807**; an earlier documented value
0.754732 was a transcription error. See the exact DLL hash and
cross-product comparison in docs/SL4_MSI_Mining_Report.md.

## Data Type Notes

All values at offsets +0x8C0 through +0xECC are IEEE 754 single-precision
floats (32-bit). The hold flag at +0x8D8 is a byte interpreted as boolean
(0xB3 is a non-zero "enabled" value, though the exact interpretation may
depend on the pipeline logic at FUN_180606370).

The base address `0x1808E0460` was identified via Ghidra cross-reference
analysis of FUN_180600c40 (CCL initialize), which references this table
for per-cycle configuration.
