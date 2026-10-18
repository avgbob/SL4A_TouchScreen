# PR #12 — internal shadow-contact experiment (2026-10-17)

**Status:** Read-only, offline, deliberately **diagnostic-only**. No synthetic input
contacts, Linux driver changes, HID commands, or auto-promotion of proposed IDs.
**Not a Windows classifier reconstruction.** The only replay source is the
[public 8,232-frame anonymized SL4A pinch raster](../../datasets/sl4a-amd-pinch/).

## Hypothesis and experiment

When two separately reported contacts collapse to one sensor-derived candidate,
there are two materially different possible explanations:
1. Both fingers remain on the glass but overlap in the 72×48 raster.
2. A finger was deliberately lifted; keeping it alive as an emitted input contact
   would create a ghost touch.

This experiment keeps the disappearance as an *internal shadow hypothesis* only
when (a) the prototype had two visible candidate-derived contacts, (b) exactly
one disappeared while the other survived, (c) their last **sensor-grid** positions
were within seven cells and the lost contact was at least three observations old,
and (d) the shadow table had capacity. A newly **observed** second contact can
propose a reconciliation if it is near the old location, sufficiently separated
from the surviving contact, and arrives before a configurable TTL. An actual
reported contact is **never created from shadow memory**. The normal mode also
never reuses a prior ID merely on the strength of this proposal. Optional auto-label reuse is an explicitly unsafe research knob, NOT enabled in this
replay.

## Reproduce

From `userspace/surface-processor/` using Python 3.10+, stdlib only:

```bash
python3 -m unittest discover -p 'test_*.py' -v
python3 shadow_replay.py /path/to/SL4A_heatmaps_privacy_hardened.zip \
  --output /tmp/sl4a-shadow-sweep.json
```

`shadow_replay.py` feeds the unchanged `processor.py` all 8,232 frames,
resets its original track state on the actual >200 ms input gap, and passes
**only emitted prototype contacts** to independent overlay instances for each
TTL. Real relative sensor timestamps are retained. The Windows-pointer
annotations are included only as **approximately aligned** diagnostic examples.

## Results on the real 8,232-frame corpus

| Internal retention TTL | Eligible two→one disappearance hypotheses | Possible identity reconnections | Actual ID reuse, conservative default | Unresolved shadows at three M examples |
| --- | ---: | ---: | ---: | --- |
| 0.2 seconds | 22 | 16 | **0** | 0/3 |
| 0.4 seconds | 22 | 17 | **0** | 0/3 |
| 1.0 seconds | 22 | 18 | **0** | 0/3 |
| 2.0 seconds | 22 | 19 | **0** | 2/3 |

All four sweeps left the source processor's visible-count histogram unchanged:
**66 frames with zero contacts; 3,529 with one; 4,637 with two**.
Thus shadow state does not invent an output finger, and the single original
~10.107-second data gap cleared stale identity memory.

**Do not interpret these numbers as measured recovery accuracy.** The recorded
physical two-finger observations do not prove which proposed new source contact
is the same anatomical finger; a genuine lift followed by a different finger
at the same place is observationally indistinguishable without additional
physical evidence. The 16–19 proposed joins can include false continuity. The
three M marker-to-frame associations use a behavioral sensor/OS clock offset
(~58 ms) rather than a validated kernel timestamp correspondence.

An important **negative result**: 0.2–1 second shadow policies have **no
shadow active at any of the three physically confirmed M examples**; even the
2-second policy only has shadow hypotheses at two of three. Reassociation
proposals mostly correspond to shorter periods of prototype candidate churn,
not automatically to the longer contact losses observed by the operator.

## Adversarial safety tests

- One genuine finger lifts while the other remains: shadow may exist internally
  until TTL, but **only the single detected contact** is output.
- Far-apart independent lift cannot create an occlusion hypothesis.
- New far-away contacts do not reuse the missing finger's label.
- Close new candidate cannot reattach while still spatially indistinct from its
  surviving anchor.
- Releasing both contacts clears all memory; no ghost can survive zero visible.
- A >200-ms time gap or >5-frame discontinuity invalidates memory.
- Insufficiently aged contacts, repeated frame numbers, invalid coordinates,
  duplicate IDs, and nonmonotonic timestamps cannot authorize reconstruction.
- Rapid genuine lift followed by a different close-by finger touch is
  **inherently ambiguous**. The default records a *proposal* but gives the new
  detected contact a fresh ID; the explicit opt-in reuse setting is unsafe.

## Engineering decision

**Research prototype is useful as a bounded identity diagnostic, not as a fix.**
The measured failure windows do not yet support an input-report hold timer or
silent ID resurrection. No Gate5, experimental kernel branch, or upstream Syax
pull request was modified.

**Next qualification gate:** Add independent physical continuity/lift labels
(e.g., synchronized tabletop video or a test jig, with consent), and derive a
Windows-independent sensor-to-OS timestamp mapping. Compare candidate/track
history against confirmed individual finger lifts and same-place new touches.
Only then consider opt-in actual ID reuse, and quantify false reconnections.