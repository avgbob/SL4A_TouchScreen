# MSHW0231 Linux driver roadmap toward Windows-like behavior

Status: **transport substantially solved for one SL4 AMD; contact behavior is
still research-grade.** This document separates proven transport, current
Linux policy, Windows reconstruction, and eventual production integration.

## Target

The goal is normal Linux Type-B multitouch input with observable behavior as
close to Windows as evidence permits: contact count, birth/lift latency,
identity continuity, coordinates, smoothing and shape. It is not byte-for-byte
emulation of proprietary internal records, and known Windows failures need not
be reproduced when Linux can improve them without creating ghosts.

## Architectural boundary

1. Kernel transport: AMD SPI, HID-over-SPI, power/reset/resume, Gate5/PR87
   activation and strict CapImg decoding.
2. Reference processor: detector, classifier, association/history, hold/lift,
   grouping and emission, developed offline and in userspace first.
3. Linux output: Type-B multitouch through uinput during qualification, then a
   measured decision whether the stable bounded core belongs in userspace or
   the kernel.

Do not modify the qualified transport merely because a contact-processing
hypothesis changes.

## Current audit

| Layer | State | Remaining gate |
|---|---|---|
| MSHW0231 transport and Gate5 activation | Physically exercised on one SL4 AMD | Exact-source E1 record, long soak and broader machines |
| Strict V0 `0x0c` decoder | 4304-byte body and 72x48 raster replayed | Fuzz/static audit and any firmware variants |
| Linux in-kernel tracker | Produces Type-B MT input | Not Windows-qualified; many policies remain heuristic |
| Windows raw corpus | 1,422 historical plus 8,232 and 17,018 correlated frames | Preserve privately and publish only sanitized aggregates |
| OS-visible Windows reference | V4 frame-aligned pointer oracle and proxy transform exist | Recover classifier coordinate and expand comparison metrics |
| Windows candidate classifier | Ten-field decoder and four-block score kernel implemented offline with exact mask/gate/triangular arithmetic | Recover initialized runtime config, overrides, winner propagation and class meanings |
| Association/history | Major functions, 48 tracks and ten histories recovered | Exact units, costs and state transitions |
| Hold/lift | Simple timer and morphology rules falsified | Reconstruct quality/history-conditioned logic |
| Grouping/emission | Some grouping and HeatCore record paths recovered | Map internal IDs/flags to observable emission |
| Palm/stylus | Unqualified | Separate evidence and test matrix |

## V4 facts every future processor must satisfy

- Established Windows contacts can remain two while thresholded sensor data is
  one connected region.
- A returned close finger can eventually be born while that same proxy remains
  one region.
- A genuine lift can make the surviving region stronger and larger.
- A fixed hold timer or morphology-only shadow would create a ghost.
- The clean run has 17,018 raw frames, 14 balanced pointer lifetimes and 19
  guided holds. `v4_oracle_contract.py` locks the sanitized counterexamples.

Established-track occlusion, new-contact birth and genuine release are three
separate decisions. A rule solving only one must not ship.

## Assumptions prohibited from release claims

- Connected components or local peaks equal physical fingers.
- Windows numeric class/state values have guessed semantic names.
- Windows state numbers map directly to Linux slot states.
- Association constants are in Linux grid units without a recovered transform.
- Grouping proves destructive candidate deletion.
- Synthetic tests, a kernel compile, or raw-frame availability proves parity.
- One qualified machine establishes broad compatibility.

## Ordered implementation plan

### R0 — Evidence consolidation

- Keep this roadmap, `docs/EVIDENCE.md`, the V4 results and exact branch heads
  current.
- Mark superseded classifier, raster, clock and morphology interpretations.
- Keep coordinate-bearing heatmaps/oracles private.

Gate: every behavioral claim names a capture, revision and evidence level.

### R1 — Freeze the exact transport baseline

- Use the focused PR87 source, not a hybrid tracker branch.
- Repeat cold boot, three warm reloads, two s2idle cycles, default-negative
  control, reset recovery and a long stream on the exact head.
