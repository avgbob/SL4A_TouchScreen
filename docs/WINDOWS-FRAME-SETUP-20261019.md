# Windows frame setup and threshold schedule — 2026-10-19

This note closes the static-analysis gap between CapImg section staging and
the initial Windows connected-component pass for the pinned
`TouchPenProcessor0C19.dll`:

- SHA-256:
  `f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`;
- frame setup: `FUN_1806003b0` and `FUN_180600820`;
- initial scan: `FUN_180604ab0`;
- selected PSDB record: `DAT_1808e0460`.

The DLL remains historical/private evidence. The public implementation keeps
only derived control flow, typed fields, constants, tests and hashes.

## Corrected data path

`FUN_18068bfc0` selects the `0x0c19` PSDB record, then calls the omitted
initializer at `0x1805ff7e0`. Its call site passes selected-record `+0xecc` as
the fifth argument; the initializer stores that pointer at processor context
`+0x16480`. `FUN_180600820` reads the same pointer.

The key correction is that `FUN_180600820` performs **threshold selection**,
not per-pixel baseline subtraction or signal-gain conversion:

1. `FUN_1806003b0` takes the maximum u16 from a frame metadata array whose
   count is at frame `+0xb6c1` and values begin at `+0xb6c2`.
2. `FUN_180600820` selects one configured signal threshold using that maximum,
   clamps it to the configured lower/upper bounds, and clears label/candidate
   workspaces.
3. It passes the original staged grid pointer to `FUN_180604ab0`.
4. `FUN_180604ab0` reads each pixel directly as
   `grid[y * 0x120 + x]`, converts the selected signal threshold to a raw-byte
   gate, and labels eligible cells.
5. The c590 LUT converts raw bytes to signal values while accumulating a
   candidate; it is not a prior raster conversion stage.

For a full 0C19 stream-0 frame, the preceding section fast path is a packed
72×48 direct view. For copied partial/multi-run 8-bit input, section staging
places rows at stride `0x120`; `packed_active_grid()` is a representation
adapter for the Python CCL, not a Windows signal transform.

## Selected 0C19 schedule

Selected record `+0xecc` is virtual address `0x1808e132c` and file offset
`0x8dff2c` in the hash-pinned DLL. Its header is:

| Relative field | Value | Recovered use |
| --- | ---: | --- |
| `+0x00` | 0.04f | lower clamp |
| `+0x04` | 0.12f | upper clamp |
| `+0x08` | 0.06f | used later; not assigned here |
| `+0x0c` | 0.055f | small-component minimum peak signal |
| `+0x10` | 20 | schedule entry count |

Each entry is `f32 selected_threshold, u32 cutoff`:

| Index | Threshold | Cutoff | Effective threshold after clamp |
| ---: | ---: | ---: | ---: |
| 0 | 0.025 | 41 | 0.040 |
| 1 | 0.030 | 59 | 0.040 |
| 2 | 0.035 | 80 | 0.040 |
| 3 | 0.040 | 105 | 0.040 |
| 4 | 0.045 | 133 | 0.045 |
| 5 | 0.050 | 164 | 0.050 |
| 6 | 0.055 | 198 | 0.055 |
| 7 | 0.060 | 236 | 0.060 |
| 8 | 0.065 | 277 | 0.065 |
| 9 | 0.070 | 321 | 0.070 |
| 10 | 0.075 | 369 | 0.075 |
| 11 | 0.080 | 419 | 0.080 |
| 12 | 0.085 | 473 | 0.085 |
| 13 | 0.090 | 531 | 0.090 |
| 14 | 0.095 | 591 | 0.095 |
| 15 | 0.100 | 655 | 0.100 |
| 16 | 0.105 | 722 | 0.105 |
| 17 | 0.110 | 793 | 0.110 |
| 18 | 0.115 | 867 | 0.115 |
| 19 | 0.120 | 944 | 0.120 |

The loop compares cutoffs for entries 0 through 18. Once the metric reaches
867 it selects entry 19; the final stored cutoff 944 is not tested by this
loop. This detail is preserved rather than simplified into a generic lookup.

## Verification and remaining boundary

`windows_frame_setup.py` parses the configuration layout, reproduces the u8
index loop and clamps, and exposes the exact float32 0C19 schedule. An
independently compiled C11 function agrees for all 65,536 possible u16 maximum
metrics. An integration test sends a complete staged 72×48 section through
the selected threshold and initial CCL.

This closes the supposed raw-to-"converted grid" stage: Windows directly scans
the staged byte values. It does **not** identify the physical meaning or
producer of frame `+0xb6c1/+0xb6c2`. Raster-only sanitized captures omit that
metadata, so they cannot reconstruct the exact per-frame threshold without an
external metric. Windows internal candidate/label output is also still needed
for a runtime golden comparison.
