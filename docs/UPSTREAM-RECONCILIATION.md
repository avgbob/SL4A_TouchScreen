# Surface Laptop AMD Touchscreen
## Upstream Reconciliation, Technical Comparison, and Contribution Plan

- **Status:** Draft for technical review
- **Prepared:** October 15, 2026
- **Repositories:** [Syax89/SL4A_TouchScreen](https://github.com/Syax89/SL4A_TouchScreen) (upstream) · [avgbob/SL4A_TouchScreen](https://github.com/avgbob/SL4A_TouchScreen) (Gate5 fork)
- **Other contributors reviewed:** DieSchatten, OctoDevStudios, cristinagp
**Scope:** Current default-branch source comparison, merged PRs #84 and #86, and existing hardware-qualification records. No new builds or hardware tests were performed for this document.

---

## 1. Purpose and operating principles

The aim is to reconcile useful upstream changes with a field-qualified Gate5 implementation, make independently useful fixes available to upstream, and avoid duplicating work or turning others' issue trackers into fork promotion channels.

The fork is **not** positioned as a replacement for Syax89's project. Syax89's work established the AMD SPI/HID-over-SPI transport and CapImg/raw multitouch foundation. The fork's key distinction is an integration path that keeps standard HID discovery and registration while activating CapImg multitouch and processing touch data in-kernel. Both approaches may provide working touch, but their initialization and lifecycle contracts differ.

Three rules govern the work:

1. **Preserve the proven baseline.** Do not replace the known-working Gate5 standard installation profile with an unqualified handshake or merge.
2. **Keep claims tied to evidence.** A test on one panel, OS, kernel, or firmware version does not qualify other variants.
3. **Contribute narrow fixes upstream.** Each upstream pull request should be independently understandable, testable, and useful without requiring adoption of the entire Gate5 architecture.

## 2. Source state at audit

The following are commit-graph observations, not quality ratings:

| Repository / branch | Relative to current upstream `main` | Interpretation |
| --- | --- | --- |
| `Syax89/SL4A_TouchScreen:main` | Baseline | Includes newer upstream changes, including PRs #84 and #86. |
| `avgbob/SL4A_TouchScreen:main` | **227 ahead, 8 behind** | Extensive independently developed code and tests; upstream changes still need reconciliation. |
| `DieSchatten/SL4A_TouchScreen:main` | 0 ahead, 8 behind | His Windows-order handshake and opcode work was merged as upstream PR #86. |
| `cristinagp/SL4A_TouchScreen:main` | 0 ahead, 276 behind | A historical upstream snapshot on the default branch; this says nothing conclusive about unexamined branches or local work. |

**Already merged upstream:**

- [PR #84](https://github.com/Syax89/SL4A_TouchScreen/pull/84), by OctoDevStudios: adds `MSHW0230` matching and documents real `045e:0c18` touch behavior.
- [PR #86](https://github.com/Syax89/SL4A_TouchScreen/pull/86), by DieSchatten: adds an opt-in Windows-style heatmap enable sequence and restricts AMD controller opcodes to `0x02` and `0x0B`.

These are **not missing upstream features**. Incorporating compatible portions into the fork is an integration task; rediscovering or reimplementing them as if they were new is not a priority.

## 3. Architecture comparison

| Area | Upstream as reviewed | Gate5 fork as reviewed | Evidence / implication |
| --- | --- | --- | --- |
| AMD SPI and HID-over-SPI | Implements controller binding, descriptor discovery, standard input and raw-mode infrastructure | Retains and extends shared foundation | Credit upstream for foundational work. |
| Normal HID registration | Implemented | Preserved throughout Gate5 initialization | Supports keeping descriptor-created HID interfaces registered, **not** proof of pen functionality. |
| CapImg multitouch | Beta raw-mode pipeline | Standard transport plus CapImg data and in-kernel tracker | Distinct integration path; requires independent compatibility testing. |
| Heatmap activation | Existing sequences and optional `win_handshake` from PR #86 | Write GET_FEATURE 6 without synchronous response-body read; wait 4.5–5.5 ms; SET_FEATURE 5 = 1 | Both have positive *different-device* hardware results; neither establishes cross-panel compatibility. |
| Early DATA during HID registration | IRQ DATA handler returns when `hid_creating` is true | Drains/processes the body even during HID creation, but suppresses HID report publication until ready | Candidate lifecycle bug fix for upstream, subject to focused review. |
| Multitouch tracking | Established heatmap decoder and touch tracker | Additional contact-continuity/coalescing experiments and tests | Differences are real; comparative input-quality superiority is **not yet established**. |
| Hardware identities | `MSHW0231`, `MSHW0162`, and merged `MSHW0230` match in code | `MSHW0231` field-qualified Gate5; `MSHW0162` conservative standard profile | Do not silently enable Gate5 for `MSHW0230`. |
| GET_FEATURE suppression | In standard mode, opt-in/default upstream guard blocks **report 6 only** | When `skip_std_getfeat=1`, current guard blocks **all feature report reads** | Consider narrowing the fork guard and validating Gate5's internal GET6 write. |
| Controller opcode safety | Explicit `0x02`/`0x0B` allowlist | No equivalent explicit early allowlist found in `amd_spi_exec_segment()` | High-value, small safety integration candidate. |
| Installer, Secure Boot, diagnostics | Installer and DKMS support | Field-tested Ubuntu MOK reuse/sign/reboot/automatic activation; expanded diagnostics | Valuable lifecycle evidence for one hardware/kernel configuration. |

### 3.1 Gate5: qualified activation contract

The documented installation profile on the tested SL4 AMD `MSHW0231 / 045e:0c19 / AMDI0060` machine is:

```text
ACPI _PS0 -> _RST
  -> RESET_RSP -> DEVICE_DESC -> 936-byte report descriptor
  -> register normal HID device
  -> WRITE GET_FEATURE(6), do not synchronously read its body
  -> wait ~4.5–5.5 ms
  -> SET_FEATURE(5) = 1
  -> DONE -> CapImg 0x0c frames
  -> in-kernel multitouch tracker -> MSHW0231 Touchscreen
```

The relevant pinned profile includes `raw_mode=N`, `raw_input_beta=Y`, `wire_double_opcode=1`, `skip_std_getfeat=1`, and `std_raw_transition=1`. Its original qualification is recorded in [docs/GATE5-QUALIFICATION.md](https://github.com/avgbob/SL4A_TouchScreen/blob/main/docs/GATE5-QUALIFICATION.md).

**Hardware outcomes on that one unit:** cold boot plus touch PASS; warm module reload plus touch 3/3 PASS; s2idle resume plus touch 2/2 PASS; Secure Boot with the existing enrolled Ubuntu DKMS MOK PASS; zero observed frame drops and unexpected post-DONE resets in those captures. These are scoped lifecycle findings, not cross-panel or comprehensive input-quality certification.

### 3.2 DieSchatten's different working activation path

His [PR #86](https://github.com/Syax89/SL4A_TouchScreen/pull/86) uses an opt-in raw-mode Windows-order sequence. The actual hardware-success configuration on a **13.5-inch `MSHW0231` Sharp-panel SL4** was:

```text
SET_FEATURE(0x56) = FF FF FF FF FF FF
  -> wait ~37–40 ms
  -> SET_FEATURE(5) = 1, with win_get6=0
  -> CapImg multitouch
```

On that same machine, including GET_FEATURE(6) and reading its reply before SET5 produced a reset. That does **not** prove Gate5's *write-only GET6* would reset that panel. Nor does Gate5's success prove it would work there. These are three distinct transaction contracts that must not be conflated.

## 4. Concrete reconciliation findings

### Finding A — early DATA-frame drain race (candidate upstream contribution)

**Observed code difference:** In upstream `seq_handle_data()`, a type-1 DATA report can return while `hid_creating` is true. In the fork, the gate allows body processing while HID creation is underway, while keeping `hid_input_report()` suppressed until registration is complete.

**Failure mechanism identified in Gate5 testing:** A DATA header may be consumed immediately after SET5 while `hid_add_device()` is still running. If the handler returns without draining its approximately 4.3 KB body, the pending frame can corrupt the next transaction's expectations and the tested unit may reset about half a second later. The Gate5 correction was associated with repeatable warm reloads.

**Important limitation:** This failure is field-demonstrated on the Gate5 path. Upstream's default raw-mode or standard-mode timing may differ. Before proposing an upstream patch, confirm that the change cannot accidentally publish incomplete HID data, dereference an unready input device, or interfere with packet ownership. Inspect the poller path separately; an IRQ fix does not automatically fix all paths.

**Recommended upstream PR:** Small, localized DATA-body-drain correction, with a host regression test for `hid_creating=true`, one complete DATA frame, correct drain, no premature HID publication, and successful handling of the next frame. Include the captured failure/recovery evidence. Do **not** bundle Gate5 activation or tracker rewrites with this PR.

### Finding B — opcode allowlist (integrate from upstream)

PR #86 places an early guard in `amd_spi_exec_segment()`:

```c
if (opcode != 0x02 && opcode != 0x0B)
    return -EINVAL;
```

This blocks unexpected opcodes before touching controller registers. Because the controller also has BIOS-flash responsibilities, this is a sensible defensive boundary. The fork's version of that function does not currently contain the same explicit allowlist.

**Action:** Port the smallest equivalent guard into the fork on an integration branch. Test both legitimate opcodes, invalid opcode rejection, continued segmented read behavior, and normal Gate5 discovery/input. Confirm diagnostic paths do not depend on additional controller opcodes. This is **not** a new upstream PR: it is already merged there.

### Finding C — limit standard GET_FEATURE suppression to report 6

The fork's current standard-mode suppression condition blocks all `HID_FEATURE_REPORT` reads whenever `skip_std_getfeat=1`. Upstream now blocks only `reportnum == 6`, leaving other feature reports available.

**Action:** Evaluate applying the narrower guard to the fork while **keeping the Gate5 sequencer's internal write-only GET6 transaction intact**. Regression-test externally requested GET6 suppression; other feature IDs; input-report behavior; Gate5 activation; cold boot, reload, and resume. If a different feature ID causes an actual problem, document that independently rather than retaining an unexplained blanket ban.

### Finding D — `MSHW0230` support is merged upstream but not qualified in Gate5

PR #84 adds a second SL4 AMD touchscreen identity, reported as `MSHW0230 / 045e:0c18`, with working direct finger touch on Debian 13 / a surface kernel. Do **not** treat `MSHW0230` and `MSHW0231` as an infallible 13.5-inch/15-inch size mapping: DieSchatten's 13.5-inch model reports `MSHW0231`.

**Action:** Keep `MSHW0230` out of the Gate5 production profile until hardware identification, grid/descriptor geometry, transport initialization, and input behavior are independently qualified. A separate read-only detection path or experimental opt-in can be considered after code review.

### Finding E — report `0x56` and historical frame constants

DieSchatten's analysis identified report `0x56` as a host Bluetooth-address payload, with `FF:FF:FF:FF:FF:FF` a neutral value for his handshake. The fork's comments already distinguish historical captures from universal protocol constants and recognize the `0C EE 5B` tail as non-semantic capture residue.

**Action:** Audit diagnostic/legacy `0x56` builders and their call sites. Avoid replaying a captured host address as though it were a universal device key. Preserve historical fixtures for test reproducibility, but isolate them from live defaults. This is a separate cleanup—not part of the first two safety fixes.

## 5. Validation gaps and test design

| Test / device | Gate5 evidence | What remains |
| --- | --- | --- |
| `MSHW0231` cold boot and touch | PASS on one unit | At least one independent unit, firmware and distro profile. |
| Warm reload | 3/3 PASS on one unit | Repeat across independent devices and after safety integrations. |
| s2idle resume | 2/2 PASS on one unit | Repeat on new kernel/firmware combinations. |
| Ubuntu Secure Boot DKMS / MOK | PASS on one unit | Zorin, Fedora, Debian, and other signing environments unqualified. |
| `MSHW0230 / 045e:0c18` | No Gate5 evidence | Detection, raw frame layout, activation and tracking validation. |
| `MSHW0162` SL3 AMD | Conservative standard HID profile; Gate5 not qualified | Do not extrapolate Gate5. |
| 1–5 finger tracking, crossing, close pinch, palm rejection | Partial targeted evidence | Formal E1 input-quality testing remains open. |
| Pen, hover, mixed pen and touch | Unqualified | Keep explicit unsupported/unverified claim. |
| Gate5 on DieSchatten's 13.5-inch Sharp `MSHW0231` | Not tested | Compare exact write-only-G6 and SET5-only sequence under controlled recovery safeguards. |

For any independent comparison, capture at minimum: ACPI ID, HID VID/PID, DMI model, panel EDID if available, UEFI version, distro/kernel, exact source SHA, module parameters, boot type, sequencer transactions, IRQ/DATA counters, reset counters, and sample input events. Do not require participants to install a second experimental driver without a recovery path. A read-only preflight should be the first step.

**Minimal A/B matrix on suitably prepared hardware:** (A) existing working upstream profile; (B) Gate5 write-only GET6 → ~5 ms → SET5; (C) no-GET6 SET5 path, where separately safe and supported. Test cold start, safe reload, resume, first-contact latency, frame draining and resets. Change one transaction-sequence dimension per run. If a controller resets unexpectedly, stop and recover rather than retrying blindly.

## 6. Implementation plan and release gates

### Stage 0 — freeze the known-good branch

- Preserve the exact Gate5-qualified commit and its evidence, module options and recovery instructions.
- Create a separate integration branch from that point. Do not modify the proven baseline during review.
- Record an upstream merge-base and precise imported upstream commit IDs.

**Gate:** Baseline replay and host tests remain reproducible; rollback remains possible.

### Stage 1 — small upstream-derived hardening changes

- Port opcode allowlist as an isolated change.
- Narrow standard feature-read suppression to report 6 as a separate change.
- Add unit/host assertions for both behavioral contracts.
- Run host tests and module builds against available supported kernel headers; perform physical Gate5 cold/reload/resume smoke tests before promoting the integration branch.

**Gate:** No changes to the qualified Gate5 handshake ordering or normal CapImg behavior; safety checks pass; physical requalification completed before release claims.

### Stage 2 — offer one focused upstream race-fix PR

- Develop the `hid_creating` DATA-drain fix against current upstream, not by submitting the entire fork.
- Reproduce the issue with a host test or a narrowly instrumented upstream variant if feasible.
- Guard against early report publication and evaluate IRQ/poller paths separately.
- Explain the user-visible failure, code-level cause, regression coverage, and compatibility assumptions in the PR.

**Gate:** Syax89 can review or decline the patch on its own merits. Do not conflate a review or merge decision with the status of the Gate5 fork.

### Stage 3 — optional cross-panel handshake study

- If DieSchatten or another owner volunteers, compare *their current working configuration* against a carefully controlled Gate5 experiment.
- Do not assume that an issue being closed means any developer still needs a fix.
- Keep experimental activation out of standard profiles until the independent test matrix supports it.

**Gate:** At least two physical units with complete provenance and repeatable cold/reload/resume results for any broader compatibility claim.

### Stage 4 — user-facing input-quality qualification

- Continue existing E1 work: 1–5 contacts, crossings, close-contact continuity, rapid lift/reacquisition, palm, pen, and longer mixed-input sessions.
- Publish failures and inconclusive results as well as passes.

**Gate:** Update compatibility language only for the behaviors the evidence actually supports.

## 7. Collaboration and GitHub etiquette

The fork will primarily organize its test matrix, issues, and invitations in [its own repository](https://github.com/avgbob/SL4A_TouchScreen). Discussion on upstream or linux-surface threads should remain directly useful to those threads:

- Credit Syax89, DieSchatten, OctoDevStudios and other contributors for their specific work.
- Avoid repeating general fork announcements in closed issues or threads where the problem has been resolved.
- Use focused upstream PRs for standalone correctness fixes; link to the fork only where necessary to reproduce evidence.
- Treat independent developers as peers comparing findings, not users to recruit away from an existing solution.
- Reuse already established contacts instead of broadening outreach without a technical reason.

**Current outreach status:** avgbob has already commented to Syax89, DieSchatten, Redpizzi and the broad linux-surface #902 audience. No immediate second-round announcement is recommended.

## 8. Immediate decision register

| Decision | Recommendation | Why |
| --- | --- | --- |
| Merge upstream `main` wholesale into Gate5 `main` | **No** | Eight behind commits touch sensitive initialization/controller paths and require scoped validation. |
| Port opcode allowlist | **Yes, integration branch** | Narrowly scoped controller hardening. |
| Narrow GET_FEATURE suppression | **Yes, integration branch with Gate5 regression tests** | Better HID feature compatibility while protecting against report 6. |
| Submit early-DATA drain PR upstream | **Prepare focused PR** | Concrete, independently useful lifecycle correction; exact upstream applicability must be verified. |
| Enable Gate5 by default on `MSHW0230` | **No** | Not qualified on that hardware ID. |
| Replace Gate5 with `win_handshake` | **No** | Distinct, un-compared hardware contracts. |
| Advertise pen support | **No** | A HID pen node is not validated stylus input. |
| Restart broad outreach | **No** | Current technical contacts and community announcements are sufficient. |

## 9. References

- [Upstream repository](https://github.com/Syax89/SL4A_TouchScreen)
- [Gate5 fork](https://github.com/avgbob/SL4A_TouchScreen)
- [Gate5 qualification report](https://github.com/avgbob/SL4A_TouchScreen/blob/main/docs/GATE5-QUALIFICATION.md)
- [Hardware testing request](https://github.com/avgbob/SL4A_TouchScreen/issues/9)
- [DieSchatten handshake PR #86](https://github.com/Syax89/SL4A_TouchScreen/pull/86)
- [OctoDevStudios hardware PR #84](https://github.com/Syax89/SL4A_TouchScreen/pull/84)
- [Syax89 issue #4 — GET_FEATURE report 6 investigation](https://github.com/Syax89/SL4A_TouchScreen/issues/4)
- [DieSchatten issue #85 — protocol evidence](https://github.com/Syax89/SL4A_TouchScreen/issues/85)
- [linux-surface SL4 AMD issue #902](https://github.com/linux-surface/linux-surface/issues/902)

---

**Review status:** Proposed plan, not executed. No repository branches, commits, issues, or pull requests were created by this document. All compatibility conclusions remain constrained to the cited source and hardware evidence.