- Record module hashes, kernel, firmware, parameters and drop/reset counters.

Gate: exact-source E1 entry; no processor changes in the transport result.

### R2 — Golden OS-visible oracle

- Generate the private V4 JSONL with `windows_pointer_oracle.py`.
- Preserve screen-pixel coordinates and relative QPC timing without guessing a
  grid transform.
- Validate all 19 holds with `v4_oracle_contract.py`.
- Measure a screen-to-sensor transform separately and version it.

Gate: **passed for the V4 OS-visible/proxy layer** — deterministic 17,018-frame
oracle, balanced lifetimes, contract pass, and independent two-contact proxy
validation p95 0.695 cells. This is not internal classifier geometry.

### R3 — Executable Windows reference model

Implement separately testable stages with function/config provenance:

1. decode, baseline and per-cycle gain;
2. candidate feature extraction;
3. ten-feature/four-block classification;
4. association and ten-sample history;
5. quality/age-conditioned hold and lift;
6. grouping and final emission.

Unknown classes stay numeric and unknown. Linux-specific policy must be
labelled as such.

Gate: the same model handles far controls, established close occlusion,
deliberate lift and returned-finger birth without stage-name special cases.

R3 checkpoint (2026-10-18): the common `FUN_180601690` arithmetic is now an
isolated, tested executable specification; see
`WINDOWS-CLASSIFIER-TYPING-20261017.md`. The DLL static image is not a valid
runtime coefficient snapshot (one interpreted block contains five NaNs), so
the kernel intentionally has no default model and is not wired into replay.
Candidate overrides, downstream score selection, hold/lift and emission remain
open; R3's behavioral gate has **not** passed.

### R4 — Quantified comparison

Report contact-count agreement, false/missed-contact duration, birth/lift
latency, ID switches, position RMS/max error, velocity discontinuity and
major/minor/orientation error. Windows' observed 1.436-second horizontal-close
failure is a reference limitation, not a bug Linux must intentionally copy.

Gate: defined thresholds pass on V4, historical raw data and synthetic adverse
inputs.

Initial default-prototype baseline: complete 17,018-frame comparison; 1,611 of
2,484 conservative guided frames had equal contact count. The 873 unequal
frames concentrate in provisional baseline/birth behavior and close second-
contact separation. Treat this as a discrepancy baseline, never a parity
percentage.

### R5 — Opt-in userspace output

- Consume validated raw reports, preferably through an existing safe HID path
  before inventing a permanent kernel ABI.
- Emit uinput Type-B contacts only from observed/qualified state; diagnostic
  shadows never emit.
- Release all contacts on discontinuity, suspend, daemon restart or transport
  reset.
- Preserve the known-working kernel tracker as rollback.

Gate: physical one/two-finger matrix passes with no deliberate-lift ghosts.

### R6 — Production placement

Measure latency, CPU, memory, jitter, startup and suspend behavior. Keep the
processor in userspace unless measurements justify a bounded fixed-point kernel
port. A kernel port may not use floating point, unbounded allocation or
unreviewed proprietary record formats.

### R7 — Upstream in small pieces

1. transport/lifecycle;
2. decoder/raw delivery if independently required;
3. evidence-backed association correction;
4. reference processor and replay tools;
5. Linux output integration;
6. optional fixed-point kernel processor;
7. additional hardware IDs only with their own evidence.

The custom in-tree kernel branch remains a build/package laboratory. A
successful kernel package does not prove boot, ACPI binding, Secure Boot,
suspend or touch behavior.

## Completion definition

Windows-like behavior can be claimed only when exact-source transport is
reproducible, V4 counterexamples pass, true lifts do not ghost, close returned
contacts have acceptable measured birth latency, IDs and coordinates meet
published limits, reset/resume clears state, and hardware/model limitations are
explicit. Until then the correct description is **working transport with an
experimental Linux contact processor**.
