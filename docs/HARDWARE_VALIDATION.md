# Blinded Crossover Hardware Validation

This is a planned validation protocol, not a hardware result. Complete results
are required before an E1 claim or release qualification is recorded.

## Targeted Tracker Regression Result — 2026-09-21 (Not E1)

A focused Surface Laptop 4 AMD hardware run was completed for the
post-association pinch-continuity work that was developed on
`tracker/post-association-coalescing` and later merged to `main` in PR #4.
This is regression evidence only; it does **not** replace the blinded crossover
protocol below and does not qualify the merged implementation for an E1 or
release claim.

Hardware/test provenance recorded for this run:

| Item | Value |
| --- | --- |
| Device | Surface Laptop 4 AMD, MSHW0231 |
| Kernel | `7.0.0-29-generic` |
| Branch HEAD | `07065e0` (`tests: mirror occlusion tracker fields in host shim`) |
| Live test module | `sl4a-spi-hid.ko` srcversion `F1084988B115CF74C159D58` |
| Signed module SHA-256 | `c42fa1575d45a49319a8900be822dba73a8833c8fbff7a941e8620441015c6b9` |
| Raw tracker parameters | `raw_mode=N raw_input_beta=Y ghost_dist=6 blob_max_distance=3 blob_debounce=3 blob_lift_frames=3 hold_frames=0` |
| Focused run id | `sl4a-pinch-final-20260921-194612` |
| Host emulator | 469 assertions, 0 failures |

The focused gesture established two contacts far apart, pinched them together,
held them close, expanded them again, and then lifted. Linux kept the same two
tracking IDs throughout the gesture:

```text
FAR HOLD      active=2 slots={0:8, 1:9}
PINCH START   active=2 slots={0:8, 1:9}
CLOSE HOLD    active=2 slots={0:8, 1:9}
EXPAND START  active=2 slots={0:8, 1:9}
FAR HOLD 2    active=2 slots={0:8, 1:9}
```

The trace also exercised the intended continuity paths rather than merely
avoiding the detector corner case:

- 278 detector-continuity rescues were recorded, including sub-1000 and
  one-pixel weak components.
- The weak-occlusion path armed once at score 5.
- The same established slot survived a real 20-frame detector blackout;
  18 frames were explicitly retained by the occlusion hold after the normal
  three-frame lift threshold was reached.
- The missing contact reacquired the same slot and tracking ID.
- At the final intentional lift, both slots had `weak_score=0` and
  `occlusion=0`, then followed the ordinary `2 -> 3 -> 0` release path.
- The deterministic host emulator additionally covers a 37-frame synthetic
  blackout and completed 469 assertions with zero failures.

This result validates the specific pinch tracking-ID regression on this
hardware/build combination. It does not cover the full hardware matrix:
cold boot, warm boot, suspend/resume, pen, the complete one-through-five-finger
matrix, long mixed-input stress, and blinded profile comparison remain required
by the protocol below. The local evtest/kernel capture is not committed to the
repository and must be preserved separately if it is to be used as future
audit evidence.

The practical unblinded candidate matrix is tracked in
[`docs/HARDWARE_QUALIFICATION_TRACKER.md`](HARDWARE_QUALIFICATION_TRACKER.md).
Completing that checklist is useful prequalification evidence but does not
replace the blinded E1 protocol below.

## Profiles And Randomization

The test operator and results assessor see only the blind labels `A`, `B`, and
`C`. The profile custodian prepares the following profiles and installs the
assigned profile before each period:

| Label | Profile | Purpose |
| --- | --- | --- |
| A | Standard HID package profile | Controlled-release candidate. |
| B | Raw package profile (`sl4a-touch.sh install --raw`) | Explicit experimental comparison. |
| C | No SL4A package installed | Baseline control. |

For each device, use a balanced cyclic order: `A-B-C`, `B-C-A`, or `C-A-B`.
Randomly assign a sequence before testing; do not substitute a failed period.
Use a fresh reboot after every profile installation or removal. The custodian
keeps the label-to-profile key, randomization record, and installed revision
outside the operator's worksheet until all periods are signed off. The operator
records observations verbatim and does not inspect installation commands,
module parameters, or the key. A separate assessor calculates the predeclared
metrics from anonymized artifacts and freezes the results before unblinding.
Full concealment of visible capability differences is not possible; the blind
prevents profile expectation and post-hoc outcome selection.

