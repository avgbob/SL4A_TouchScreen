# Independent audit of research PR #12 (2026-10-17)

This audit evaluates **offline experiment correctness**, not Windows touch-driver
fidelity. It did not modify the upstream Syax repository, fork `main`, Gate5,
HID transport, or machine input devices.

## Confirmed defects corrected

| Issue | Evidence / fix |
|---|---|
| Fabricated Windows class and group | Generated contacts previously defaulted to `status=1` and `group=local_track_id`. This invented class assignment caused arbitrary close pairs to be labeled class 7. Now both fields are `None` until actual classifier/group input is available. The recovered coalescer algorithm can still be exercised on explicitly classified reference records. |
| Frame coverage misleading | Comparator previously ignored missing reference frames while reporting zero misses. It now rejects unequal frame sets unless `--allow-partial` is explicitly specified. Partial reports disclose incomplete coverage. |
| Exhausted slots discard all new births | In a 48-track displacement case, all 48 new candidates were silently dropped. Now existing matches are updated, expired tracks reclaimed, then births allocated. |
| Invalid frame sequence mutates baseline | Repeated frame numbers passed during calibration; post-baseline duplicates mutated the signal before rejection. Monotonicity is checked before decoding and baseline updates. |
| Zero mass division | Setting `minimum_rise=minimum_weight=0` crashed `Detector.detect()` on a zero map. Zero-mass candidates are now discarded. |
| Nonfinite association configuration | NaN/Inf passed validation; association scale is now finite and bounded. |
| Invalid reference coordinates | NaN/Inf, repeated contact IDs, invalid frame types and malformed JSONL now fail validation. |
| V0 binary extension not supported | `.v0` and `.raw` captures now enter binary replay, alongside `.bin`. Errors include capture name and frame index. |

## Regression tests

Local: `python3 -m unittest -v test_processor test_compare`

Tests cover decoder V0/numbered/SPB inputs, malformed sections, known LUT values,
track matching, explicit report coalescing, real-class **unknown** annotations,
strict coalesce boundary, baseline sequencing, zero mass, saturated track replacement,
contiguous reference coverage, coordinate validation, and binary `.v0` replay.

GitHub Actions for this PR executes `python3 -m unittest discover -s userspace/surface-processor -p 'test_*.py'` and syntax compilation.

## Unresolved / not Windows-equivalent

1. Candidate detector is a **simple connected-component approximation**. Two real
   fingers can become one connected component. The common `FUN_180601690` score
   arithmetic and numeric transition gates now exist as separate tested
   modules, but the prototype has no bundled coefficient view and still lacks
   the override paths and outer score-selection semantics. It also does not
   implement Windows' peak-guided split, per-cycle gain, or quality-conditioned
   recovery.
2. Current values for activation gating (`0.1`), min blob weight, birth age, and
   baseline drift are **provisional**. They do not establish Windows equivalence.
3. The reported `hold_frames` setting retains internal tracks but **does not
   publish contacts during absent frames**. It is not Windows hold/lift semantics
   and cannot be used as a stable Linux contact-output policy as-is.
4. Local contact IDs and group/class metadata are not Windows virtual-HID IDs.
   The recovered post-report coalescer alone does not determine which internal
   contacts Windows would publish.
5. Gap `>5` is applied to the caller's monotonically increasing frame number;
   the replay enumerator synthesizes numbers from file order. Without hardware
   timestamps/counters, a missing physical frame may be invisible to it.
6. The clean guided V4 run now provides synchronized raw frames and OS-visible
   Win32 pointer contacts on a shared QPC scale. It does **not** expose
   HeatCore's internal candidate classes, groups, pre-publication IDs, or every
   intermediate rejection decision. Screen-to-sensor coordinate calibration
   remains to be measured rather than guessed.
7. A 48-candidate exhaustive adversarial scene is a host robustness check, not
   evidence of practical 48-finger support or acceptable hardware latency.

## Release gates

- Remain a **draft research PR**.
- Keep existing touchscreen driver unchanged.
- Keep the retained raw corpus and synthetic close-birth/pinch/occlusion traces
  in CI; record counts and ID continuity, not only pass/fail tests.
- Use `windows_pointer_oracle.py` and `v4_oracle_contract.py` as the OS-visible
  output gate. Recover classifier/group semantics separately before claiming
  internal Windows equivalence.
- Only then consider opt-in CapImg export, userspace uinput, or in-kernel port.

## Post-audit addendum — archived Windows corpus

On October 17 the preserved Windows CSVs were used in a GitHub Actions
check-out. The new offline extractor recovered the expected **1422 valid V0
frames (638 boot, 247 init, 537 touch)** and passed 31 synthetic/contract
tests. The 537 touch frames replayed as 30 baseline + 507 tracking frames,
with 501/507 exact candidate-count agreements against a separate raw-region
proxy. This retires the earlier limitation that no real frames were run,
**but does not retire the lack of final processed Windows contact truth**.
See WINDOWS-EVIDENCE-INVENTORY.md and Actions run 39049773971.

## Classifier reconstruction checkpoint — 2026-10-18

The field order, suppression mask, count gates, packed upper-triangular
transform, four-score equation and score-3 edge penalties are implemented in
`windows_classifier.py`. `windows_class_transition.py` now adds the recovered
lower-index-tie argmax plus current-frame and history transition gates over the
five-stored-class by four-proposed-class numeric table.

The original static-image audit decoded the wrong base. The tracker initializer
stores `DAT_1808e0460 + 0xecc`, not `DAT_1808e0460`, at context `+0x16480`;
the shifted bytes decode as finite and internally plausible. The code accepts
caller-supplied bytes but bundles no proprietary coefficients. The outer
`FUN_1806067d0` policy, later correction, class meanings, contact behavior,
Gate5, uinput and kernel paths remain unchanged. See
`docs/WINDOWS-CLASSIFIER-TYPING-20261017.md` and
`docs/WINDOWS-CLASS-TRANSITIONS-20261018.md`.
