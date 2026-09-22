# Hardware Qualification Tracker — SL4 AMD Post-Association Tracker

This file tracks the broader Surface Laptop 4 AMD hardware matrix for
`tracker/post-association-coalescing` after the targeted pinch-continuity fix.

It is **not** an E1 release-qualification record. The blinded A/B/C crossover
protocol in `docs/HARDWARE_VALIDATION.md` remains the authority for an E1
claim. This tracker is the practical candidate matrix used to decide whether
the current raw tracker is stable enough to proceed to that protocol.

## Current Candidate

| Item | Value |
| --- | --- |
| Branch | `tracker/post-association-coalescing` |
| Tracker implementation base | `07065e0` |
| Documentation HEAD before this tracker | `151a016` |
| Tested module srcversion | `F1084988B115CF74C159D58` |
| Signed module SHA-256 | `c42fa1575d45a49319a8900be822dba73a8833c8fbff7a941e8620441015c6b9` |
| Kernel | `7.0.0-29-generic` |
| Device | Surface Laptop 4 AMD; MSHW0231 |
| Targeted pinch run | `sl4a-pinch-final-20260921-194612` |

The targeted physical pinch run preserved the same Linux tracking IDs through
far -> pinch -> close hold -> expand -> far. It recorded 278 weak-component
continuity rescues, one weak-occlusion arm, 18 explicit occlusion-hold frames,
same-slot reacquisition after a 20-frame detector blackout, and ordinary
`2 -> 3 -> 0` release on the final intentional lift. The host emulator also
covers a 37-frame synthetic blackout and completes 469 assertions with zero
failures.

## Candidate Hardware Matrix

Keep every evidence directory intact and preserve its manifest/checksums.

| Case | Status | Required observation |
| --- | --- | --- |
| Cold boot | PASS after profile correction | Corrected persistent profile (`raw_mode=N raw_input_beta=Y std_raw_transition=3`) survived a true cold boot with `F1084988B115CF74C159D58`; `MSHW0231 Touchscreen` returned on `event15`, the beta MT bridge registered, and the boot log showed the intended mode-3 SET5 transition. The earlier profile-mismatch failure is retained below. |
| Warm boot | TODO | Same checks after normal reboot. |
| Suspend/resume >=30 s | TODO | Touch returns after resume; binding/state sane; no input loss. |
| Safe module reload | PASS | `F7D22... -> F108...`; touchscreen returned; known descriptor fallback bound successfully. |
| Pen/stylus | TODO | Record pass/fail/not observed; capture stylus trace if present. |
| One finger | TODO | Contact appears and releases normally. |
| Two-finger pinch/expand | PASS | Same two tracking IDs preserved through the complete gesture. |
| Three fingers | TODO | Three contacts appear and all release. |
| Four fingers | TODO | Four contacts appear and all release. |
| Five fingers | TODO | Five contacts appear and all release; record degradation if present. |
| One-finger lift after close two-finger state | TODO | Lifted ID disappears; remaining ID stays stable; no ghost reappearance. |
| 30-minute mixed-input stress | TODO | No input loss/stuck contacts; start/end protocol stats recorded; kernel log reviewed. |

## Cold-Boot Finding — 2026-09-21

The first cold-boot qualification attempt is retained as a failure rather than
discarded. The intended module srcversion loaded successfully, and the standard
HID descriptor fallback completed, but the raw multitouch bridge did not
register. The boot log therefore exposed only the HID-core `spi 045E:0C19`
nodes (plus stylus), while the expected `MSHW0231 Touchscreen` beta bridge was
absent and the direct-touch evidence helper exited without a matching target.

This is a profile-persistence mismatch, not evidence that the post-association
tracker regressed: the successful physical tracker run was loaded with
`raw_mode=N raw_input_beta=Y`, whereas the repository's supported standard
installer profile intentionally writes `raw_mode=N wire_double_opcode=1` and
does not enable `raw_input_beta`. Qualification must use one explicit,
versioned beta-bridge profile on every lifecycle test so a reboot and a manual
reload exercise the same input semantics.

After persisting the qualification profile with
`raw_mode=N raw_input_beta=Y std_raw_transition=3`, a second true cold boot
loaded the same `F1084988B115CF74C159D58` module, recreated
`MSHW0231 Touchscreen` on `event15`, registered both the heatmap input and
standard-transport MT bridge, and executed
`standard-mode raw transition: mode=3 GET6=0 SET5=1`. Functional multitouch
was also observed after boot. Cold boot is therefore PASS for the corrected
candidate profile; the failed first attempt remains part of the qualification
history because it exposed the persistence mismatch.

The first corrected cold-boot evidence session used
`--capture-direct-touch`, which intentionally selects the standard HID
`spi 045E:0C19` node rather than the beta bridge, and the unprivileged caller
could not open that event device. That artifact remains useful provenance but
is not the input trace for this matrix. Candidate touch cases must use
`--capture-beta-multitouch`; on systems where the invoking user cannot read
`/dev/input/event*`, run the read-only evidence wrapper with `sudo`. The
trace bundle propagates requested capture failures so they cannot be recorded
as a completed session.

## Evidence Root

Use one root for this candidate:

```sh
RUN="$HOME/SL4A_TouchScreen-pr4-validate/evidence/20260921-sl4a-amd-F108"
mkdir -p "$RUN"
```

The helpers refuse to overwrite existing case directories, so repeated attempts
must use a new case name or suffix rather than replacing evidence.

## Case Capture Pattern

For ordinary touch cases:

```sh
sudo ./tools/hardware_evidence/run_blinded_session.sh \
  --period p1 \
  --case CASE \
  --duration 20 \
  --capture-beta-multitouch \
  --output "$RUN/p1-CASE"
```

The `p1` label here is only an opaque artifact namespace for this unblinded
candidate matrix. It does not mean the blinded A/B/C protocol has been run.

For pen:

```sh
./tools/hardware_evidence/run_blinded_session.sh \
  --period p1 \
  --case pen \
  --duration 20 \
  --capture-stylus \
  --output "$RUN/p1-pen"
```

For the stress period:

```sh
sudo ./tools/hardware_evidence/run_blinded_session.sh \
  --period p1 \
  --case mixed-stress-30m \
  --duration 1800 \
  --capture-beta-multitouch \
  --output "$RUN/p1-mixed-stress-30m"
```

## Recommended Execution Order

1. Cold boot.
2. Warm boot.
3. Suspend for at least 30 seconds, then resume.
4. Pen/stylus observation.
5. One-finger contact/release.
6. Three-finger contact/release.
7. Four-finger contact/release.
8. Five-finger contact/release.
9. One-finger lift while a second finger remains after a close two-finger state.
10. Thirty minutes of mixed-input stress.

The reload and two-finger pinch cases are already physically covered for the
current candidate and remain marked PASS above.

## Acceptance Rules

For every contact-count case, require the requested contact count, normal
release, no unrequested tracking-ID births, no stuck contact after lift, and no
new kernel crash/oops/warning attributable to the tracker.

For lifecycle cases, require the expected touchscreen/HID input nodes to return
with one controller/device binding and usable touch input. A missing node,
failed resume, or required manual recovery is a failure and must remain in the
evidence record.

For the one-finger-lift safety case, the extended pinch occlusion path must not
keep the intentionally lifted contact alive. The remaining contact must retain
its ID while the lifted ID disappears after the ordinary release behavior.

Do not add an E1 row to `docs/COMPATIBILITY.md` from this matrix alone.
