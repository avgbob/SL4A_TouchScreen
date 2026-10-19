# Windows candidate-feature producer boundary — 2026-10-19

This note records the first source-grounded portion of the pipeline upstream of
the recovered `FUN_180601690` four-score classifier. It is not a complete
raw-heatmap candidate detector.

## Implemented boundary

`userspace/surface-processor/windows_candidate_features.py` accepts typed
statistics for an **already selected and labelled component** and produces the
ten fields consumed by the common classifier path:

| Classifier order | Candidate offset | Producer evidence | v2 status |
| ---: | ---: | --- | --- |
| 0 | `0x9e:u16` | copy of `0x38` in `FUN_180600c40` | structurally reproduced |
| 1, 4 | `0x99:u8`, `0x98:u8` | split pass 0 in `FUN_1806042f0` | fallback exact; thresholded CCL open |
| 2, 5 | `0x9b:u8`, `0x9a:u8` | split pass 1 in `FUN_1806042f0` | fallback exact; thresholded CCL open |
| 3, 6 | `0x9d:u8`, `0x9c:u8` | split pass 2 in `FUN_1806042f0` | fallback exact; thresholded CCL open |
| 7 | `0x8c:f32` | covariance eigen-axis ratio in `FUN_180600c40` | arithmetic and pinned axis-scale double reproduced |
| 8 | `0x90:f32` | trace × `2π` / (`cells-1`) in `FUN_180600c40` | structurally reproduced |
| 9 | `0x94:f32` | neighbourhood accumulator normalization in `FUN_180605960` | final normalization and oversize fallback reproduced; walks open |

The byte-pair names `component_count` and `max_component_cells` follow the
scratch CCL outputs copied from context offsets `0x19471` and `0x1946c`. They
do not assert semantic Windows touch classes.

## Anchors

All source links below refer to the pinned historical binary extraction commit
`c94c399618b23588c95711ab4449d9400036ffd0`:

- `FUN_180600c40`: candidate post-processing, covariance and classifier-field
  writes.
- `FUN_1806042f0`: three split thresholds, fallback byte pairs, and scratch CCL
  results.
- `FUN_180605960` and `FUN_180605680`: 16×16 surrounding-neighbourhood mask,
  accumulation, normalization, and 100.0 fallback.
- `static_data_references.tsv`: `DAT_180765c18 = 4.0`,
  `DAT_1806c6458 = 0.5`, `DAT_180716340 = 1.0`,
  `DAT_180765c38 = 2π`, and `DAT_180719140 = 1.15`.

The static-data export records `_DAT_180765c20` as an overlapping double without
printing its value. The pinned DLL (SHA-256
`f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`) remains
available in a pre-removal Git object. PE VA `0x180765c20` maps to file offset
`0x764c20`, whose bytes `36 cd 93 40 e4 cb 96 40` decode to the exact double
`0x1.6cbe44093cd36p+10` (`1458.9729025930405`). The implementation pins those
bytes' value; it does not accept a guessed runtime default. A separate C11
`float` oracle checks the Python operation order over randomized positive
semidefinite moment inputs.

## Explicitly open gates

The module refuses to imply an end-to-end producer. These remain open:

1. provenance and meaning of the per-frame metadata used by
   `FUN_180600820`'s recovered threshold schedule;
2. candidate selection, peak suppression and record lifecycle;
3. three thresholded split CCL passes when `FUN_1806042f0`'s condition is true;
4. the two neighbourhood walks that create the small-box `0x94` accumulator;
5. comparison of produced candidate records against instrumented Windows
   runtime records.

The selected 0C19 stream-0 geometry and the initial eight-connected CCL are
now structurally recovered in the adjacent staging and initial-CCL modules.
Frame setup is also recovered: it sends staged bytes directly into the main
CCL after selecting a threshold, rather than performing the previously assumed
baseline/grid conversion. That closes the former conversion gate, but not the
metadata-provenance or Windows-runtime output-comparison gates above.

Until those gates close, callers must supply labelled-component statistics and
must label their provenance. This code can feed the recovered classifier for
unit and differential work, but cannot turn a raw 72×48 frame into Windows
contacts.