## Safety Disclosure

Blinding does not conceal safety-relevant information. Before every period, the
operator is told that the profile can affect touchscreen input, is not
release-qualified, and that B may enable experimental raw processing. Keep a
keyboard or other independent input available. Stop the period, preserve the
evidence, and report a kernel warning, crash, unexpected input, thermal issue,
or inability to recover input. Do not perform reload while an input client uses
the device or while a period is actively being configured.

## Predeclared Cases And Metrics

Run every case once per period, in this order: cold boot, warm boot,
suspend/resume (at least 30 seconds), reload when safe, pen, one through five
fingers, and 30 minutes of mixed-input stress. Record `pass`, `fail`, `not
observed`, or `not applicable`; do not reinterpret a missing device as a pass.

| Case | Metrics recorded before unblinding |
| --- | --- |
| Boot, resume, reload | HID/input presence, one controller/device binding, `ready`, lifecycle state, kernel warnings/errors. |
| Pen and one through five fingers | Input event presence, contact count, releases, spurious or stuck contacts, and bounded direct-touch `evtest` evidence when available. |
| Stress | Duration, start/end `protocol_stats`, error count, input loss, and kernel warnings/errors. |
| Every period | BIOS/firmware, kernel, distribution, Secure Boot/MOK state, profile label, and non-default parameters. |

## Artifacts And Storage

Collect after each case group and at the end of stress, using a unique path:

```sh
./tools/hardware_evidence/collect.sh --output \
  evidence/<run-id>/<period>-<case>-sl4a-hardware-evidence-<UTC>
```

For the one-touch case, also create a new bounded direct-touch trace while
performing the input action:

```sh
./tools/hardware_evidence/capture_direct_touch.sh --duration 20 \
  --output evidence/<run-id>/<period>-<case>-direct-touch.evtest.txt
```

For the pen case, capture the dynamically discovered stylus node instead:

```sh
./tools/hardware_evidence/capture_stylus.sh --duration 20 \
  --output evidence/<run-id>/<period>-<case>-stylus.evtest.txt
```

The helper discovers the HID direct-touch node from sysfs identity and
capabilities rather than an `eventN` value. Do not install `evtest` or alter
drivers for this protocol. If the caller lacks `/dev/input` access, invoke the
read-only helper with `sudo`; it returns the capture file to the invoking user.
If `evtest` or device access is unavailable, record that fact as `not observed`
with the collection artifact.

The stylus helper requires exactly one HID `045E:0C19` input whose name contains
`Stylus` and which exposes absolute X/Y and pen-tool capability. The blinded
session runner can request it without profile knowledge using `--capture-stylus`;
the trace is retained at `trace/input/stylus.evtest.txt`.

Use `<run-id>` as `YYYYMMDD-device-id` and `<period>` as `p1`, `p2`, or `p3`;
do not put the unblinded profile name in artifact paths. Preserve the generated
`manifest.txt`, its complete listed tree, command recordings, operator worksheet,
separately. Input traces or raw captures may contain personal data; store them
only with the required approval and access controls. The collector records
missing or unreadable state as evidence and must not be edited to imply success.

## Unblinding And E1 Recording

After every assigned period is complete, the operator signs the worksheet and
artifact list. The custodian then releases the key, joins labels to profiles,
and records deviations and failures before any analysis. A failed, stopped, or
incomplete period remains in the result. Do not claim equivalence from this
protocol alone.

Only a reproducible completed run may add an E1 row to
`docs/COMPATIBILITY.md`; an empty or failed run is not release-qualified. Copy
this row, replace every placeholder, and link the immutable artifact location:

```text
| YYYY-MM-DD | Surface Laptop 4 AMD; AMDI0060/MSHW0231 | <BIOS and touchscreen firmware> | <kernel> | <distribution> | <unblinded A/B/C profile and parameters> | <Secure Boot state; MOK/signature result> | <per-case outcomes and deviations> | E1: <run-id>, <artifact path>, <checksums> |
```

Also add the dated E1 source to `docs/EVIDENCE.md`. No row is added until
unblinding, provenance review, and artifact checksum verification are complete.
