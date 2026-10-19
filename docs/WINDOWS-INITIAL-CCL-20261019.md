# Windows initial candidate CCL boundary — 2026-10-19

This note defines the v2 reconstruction boundary for the first Windows
connected-component pass. The implementation is
`userspace/surface-processor/windows_initial_ccl.py`.

## What is reproduced

The implementation is anchored to the pinned TouchPenProcessor0C19 DLL
(SHA-256
`f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`)
and these decompiled functions preserved at historical commit
`c94c399618b23588c95711ab4449d9400036ffd0`:

| Function | Reproduced behavior |
| --- | --- |
| `FUN_1805ff7e0` | Initializes `c590[0..254]`; slot 255 is deliberately not invented |
| `FUN_180604ab0` | Converts the selected signal threshold to a raw-byte gate and scans the active rectangle row-major |
| `FUN_180604fe0` | Uses left, upper-left, up and upper-right provisional labels; creates/updates 0xb0 candidate accumulators; records equivalences |
| `FUN_180604bd0` | Resolves equivalences to the lowest label, merges accumulators in label order, and applies the small-component peak gate |

The main pass is therefore **eight-connected scanline CCL**. The older
repository description of Windows as a four-connected BFS was drift from the
decompilation and is not used by v2.

Recovered limits and constants are preserved:

- at most `0x30` provisional labels;
- fixed equivalence buffer behavior with capacity `0x2d0`;
- LUT constants `1.0f`, `0.600000024f`, and `0.00222035428f`;
- threshold-relative weight floor approximately `0.0001f`;
- components with more than two cells pass the initial acceptance gate;
- one- and two-cell components require peak LUT signal strictly greater than
  configuration float `+0x0c`.

The result keeps both the provisional label raster and canonical-label table.
This matters because Windows does not rewrite the whole raster after merging;
later stages resolve provisional labels through the table.
Each canonical result can also serialize the initial fields of its 0xb0 Windows
candidate record; offsets owned by later stages remain zero.

## Hard boundary: staged grid geometry, not assumed 72×48 coordinates

The section parser and staging routine are now structurally reproduced from
`FUN_18068e990`; see
[`WINDOWS-SECTION-STAGING-20261019.md`](WINDOWS-SECTION-STAGING-20261019.md).
It confirms a 288-byte physical row stride for staged 8-bit runs and a direct
view when the first run's sample count equals configured `width * height`.

It does **not** establish that Windows configures the detector as 72×48. The
section carries no width or height. Windows loads those from selected runtime
configuration fields `+0x3e` and `+0x3c`. The captured section has 3,456 bytes,
which can be viewed as 72×48 for capture analysis, but that factorization is
not yet a Windows detector-coordinate claim.

The CCL Python API still uses a packed representation of the **already staged
active rectangle** and takes explicit width and height. Callers must first
provide the recovered runtime geometry and use `packed_active_grid()`; passing
`decode_frame()` output directly remains an unproved proxy.

## Verification state

- Scalar LUT, threshold and adjusted-weight arithmetic is compared bit-for-bit
  with an independent compiled C11 `float` oracle over randomized inputs.
- Topology tests lock diagonal connectivity, provisional-label bridging,
  canonical merging, capacity failures, accumulator fields, and the strict
  one/two-cell peak gate.
- No Windows-runtime candidate record has yet been captured, so this stage is
  **structurally and numerically reproduced from the binary**, not
  **Windows-output compared**.

## Next evidence gates

1. Recover the selected 0C19 runtime configuration and its `+0x3c/+0x3e`
   height/width values on this machine.
2. Obtain Windows internal candidate/label records for golden comparison.
3. Reproduce the conditional three-threshold split CCL, whose neighbor mode is
   not identical to the initial pass.
4. Reproduce the two surrounding-neighborhood walks feeding candidate `0x94`.
5. Join accepted records to centroid/covariance post-processing and the
   recovered classifier without bypassing record-status gates.
