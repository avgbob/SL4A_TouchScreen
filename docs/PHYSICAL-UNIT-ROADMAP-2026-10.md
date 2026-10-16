# Physical-unit roadmap: Surface Laptop 4 AMD / MSHW0231

**Date:** 2026-10-16. **Scope:** one local SL4 AMD 13.5-inch unit,
the independent DieSchatten device, and Syax89's upstream PR #87.
This is an operating plan, not a claim of broad compatibility.

## 1. What is already done — do not rerun historical work

| Evidence | Result | Qualification |
| --- | --- | --- |
| Gate5 historical `58f0231` | cold boot 1/1, warm reload 3/3, s2idle 2/2, no unexpected resets or dropped frames | Exact historical Gate5 code only; **not** the rebased PR #87 head |
| 2026-10-16 mode 3 / bare SET5 | ordinary HID data 2461; CapImg zero | A failed warm-reload control, not universal proof SET5 cannot activate |
| 2026-10-16 restored Gate5 mode 1 | CapImg 1036, no dropped frames | Current installed positive control |
| 2026-10-16 mode 4, exact `308f914` | CapImg 749; two-finger pinch works; no additional reset or drops | One warm reload only. Later watchdog-fix driver revision is unqualified |
| DieSchatten's SL4 AMD 13.5 | live `wVersionID=0x0004`; GET6-free raw-mode activation works; GET6 reply-read attempts reset even with 1.7/17.3 ms response-to-SET5 gap | Independent raw-transport data, not a standard-transport equivalent |
| Existing DKMS + Secure Boot lifecycle | Ubuntu enrolled MOK reusable, signed driver, Gate5 boot service previously qualified | Do not rotate signing keys or reinstall merely to run an experiment |

