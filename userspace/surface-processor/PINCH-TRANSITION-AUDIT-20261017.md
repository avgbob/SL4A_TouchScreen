# Correlated pinch — pre-loss transition audit (research PR #12)

**Status:** Offline sensor/contact *behavioral* comparison. No Linux driver changes, no simulated HID output, no production policy switch. Reproducible from [the published privacy-hardened dataset](../../datasets/sl4a-amd-pinch/). This document does not claim exact Windows classifier reconstruction or clock synchronization.

## New result

The 8,232-frame CapImg corpus was examined at all four Windows secondary-contact `UP` events during pinching, not merely the three later user `M` annotations. A 72×48 grid, threshold-150 (lower byte = stronger capacitance), 8-connected regions of at least 3 cells, and an odd 15-frame median filter were used to find approximate persistent transitions from **two raw regions to one**. One short 80 ms return to two regions is kept explicitly rather than silently discarded.

**Calibration controls, chosen outside close-pinch failures:**

| Known Windows event, relative seconds | Raw region transition, relative seconds | Raw minus Windows |
|---|---:|---:|
| First one-finger `UP` (12.018382) | 1 → 0 (12.088102) | +0.069720 s |
| Far-apart second `DOWN` (22.496142) | 1 → 2 (22.544888) | +0.048746 s |
| Deliberate independent finger lift (84.457072) | 2 → 1 (84.524750) | +0.067678 s |
| Final independent release (92.161076) | 1 → 0 (92.197409) | +0.036333 s |

Median **raw-minus-Windows offset: +0.058212 seconds**. The four values span **+0.036333 to +0.069720 seconds**, a 33.4 ms range. This is *behavioral alignment* of detection threshold transitions—not an independent ETL QPC-to-UTC conversion, and not a subframe-precision calibration. Signal/OS event latencies are included in these numbers. Recording gaps were preserved.

### Close-pinch `UP` events

| Windows `UP` (relative s) | First sustained raw 2 → 1 (s) | Raw collapse precedes Windows `UP` by* | Later operator confirms 2 physical fingers before next `DOWN`? |
|---:|---:|---:|---|
| 44.136034 | 42.745236 | **1.449 s** | **No annotation for this interval** |
| 57.116651 | 56.485073 | **0.690 s** | Yes (M1) |
| 63.548000 | 63.178807 | **0.427 s** | Yes (M2) |
| 73.968415 | 72.996253 | **1.030 s** | Yes (M3) |

*Computed as `(Windows UP + median control offset) - first sustained raw 2→1 transition`; estimates depend on the specific sensor detector. In the final row, the data briefly resplit into two raw regions at 73.175953–73.255614 s (~80 ms), but the persistent 2→1 episode began at 72.996253 s. The shorter-lived resplit remains documented, rather than being mistaken for a new sustained detection.

The raw region generally becomes a single region **before** Windows issues `UP` during the pinch, by tenths of a second or longer. This is compatible with a touch-history/quality gate that temporarily retains a contact after the sensor signals overlap. It could also reflect filtering, sensor threshold and a physical gesture evolution. **It does not establish that HeatCore or a specific recovered DLL function implements that exact delay.**

The fourth event's physical state at the instant of `UP` was *not* separately annotated. The other three intervals have later `M` annotations that establish two physical fingers only at those later moments, **not** continuously through every preceding millisecond.

## Weak-signal falsification experiment

The same frame data was tested with a very permissive smoothed local-peak search: 3×3 mean-depth relative to nominal background 180, non-maximal suppression requiring peaks 4 sensor cells apart, strength thresholds **2, 5, 10, and 20** (lower thresholds are more permissive). These are *not* Microsoft classifier conditions. Evaluation used **75 frames sampled across the three M windows** plus control samples.

| Region / frame sample | At least two qualifying smoothed peaks, across all tested thresholds |
|---|---:|
| Early genuine one-finger control (60 frames) | 0/60 |
| Late genuine single remaining finger (61 frames) | 0/61 |
| Wide-apart two-finger hold (31 frames) | 31/31 |
| M1 (25 frames) | **0/25** |
| M2 (25 frames) | **0/25** |
| M3 (25 frames) | **0/25** |

Lowering the peak threshold to **2** did **not** recover a clearly separated second local maximum in the annotated failure windows. That argues against an easy detector-threshold tweak or simple watershed split. It **does not prove only one physical finger is encoded in the raster**: two contacts may be closer than four sensor cells, generate a single maximum, or require learned shape/history deconvolution.

## Engineering decision

- **Do not patch a fixed hold timer into the Linux output path.** In the independent-lift control at ~84.46 s and the final genuine release at ~92.16 s, a second contact held on solely because it previously existed would be a ghost. Stage 4 is critical negative evidence.
- Investigate **tracking-history and occlusion as unreported shadow state** first. This can track a hypothesis of continuity for analysis without outputting an extra finger; output policy requires explicit confidence and physical qualification.
- Investigate whether morphology (contact area, mass, orientation and trajectory over ~2s before `UP`) distinguishes a close merge from a real release. Current controls do **not** uniquely label all pre-`UP` physical states, so the appropriate output rule remains open.
- Calibrate QPC↔UTC or collect a synchronized physical-contact label at each actual release before making claims of exact event latency or Windows implementation parity.
- Keep PR #12 experimental and **do not modify** the working Gate5 Linux kernel path, the in-tree kernel experiment, or upstream Syax PR #87.

## Reproduce

```bash
# In research/windows-contact-processor-v1 working tree (Python 3.11 stdlib only):
python3 userspace/surface-processor/pinch_transition_audit.py \
  SL4A_heatmaps_privacy_hardened.zip --output /tmp/sl4a-transition-audit.json
python3 -m unittest discover -s userspace/surface-processor -p 'test_*.py' -v
```

The dataset ZIP SHA256 is `2c77050b9356b141ff0b30acf0a99a896db86a31d43cde6922dca558174aed2a` and its heatmap-only content SHA256 is `fa4773c352178cb06fcbd686d5e021d98bae03af4ca4ccc94f93a2e3f63f71a9`.

Regression tests cover sensor region counts, jitter filtering, four independent event alignment anchors, valid/no-match cases, short merge flicker vs sustained re-separation, and explicitly **no input emission** from the audit. Published CI downloads/validates the fixed dataset by SHA before comparison and retains the JSON report as an Actions artifact.