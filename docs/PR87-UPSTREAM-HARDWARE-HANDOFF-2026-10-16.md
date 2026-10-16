# PR #87 — exact-head physical qualification handoff (2026-10-16)

**For upstream review; draft text, NOT automatically posted to the PR.**

PR: https://github.com/Syax89/SL4A_TouchScreen/pull/87 (open draft
when reviewed at 22:24 UTC on October 16).
Tested exact upstream PR head: `18f0fe79623e6de4fdf1ae493f82a7048397386a`.
Test unit: **Surface Laptop 4 AMD, MSHW0231**, Ubuntu kernel
`7.0.0-34-generic`, same enrolled signing MOK.
One physical device only; no multi-device compatibility assertion.

## Proposed GitHub reply to Syax89

@Syax89 Final **exact-head physical acceptance** results for PR #87,
source `18f0fe79623e6de4fdf1ae493f82a7048397386a`,
on my **Surface Laptop 4 AMD / MSHW0231**, Ubuntu
`7.0.0-34-generic`:

| Defined physical category | Result |
| --- | --- |
| Warm activations, same signed module | **3/3 PASS** |
| Genuine s2idle cycles with postwake gesture capture | **2/2 PASS** |
| Full evdev-gated gesture matrix, 1–5 fingers | **16/16 PASS** |
| Default-standard opt-out/device-registration negative control | **PASS**, on retrospective correction of a verifier false negative |
| True cold first-HID initialization after full poweroff/on | **PASS** |

All trials used the same pinned experimental source; the signed
PR module was SHA256
`61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`
and loaded `srcversion=65F0D14FBDFB5E84748373E`,
distinct from installed Gate5 `3326E559A916BE5CB52375D`.

For the **new cold first-HID trial**, the staging boot ID was
`275a12d5-5e6c-42cc-98cd-28b8435eb5a7`;
the trial/current boot ID was
`97c56a82-481b-4f05-b0f1-7f3f8f8558eb`.
After a reported full shutdown/physical power-on, a one-shot boot hook
consumed itself before loading the experimental module, rejected
an already loaded/earlier-probed HID path, and recorded source and
kernel identity. The independent rollback timer was armed before
insertion. The operator confirmed `COLD_PR87` and then completed
an audible/event-gated single-finger move/lift and continuous
two-finger pinch→expand→full-release capture **PASS**. The runner
reported source/reset/drop checks and capture hashes passing.
At 22:24:19 UTC the exact-source-specific rollback confirmed
restoration of production Gate5, with both AMD controller and HID
bindings. The one-shot runner printed
`PR87 COLD FIRST-HID PASS` and SHA256 verification reported
**15/15 root-owned evidence files OK**.

Cold local evidence (not uploaded to GitHub):
`/var/lib/sl4a-pr87-coldboot/`
and
`~/sl4a-hardware-runs/pr87-cold-first-hid-20261016T222247Z/`.
Full warm/s2idle/matrix/negative chronology and acceptance notes:
[acceptance document](https://github.com/avgbob/SL4A_TouchScreen/blob/experiment/sl4-std-host56-set5/docs/PR87-EXACT-HEAD-PHYSICAL-ACCEPTANCE.md).
The local kernel-boot journal, raw evdev data and detailed counter
snapshots have not been uploaded; I am reporting the real terminal
runner verdicts, **not** a separate independent replay of all raw
samples.

**Opt-out qualification caveat:** the original field verifier
returned `INCONCLUSIVE` solely because it expected sysfs
`ready=1`, but the actual driver returns `ready="ready"`.
The same archived test showed sequencer DONE=4, descriptor replies
1/1, all opt-out parameters correct, no experimental bridge
registered, and Gate5 restored. A strict read-only re-review
and corrected tests passed; original INCONCLUSIVE evidence is
retained unchanged. Runtime report `0x0c` forwarding
policy is tested separately in the compiled actual production-handler
regression, **not** inferred from a silent opt-out trial.

**Scope:** all five *defined* physical acceptance
categories now pass on this single test unit for this
exact PR head. No claims yet for spontaneous post-DONE reset/rearm,
multiple hardware samples, prolonged stress, stylus behavior,
or kernel-mainline integration. The PR can remain draft if the
maintainer wants those or other independent verification.
Would you like any particular extra failure-path test or a sanitized
subset of the recorded logs before considering the draft ready
for review?

## Internal provenance / acceptance ledger

- 2026-10-16 warm 3/3 physical result:
  `~/sl4a-hardware-runs/pr87-exact-warm3-20261016T193705Z`.
- 2026-10-16 s2idle 2/2 physical result, confirmed sleep gaps
  **158.454s and 324.521s**:
  `~/sl4a-hardware-runs/pr87-exact-s2idle2-20261016T201323Z`.
- 2026-10-16 full matrix **16/16**:
  `~/sl4a-hardware-runs/pr87-exact-matrix-20261016T213332Z`.
- 2026-10-16 default negative control, reviewed source contract:
  original verdict `INCONCLUSIVE` due to exact known verifier bug;
  no re-run claimed.
- 2026-10-16 cold first-HID new stage/trial boot IDs and
  postboot short gestures PASS, Gate5 rollback:
  `~/sl4a-hardware-runs/pr87-cold-first-hid-20261016T222247Z`
  and `/var/lib/sl4a-pr87-coldboot`.
- Independent mode4 cold first-HID result does not count toward
  exact-PR87 cold gate.
- Human operator said `COLD_PR87` following a full poweroff.
  Boot ID change is proof of a new kernel boot; the poweroff
  claim relies additionally on that explicit user confirmation.
- No raw per-frame logs, privileged journal files or root evidence
  bytes were uploaded in the pasted terminal output. Request
  sanitized checksums/logs only if upstream requires them.

**Next decision is maintainer-driven**: whether to take PR
out of draft, request independent-device sampling, or add
spontaneous-rearm validation. Physical PASS alone does not imply
upstream review/merge is complete.
