# Windows contact-processor evidence manifest — 2026-10-18

This is the scope ledger for the `research/windows-contact-processor-v2`
rebuild. It records which observations may be used as regression truth and
which material is historical, superseded, private, or diagnostic-only.

The reference processor is not a Linux input driver and is not yet a complete
Windows reconstruction. Numeric Windows classes remain unnamed.

## Preserved source checkpoints

| Purpose | Commit | Preserved tag | Status |
| --- | --- | --- | --- |
| Offline processor/oracle v1 | `3d8d3dafa0b65df8f4ca17890b8e616d321d1e40` | `research/windows-contact-processor-v1-checkpoint-20261018` | Frozen research source; do not merge wholesale |
| In-tree kernel experiment | `54ab82b4d1e75b5100d0311716aac3cf2be5c1d2` | `experiment/in-tree-kernel-checkpoint-20261018` | Frozen build/package laboratory; not processor fidelity evidence |
| v2 base | `27ff57f561ca49fc1273404780a82f8c1648057d` | current `main` at rebuild start | Canonical base for curated migration |

## Capture and oracle authority

| Evidence | Identity | Authority in v2 | Limits |
| --- | --- | --- | --- |
| Historical Windows raw corpus | 638 boot + 247 init + 537 touch = 1,422 strict `0x0c` frames; stream hashes remain in `RESEARCH-SOURCE-MANIFEST.md` | Decoder and raw-replay regression | No synchronized processed contact IDs |
| Correlated V2 pinch | ETL SHA-256 `23ee9ad0df5703458a15bd4741acdb910041f84edeef908cce73f0775c7acb30`; tracerpt CSV SHA-256 `56c9f4b3b9ee7fe526667de208dce59f8a150f7372448a218783e11075502131`; 8,232 strict frames | Sensor/annotation research | Earlier M annotations require the tracked accidental-key correction; not the final frame-aligned oracle |
| V3 physical-truth session `SL4A-PhysicalTruth-20261017-210517` | Operator reported one accidental `N` key press | **Superseded; never canonical regression truth** | Error-prone multi-key protocol can leave stale or incorrect labels |
| Guided V4 session `SL4A-PhysicalTruth-20261017-214307` | Private evidence-bundle SHA-256 `e490793616d6668419887ae609289b4bc348a2adddd6a38b3c6d415e7ee21ab7`; 17,018 frames; 19 holds; 14 DOWN / 14 UP | **Canonical OS-visible physical-truth oracle for this machine/run** | Human confirmations, one machine, OS-visible pointers rather than internal HeatCore state |

V4 replaces V3 because it accepts only SPACE, bounds every confirmed state with
an automatic two-second hold, and explicitly returns to unknown between holds.
No V3 morphology or hold rule may be promoted into output policy.

## Binary and decompilation identities

| Artifact | SHA-256 / source | Permitted claim |
| --- | --- | --- |
| `TouchPenProcessor0C19.dll` | `f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`; preserved in historical Git commit `c94c399` | Exact source for the pinned 0C19 static/decompiled implementation |
| `HeatCore.dll` 10.0.26100.9278 | `b295b095acf574007b894f841ef083e8cb06a72a256ee0bb75b4be80f2fcd5df`; 401,408 bytes | Matching-build static ABI evidence; not proof of runtime call targets or semantics |

Microsoft binary bytes and private coordinate-bearing captures are not added to
this public branch. Parsers accept caller-supplied bytes and may publish only
derived layout checks, digests, and privacy-safe aggregates.

## Evidence-state vocabulary

- **FOUND:** identity and location recorded.
- **READ:** relevant bytes, records, or source inspected.
- **STRUCTURALLY REPRODUCED:** layouts and control flow implemented.
- **NUMERICALLY REPRODUCED:** operation order and float width cross-checked.
- **WINDOWS-OUTPUT COMPARED:** output measured against a frame-aligned oracle.
- **RELEASE QUALIFIED:** physical hardware matrix, reset/resume, and safety gates
  passed on the exact source being released.

Passing an earlier state never implies a later one.

## Current v2 gates

1. Strict V0 decoding: port and lock against tracked fixtures/corpora.
2. V4 oracle: reconstruct only from a hash-verified private run and lock its
   sanitized 17,018-frame behavioral contract.
3. Candidate score kernel: use 32-bit float operations in recovered order and
   cross-check against a compiled C oracle.
4. Initial converted-grid CCL: reproduce the 255 initialized LUT entries,
   raw threshold gate, eight-connected provisional scan, equivalence merging,
   accumulator records and initial component acceptance. The V0-to-converted
   grid transformation remains open, so raw captures are not fed into this
   stage as if they were Windows runtime buffers.
5. Labelled-component feature kernels: reproduce the exact no-resegmentation
   split-byte fallback, covariance-derived `0x8c`/`0x90` fields, and final
   `0x94` normalization/oversize branches. This is not raw-frame candidate
   production. The overlapping `_DAT_180765c20` double is pinned from the
   hash-identified DLL bytes rather than guessed.
6. V0 `0x0100` section parsing/staging is structurally reproduced from
   `FUN_18068e990`, including its full-run direct view, 288-byte multi-run
   placement, and calibrated 16-bit conversion. The section does not encode
   geometry, but the recovered `0x0c19` selector maps to static record
   `DAT_1808e0460`, whose stream-0 configuration `+0x3c/+0x3e` is height 48,
   width 72; stream 1 is unconfigured. Full 8-bit runs and converted 16-bit
   runs are packed; only copied partial/multi-run 8-bit data uses stride 288.
7. Conditional split CCL, surrounding walks, outer class policy, association,
   hold/lift and final emission remain open until separately implemented and
   tested.
8. No uinput or kernel output is authorized by these offline gates.

## Maintenance rule

Any new behavioral claim must identify its capture or binary, hash, source
function/offset where applicable, evidence-state vocabulary above, privacy
status, and known uncertainty. Contradictions are resolved by supersession,
not by deleting the prior record.
