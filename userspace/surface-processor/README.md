# SL4A offline Windows reference processor v2

This directory is an evidence-first, offline reconstruction workspace. It is
not a live HID driver, uinput daemon, or complete Windows contact processor.

## Current foundation

- `capimg_v0.py` strictly decodes the observed MSHW0231 V0 envelopes and
  validates the section structure before returning a 72x48 raster.
- `windows_pointer_oracle.py` aligns a private guided V4 pointer log to its raw
  frame clock after verifying the original pointer-file hash.
- `v4_oracle_contract.py` locks privacy-safe V4 counts and counterexamples
  without publishing coordinates or heatmaps.
- `windows_classifier.py` implements the common four-block
  `FUN_180601690` score path with binary32 rounding after every recovered
  arithmetic operation.
- `windows_candidate_features.py` implements the source-grounded portion from
  an already labelled component to the classifier's ten fields: exact
  no-resegmentation byte pairs, covariance features, and the final surrounding
  score branches. It does not perform raw-frame CCL or the unresolved walks.
- `windows_initial_ccl.py` reproduces the initial eight-connected Windows
  scanline CCL, provisional-label merging, 0xb0 accumulator fields, and
  small-component acceptance gate over an already converted byte grid.
- `c_oracle/windows_classifier_oracle.c` independently checks that score
  operation order with compiled C `float` arithmetic.
- `c_oracle/windows_candidate_features_oracle.c` independently checks the
  recovered covariance-feature operation order and pinned double constant.
- `c_oracle/windows_initial_ccl_oracle.c` independently checks LUT, threshold,
  and adjusted-weight float operation order.

The score model excludes the three recovered override paths, outer class
selection, later correction, full candidate detection, association, hold/lift,
grouping, and final emission. Its C agreement is numerical reproduction of the
transcribed common path, not a Windows runtime golden-vector comparison. See
[`docs/WINDOWS-CANDIDATE-FEATURES-20261019.md`](../../docs/WINDOWS-CANDIDATE-FEATURES-20261019.md)
for the precise upstream boundary.

The CCL input boundary is documented separately in
[`docs/WINDOWS-INITIAL-CCL-20261019.md`](../../docs/WINDOWS-INITIAL-CCL-20261019.md);
the captured V0 raster must not yet be treated as the converted Windows grid.

## Verification

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover \
  -s userspace/surface-processor -p 'test_*.py' -v
python3 -m compileall -q userspace/surface-processor
git diff --check
```

The C cross-check requires a C11 compiler and compiles only into a temporary
test directory. Tests and tools do not access `/dev/hidraw`, SPI, uinput, or a
running kernel module.

## Evidence boundary

See
[`docs/WINDOWS-PROCESSOR-EVIDENCE-MANIFEST-20261018.md`](../../docs/WINDOWS-PROCESSOR-EVIDENCE-MANIFEST-20261018.md).
The guided V4 run is canonical for this machine/run. The ambiguous multi-key V3
session and heuristic/shadow implementations remain historical diagnostics.
