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
   fingers can become one connected component; the prototype does not implement
   peak-guided split, the recovered candidate classifier `FUN_180601690`, per-cycle
   gain, or quality-conditioned recovery.
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
6. No synchronized raw/processed Windows reference capture was available in the
   execution environment. The historic 537-frame raw capture was **not** run;
   comparison to Windows processed contacts remains **unverified**.
7. A 48-candidate exhaustive adversarial scene is a host robustness check, not
   evidence of practical 48-finger support or acceptable hardware latency.

## Release gates

- Remain a **draft research PR**.
- Keep existing touchscreen driver unchanged.
- Run the retained raw corpus and synthetic close-birth/pinch/occlusion traces;
  record counts and ID continuity, not only pass/fail tests.
- Acquire a frame/time-aligned **processed Windows contact** oracle; establish
  classifications and actual emission semantics before claiming parity.
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
