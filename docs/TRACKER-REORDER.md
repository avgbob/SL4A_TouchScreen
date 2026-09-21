# Tracker reorder: association before close-contact suppression

Status: **implementation branch / not release-qualified**

Branch: `tracker/post-association-coalescing`

This branch converts the experimentally-proven close-contact workaround into the
pipeline order recovered from `TouchPenProcessor0C19.dll`: candidate-to-track
association happens before any close-contact coalescing/suppression decision.

## Why this change exists

The previous Linux order was:

```text
candidate extraction
  -> destructive ghost merge
  -> Hungarian assignment
  -> slot state machine
```

A two-finger MSHW0231 field capture showed that this order was wrong in a
directly measurable way. Across the captured frames, every pair of legitimate
pre-merge blobs below the six-cell `ghost_dist` threshold was collapsed to one
before Hungarian could see the second candidate. The second Linux slot then aged
toward lift even though the detector still had two physical-contact candidates.

The diagnostic bridge in `tracking/pinch-split-diagnostics` proved the inverse:
when two close candidates could be explained by two established tracks, keeping
both through Hungarian preserved both Linux contacts below the same six-cell
threshold.

The recovered Windows order independently says:

```text
candidate extraction
  -> candidate/track association
  -> track update/state selection
  -> contact records
  -> report coalescing
```

and its coalescing function keeps both local contact records; it rewrites
classification/group state rather than deleting a candidate before tracking.

## What this branch changes

The Linux tracker now does:

```text
candidate extraction
  -> Hungarian assignment
  -> post-association close-candidate policy
  -> slot state machine
  -> MT emission
```

The post-association policy is deliberately conservative:

- state 2 (active) and state 3 (lift-pending) are treated as established
  continuity;
- two close candidates assigned to two different established tracks are both
  preserved;
- an established track wins over a close candidate assigned to a
  non-established slot;
- if neither candidate has established-track continuity, the higher
  pre-edge-penalty `raw_w` candidate wins, preserving the old duplicate
  rejection behavior;
- the comparison remains strict: exactly six cells is not suppressed.

This is **not** a claim that Linux now reproduces the complete Windows
classification/coalescing state machine. The Windows processor has candidate
classes and mutable merge-group labels that Linux does not yet model.

## Deterministic host regression

`tests/tracker_coalescing_host_test.c` includes the staged real
`driver/mshw0231-raw.c` and directly exercises the driver implementation.

It pins these cases:

1. two established contacts below six cells survive;
2. an active + lift-pending pair below six cells survives;
3. an established contact beats a heavier close new candidate;
4. two ambiguous new close candidates still collapse to the stronger raw blob;
5. exactly six cells remains outside the strict coalescing threshold;
6. a deterministic one-frame dropout sends one slot `2 -> 3`, then the next
   two-candidate close frame recovers that same slot `3 -> 2` without
   reallocating it.

That last case replaces the need to physically induce the rare one-frame split
hiccup by hand.

## Important remaining gap

This branch intentionally does **not** solve the "two contacts are first born
already very close" ambiguity. With no established tracks, two close candidates
still use conservative raw-weight duplicate suppression.

The recovered Windows processor resolves this with earlier candidate
classification/suppression plus persistent track state. The next tracker
milestone should therefore be classification/history work, not another
`ghost_dist` radius experiment.

A second remaining issue is the CCL split stage: a frame can contain two peaks
but emit one blob when `HEATMAP_SPLIT_MIN_DIST` considers the peaks too close.
Established slot grace now makes a one-frame event recoverable, but a robust
tracker should eventually use existing track hypotheses to interpret such a
merged component rather than relying only on a static split distance.

## Transport boundary

This tracker work is independent of the raw transport experiment. The intended
SL4 path remains:

```text
normal HID-over-SPI discovery
  -> suppress harmful standard feature Report 6 transaction
  -> SET_FEATURE Report 5 only
  -> standard-path CapImg 0x0c
  -> heatmap/contact processor
```

`raw_mode=Y` is not required for this path.

## Before release qualification

Do not promote this branch directly to a release profile until all of the
following are complete:

- host CI and kernel builds pass;
- captured-frame/local replay still builds against the reordered static stages;
- cold boot validates the final Report-6/SET5 profile without a manual reload;
- suspend/resume re-enters SET5 and reacquires CapImg cleanly;
- close-start contact creation is addressed by classification/persistent-track
  logic rather than another distance-only tweak;
- debug-only TRACKDBG/SPLITDBG volume is reduced;
- the kernel stack-frame warnings in the tracker are removed or justified.