References: [Gate5 qualification](GATE5-QUALIFICATION.md),
[mode 4 hardware note](EXPERIMENT-STD-HOST56-SET5.md),
[Syax89 PR #87](https://github.com/Syax89/SL4A_TouchScreen/pull/87),
[DieSchatten issue #85](https://github.com/Syax89/SL4A_TouchScreen/issues/85).

## 2. Mandatory sound-and-evidence policy for physical tests

**2026-10-16 usability correction:** audible *tones alone* are inadequate when
the tester's hands obstruct the laptop screen and the terminal does not scroll.
The guided runner now uses **offline synthesized SPOKEN instructions**,
requires a spoken-message preflight, and monitors the exact kernel evdev device
live. The next action starts **only after** the requested finger count,
tracking-ID continuity, movement direction, or release is actually observed;
a `sleep` duration **never counts as PASS**. It speaks positive recognition
(e.g. "Two fingers detected. Lift all fingers now.") and repeats an unsuccessful
instruction up to three times. Three unsuccessful attempts **stop and preserve
INCONCLUSIVE evidence**, rather than skip or invent a successful action.

Ubuntu speech engine prerequisite: `espeak-ng` (offline; no subscription).
If missing, `sudo apt install espeak-ng`; ordinary audio playback still uses
the existing working `paplay`, `pw-play` or `aplay`.

A second read-only evdev monitor observes the live contacts while the
existing `evtest` collector retains the bounded, checksum-protected raw
trace. A stop marker closes that collector early **after a verified session**,
instead of waiting for the worst-case timeout. The raw JSONL monitor trace,
speech/phase markers and collector artifacts are preserved for review.
**Not yet hardware-qualified:** the new audio/event gate needs its first
end-to-end test on the Surface before replacing previous evidence practices.

Our earlier September one-off tests used `printf '\a'` terminal bells,
prompt/sleep sequences and `test.markers` timestamps while running `evtest`.
Those cues were not centralized and terminal-bell output is not proof the
operator heard anything.

All **interactive** physical touch/stylus sessions now use:
- Playback test; operator must type **YES** only after hearing actual audio.
  If no sound, STOP before recording. Use USB/Bluetooth audio/headphones
  if internal Linux speakers are unavailable.
- Audible **5-4-3-2-1 GO**, distinct GO for each named gesture,
  an audible **3-2-1** near each phase end, STOP and finished tones;
  printed instructions and UTC + monotonic timestamps in `cues.tsv`.
- A real `evtest` session started before the countdown, with sysfs and
  kernel log evidence captured by the existing read-only collector.
  Root permissions are used for the collector, not desktop audio.
- New per-session directory with metadata, runner Git SHA, module
  srcversion, binary checksum when available, loaded parameter profile,
  before/after counters, event trace, logs and manifest/checksums.
- No fake PASS when audio failed, evtest did not record events, a
  collection job failed, a frame dropped, or mode/identity was wrong.

Reusable runner on the **experiment branch**:
`tools/hardware_evidence/guided_session.py`.

Available cued protocols: `full` (all quick + pinch + contacts under ONE audio preflight and ONE evidence bundle), `quick` (one finger/pinch/expand/lift),
`pinch` (same two contact IDs maintained far→close→hold→expand→lift),
`contacts` (1–5 contacts/one-finger lift/recontact),
`stylus` (hover/contact/lift), and `single --input-source direct`
(conservative standard-HID control). The established
`run_blinded_session.sh` still collects event traces and checksums;
the new runner supplies operator cues/timestamps. Host CI unit tests
need not beep because no human is making timed gestures.

**Sound-only preflight (no driver changes):**

```sh
cd ~/SL4A_TouchScreen-host56
python3 tools/hardware_evidence/guided_session.py --audio-check
```

**Guided capture when the intended module is already loaded:**

```sh
python3 tools/hardware_evidence/guided_session.py \
    --protocol full --expected-mode 4 --case mode4-warm-01-full \
    --output "$HOME/sl4a-hardware-runs/mode4-warm-01-full"
```

For temporary mode4 the wrapper also supports:
`bash tools/experiments/host56-mode4.sh audio-check`,
`bash tools/experiments/host56-mode4.sh capture quick`,
`capture full`, `capture pinch`, `capture contacts`, and `capture stylus`.
It refuses to take a mode4 capture if a different mode is loaded.

### 2026-10-16 evidence hardening

The guided runner now **requires an explicit `--expected-mode`** for a physical
test. It verifies that the running module's `srcversion` matches the
worktree's signed module, its vermagic matches the running kernel, the tracked
Git tree is clean, and the exact source SHA / signed module SHA-256 is recorded.
These are cross-checks, not a cryptographic dump of the loaded in-memory image.

After gesture capture, a run **fails** when `reset_rsp` or
`frames_dropped` increases, and MT tests also require increasing
`raw_observed` and DATA counts. No counter/identity mismatch can be
reported as a qualification PASS. A final root `SHA256SUMS.txt` covers
**every file**, including the cue markers and live-event JSONL copied after
the lower-level collector finalizes. A checksum verification failure
invalidates the evidence package.

The two-finger release gate now requires both **original tracking IDs
to be observed down in the release phase** before accepting the empty
release frame. Speech explicitly checks the held contacts first, then
says "Lift them now" without an intervening countdown that might cause
the release to occur before monitoring begins.

These safeguards are host-tested and **still require their first physical
end-to-end validation**. Existing October 16 tests with a silent timer
remain historical evidence only; they are not retroactively upgraded.

## 3. Desk work FIRST (no physical unit)

- [x] Isolated mode4 branch, exact-MSHW0231-only, production boot Gate5 unchanged.
- [x] Correct DATA-path raw-runtime watchdog arm, as Syax89 requested on PR87.
      Prevent noisy zero-duration standard-liveness callbacks.
- [x] Add mode4 feature-order + hardware gate regression checks.
- [x] Add audible reusable guided evidence runner and host tests.
- [ ] **Final CI green** on the post-fix exact branch HEAD, including whitespace,
      plain and sanitizer host tests, Ubuntu and current-kernel builds.
- [ ] Incorporate Syax89's **extracted production DATA-handler** behavioral test
      (not only source-string checks) into mode4, checking full 4.3 KiB drain,
      hid_creating, no premature HID publication, default-HID negative control,
      and raw-only watchdog arm.
- [ ] Prepare a reversible, already-enrolled-MOK-signed, **exact PR87 head**
      temporary loader. It must not replace the installed Gate5 DKMS module,
      and must prove which source/binary is actually loaded.
- [ ] Automated report summary: one row per evidence folder, verdict
      PASS/FAIL/INCONCLUSIVE, exact SHA, before/after counters, event count,
      unexpected post-DONE resets, dropped frames, audio confirmation,
      and manifest checks.
- [ ] Reconcile old qualification trackers as historical rather than
      overwriting their original results.
- [ ] Keep speculative GET6 wire/IRQ research separate from release evidence.

## 4. Physical preflight — once per machine/session

- [ ] Connect power and have independent USB/Bluetooth mouse or keyboard.
- [ ] Hear actual tones using `--audio-check` before any guided physical run.
- [ ] Check ACPI MSHW0231, kernel/BIOS, Secure Boot, signer, module file/hash,
      loaded srcversion/params and untouched boot mode-1 profile.
- [ ] Confirm `evtest` present and the MT input node is discoverable.
- [ ] Establish rollback: original `modprobe sl4a-spi-hid` must restore Gate5
      mode1 after a temporary module is removed.
- [ ] Use a unique evidence folder; no overwrites or silent failed runs.

## 5. Mode4 hardware batch (no-GET6 path)

**Pin post-watchdog-fix exact source SHA before testing**; old
`308f914` pinch PASS is historical, not a result for this new binary.

| ID | Test | Physical work / evidence |
| --- | --- | --- |
| M4-1 | Warm reload #1 | Load signed temporary mode4; run **one `full` audible capture** (quick + pinch + contacts under one preflight/evtest file); check CapImg, IDs and releases |
| M4-2 | Warm reload #2 | One reload + short audible `quick` |
| M4-3 | Warm reload #3 | One reload + short audible `quick` |
| M4-4 | s2idle #1 (>=30s) | Resume + `quick`, fresh descriptors and CapImg |
| M4-5 | s2idle #2 (>=30s) | Resume + `quick`, no unexpected post-DONE reset |
| M4-6 | True cold boot | **Blocked** until a reviewed *temporary persistent mode4 opt-in* with automatic safe rollback exists; a reboot of current temporary .ko would load Gate5, not mode4 |
| M4-7 | Rollback control | Restore the installed Gate5 `mode1`, verify CapImg/gestures and unchanged boot config |

Do not rerun the complete `contacts` protocol for every reload; only
repeat a long gesture suite after changing the tested driver SHA or
investigating a specific input-quality regression.

## 6. Upstream PR #87 — separate exact-build acceptance

**PR:** https://github.com/Syax89/SL4A_TouchScreen/pull/87

At roadmap creation, draft head was `458e6844fb9cb9916649624ac8ad5864bb402317`.
Refresh and PIN it immediately before testing. PR87 implements Gate5
write-only GET6→~5ms→SET5, **not** mode4 host-0x56 activation.

Syax89's requested exact-head acceptance evidence:
- True cold power-on, touchscreen binding, real MT gestures.
- Three repeated warm reloads, with a short `quick` input test after each.
- Two s2idle cycles with touch after each.
- Actual two-finger pinch and tracking-ID continuity.
- Zero dropped frames and no unexpected post-DONE resets after activation.
- Conservative default-standard (`raw_input_beta=0`,
  `std_raw_transition=0`) **direct** single-finger control; no accidental
  mode1/bridge activation.
- No fake standard-liveness logging, no early-DATA body abandonment,
  raw transport behavior retained, and host/kernel CI confirmed.

Use the same **single `full` run then short `quick` lifecycle runs**,
acoustic/trace protocols and evidence indexing as mode4, but build and
load PR87 **from its own source**. A successful
mode4 test cannot be counted as PR87 physical acceptance.

## 7. Quality / release matrix AFTER upstream acceptance

- [ ] Pen hover, contact, lift; pen/finger coexistence and palm rejection.
- [ ] 1–5 contacts, same-ID pinch continuity, crossing/occlusion,
      one finger lifted while another remains, rapid recontact and phantom-ID check.
- [ ] 30-minute mixed touch/pen soak and clean kernel logs; audible
      start/end and periodic operator prompts when human interaction is expected.
- [ ] Longer lid/s2idle cycles; spontaneous reset recovery only if actually seen.
- [ ] MSHW0230 and MSHW0162 require their own hardware, not extrapolation.
- [ ] E1 blinded crossover per [HARDWARE_VALIDATION.md](HARDWARE_VALIDATION.md).
      None of today's findings constitute E1 release qualification.

## 8. Per-run pass/fail contract

Record exact: test label; start/end UTC; Git SHA/dirty tree; module path,
signed SHA-256, signer, secure boot; kernel/BIOS; loaded modes/params;
persistent config; audio confirmed; cue markers; evtest device/event trace;
initial/final `ready`, `seq_state`, `protocol_stats`; reset and dropped deltas;
gesture/release observations; suspend/reload/cold flag; collector manifest,
checksum; verdict and notes.

For MT bridge **PASS** requires CapImg `0x0c`, increasing `raw_observed`,
real MT events and working gestures, correct input release, no added
`frames_dropped`, and no unexpected reset after DONE. One reset response
during startup is expected. For conservative standard control, require
ordinary single-touch events; **do not require CapImg**.

These operator-guided cases are **unblinded engineering runs**, even though
they reuse the existing read-only collector with the `p1` artifact label.
They must never be misrepresented as the distinct E1 blinded crossover.

Every failed/inconclusive run is retained. A console claim that "pinch
worked" without a timestamped gesture trace is useful operator evidence,
but does not replace exact-head lifecycle qualification.

## 9. Housekeeping / communication

- Keep local raw evtest data, cue files, manifests and logs in immutable
  folders with an `evidence-index.tsv` summary; do not flood GitHub issues
  with bulk machine logs or sensitive unrelated input.
- Post one summarized exact-SHA acceptance report to Syax89's PR #87
  **only when its acceptance batch is complete**.
- Post another DieSchatten follow-up to #85 only for a new material
  compatibility result; the initial cross-device mode4 result is already posted.
- No new MOK key, BIOS change, firmware flash, or installer-default switch
  during controlled comparisons. Keep mode1 as recovery anchor.

**Next physical action:** confirm audio works on the Surface, then prepare
and qualify the **post-watchdog-fix mode4 revision** starting with a warm
reload and the audible quick+pinch session. PR87 exact-head hardware
qualification follows once its own safe loader is prepared.
