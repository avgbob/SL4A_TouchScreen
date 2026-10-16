# Syax89 PR #87 — exact-head hardware acceptance campaign

**Current status (2026-10-16):** **exact-head PR #87 warm
3/3 PASS, genuine s2idle post-wake 2/2 PASS, and full physical
16-phase gesture matrix PASS** on one physical MSHW0231,
kernel `7.0.0-34-generic`. The experimental signed PR `.ko` was
verified and production Gate5 restored by the respective runners.
**Real exact-PR87 cold first-HID load and default-standard
negative/opt-out control are STILL PENDING.** The full matrix is
a warm module activation, not a cold boot or default-standard test.
Earlier incomplete warm/harness, postwake voice-confirmation attempts,
and the 425.775ms evdev release-gap outlier are retained as separate
historical evidence. The old narration occasionally spoke a stale
one-contact cue; a subsequent harness revision suppressed that stale
speech without changing PR87 source or the zero-contact PASS gate.
PR: https://github.com/Syax89/SL4A_TouchScreen/pull/87
Exact pinned test driver revision:
`18f0fe79623e6de4fdf1ae493f82a7048397386a`.
Expected physical target: Surface Laptop 4 AMD, MSHW0231,
Ubuntu kernel `7.0.0-34-generic`, Secure Boot enabled with existing
enrolled Ubuntu DKMS MOK. Known-working, installed boot fallback:
Gate5 `sl4a-touch/1.7.0` mode1, production driver source identity
`3326E559A916BE5CB52375D` from preceding hardware diagnosis.

### First analyzer field run: zero measurements — label mismatch FIXED

The user ran the first analyzer on **all five** qualified PR87
quick captures plus the independent mode4 quick capture. It
printed `Analyzed 0 release-phase result(s)`. This is an
**analyzer bug**, not a release-time result: that first analyzer
only recognized phase names `quick-expand`/`quick-lift` or
`pinch-expand`/`pinch-lift`. The actual
`guided_session.PROTOCOLS["quick"]` and
`PROTOCOLS["pinch"]` use unprefixed `expand` and `lift`,
as confirmed directly in the generator source. Thus an
otherwise valid capture produced no matching markers.

The correction recognizes **real `expand` / `lift`** and
keeps prefixed aliases only for older/alternate captures;
discovery now starts from `operator/cues.tsv` even when the
evdev JSONL is missing. An empty root prints
`NO_CAPTURE_FOUND`, unknown pass labels print
`NO_MATCHING_RELEASE_PHASE` with recorded label names,
and missing/unreadable evdev is `UNREADABLE`; these all
produce **nonzero** process exit status, not silent success.
Regression tests use fixtures shaped after the **real
unprefixed** recorder, plus malformed/empty-label cases.
The analysis remains read-only. **Actual release gaps are still
not determined** until the corrected tool is run against the
existing local captures.

## Default-standard physical negative control: prepared, NOT yet run

Use `bash tools/experiments/pr87-exact-head.sh standard-negative`
on the physical Surface to test the *same pinned PR87 source*
`18f0fe79623e6de4fdf1ae493f82a7048397386a` with
`raw_mode=N raw_input_beta=N std_raw_transition=0`. The distinct
`NEGATIVE` confirmation precedes signing/loading. The script temporarily
unloads Gate5, loads the exact signed PR87 module in opt-out mode,
checks source/parameter/binding identity, and runs a read-only sysfs
verifier. That verifier requires ordinary standard HID descriptor
discovery (`ready=1`, `device_desc>0`, `rpt_desc>0`) and **no**
registered `MSHW0231 Touchscreen` heatmap-backed input device.
It is intentionally **not** a multitouch gesture PASS test:
the experimental MT bridge is supposed to be absent in opt-out mode.
The harness restores production Gate5 using its existing EXIT/interrupt
rollback and saves local provenance/counter snapshots/checksums without
touch coordinates or event streams.

The passive `raw_observed` counter can legitimately be nonzero in
ordinary mode, so the verifier never uses it as proof of publishing.
Similarly, a silent standard-mode touchscreen cannot establish whether
Report ID `0x0c` was withheld by the HID dispatcher. Actual policy
is separately tested by the compiled, production-handler host tests.
This physical control proves **opt-out parameter and device-registration
behavior**, not an exhaustive byte-for-byte comparison of every HID path.

**Status: runner prepared and host-tested; physical control PENDING.**
Never mark this as physical PASS from CI alone.

## 2026-10-16 21:33 UTC: exact-head full physical matrix **16/16 PASS**

The operator ran `bash tools/experiments/pr87-exact-head.sh full-matrix`
on the physical SL4 AMD MSHW0231, kernel `7.0.0-34-generic`.
Local evidence:
`~/sl4a-hardware-runs/pr87-exact-matrix-20261016T213332Z`,
capture `cycle-matrix-full`. This report is based on the shared
terminal transcript and runner verdict; the local per-frame raw
evidence and individual counter values have not been uploaded
or independently audited.

The one-shot runner confirmed installed working Gate5
`srcversion=3326E559A916BE5CB52375D` before testing.
It fetched/pinned exact PR87 source
`18f0fe79623e6de4fdf1ae493f82a7048397386a`,
built and signed the experimental HID (SHA256
`61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`,
`srcversion=65F0D14FBDFB5E84748373E`), and loaded
that exact PR module successfully.

The spoken/event-gated full suite reported PASS for **all 16**
phases: quick one/pinch/expand/lift (4), connected
pinch far/close/hold/expand/lift (5), and contact-count
one/two/three/four/five plus one-lift and recontact (7).
It exercised 1–5 detected fingers, continuous original-ID
tracking, staggered release and recontact. Importantly,
the previously recurring stale spoken “One original finger remains”
prompt **did not appear** during this run using the revised
nonblocking narration harness; the transcript still does not
physically measure finger-off latency.

The capture printed:
`All live gesture gates, source identity, resets, frame drops and
evidence checksums passed for this session.`
Afterward the runner reported
`RESTORE PASS: working production Gate5 bound`,
validated the four reported top-level checksum entries, then
`PR87 FULL MATRIX PASS; source pinned, signed module stable,
Gate5 restored.` Thus the full-matrix acceptance category is
**COMPLETE** for this exact source and one unit.

The first attempted matrix command in the same transcript was
stopped before driver loading by failed sudo authentication.
A second attempt typed lowercase `matrix` and was safely
cancelled before touching the driver. Neither counts as a
physical test failure. The final `MATRIX` attempt completed PASS.

**Still unqualified:** exact PR87 cold first-HID
power-on activation and physical default-standard
negative/opt-out behavior. The GET6-free mode4 cold-boot
success is a **different driver revision/activation protocol**,
and cannot substitute for the PR87-specific cold trial.

## 2026-10-16: nonblocking reactive voice/event-loop hardening

Experimental *harness-only* change (not part of Syax89 PR #87
and not a production touchscreen driver modification): progress
announcements run on one serialized background speech worker while
the event gate immediately consumes all queued evdev frames.
The worker is joined between gesture phases to avoid overlapping
spoken instructions; the existing timestamped `gesture-progress`
markers, zero-contact completion, ID-reappearance checks and
original-pair continuity remain mandatory. Feedback not yet begun
is cancelled after a gesture passes, and a bounded narration
backlog or a speech-worker exception makes the run inconclusive.

A synthetic slow-voice regression injects two tracked finger frames
while progress speech is deliberately delayed and requires the
pinch PASS event timestamp to precede voice completion. This checks
event-loop independence, not physical touchscreen release latency.
No hardware results or prior acceptance statuses change.

## 2026-10-16 21:06 UTC: PR87 warm-2 425ms gap versus voice-cue timing **RESOLVED AS TWO SEPARATE OBSERVATIONS**

The physical operator ran
`tools/hardware_evidence/release_outlier_detail.py` on the
already saved `pr87-exact-warm3-20261016T193705Z/cycle-2-quick`
evdev frames and spoken-cue timestamps. No module was touched.

All times below are in the Python observer's **monotonic** domain,
relative to when the first original tracking ID disappeared;
the independent kernel evdev event-to-event gap was
**425.775 ms**, agreeing with Python observer's **425.745 ms**.

| Observed stage | Relative to first released finger |
| --- | ---: |
| `Lift both fingers now` speech queued/started | −1300.443 ms |
| First original ID released | 0.000 ms |
| Both original IDs gone | +425.745 ms |
| `lift` phase marked begin after blocking speech | +961.236 ms |
| `One original finger remains` progress cue queued | +961.923 ms |
| Release PASS cue | +4802.244 ms |

**Key causal discovery:** The stale intermediate **progress cue
was logged 536.178 ms AFTER the final zero-contact evdev frame**.
The transcript and source show `guided_session.Audio.speak()`
runs synchronously, while the input-event monitor thread continues
recording frames. The runner replayed the queued `2→1` event
AFTER the `2→1→0` physical event chain was already emitted;
the old version spoke the stale message and held up the PASS
cue a further **3840.321ms** (progress cue to PASS).
The actual zero-contact frame existed well before the narrated
“one remains”. The new harness suppresses **only this
misleading spoken instruction** while preserving its timestamped
evdev evidence and strict original-ID, zero-contact acceptance.

**Correction of preceding hypothesis:** The narrator's
`One original finger remains` line **cannot have CAUSED this
425.775ms kernel first-to-last release interval**, because
that cue was not even queued until more than half a second
AFTER both releases. The original `Lift both fingers now`
instruction started over a second *before* the first release.
The **actual reason** Linux saw 425.775ms between first/second
releases is **not determined** without a physical finger-off
reference. It could reflect non-simultaneous human action,
device/firmware processing, or driver delay. Do not attribute
this gap to speech or a driver fault from these data alone.

**Engineering disposition:** stale voice-reporting behavior
CONFIRMED in the old test harness; actual second-contact
release evdev-event timing OUTLIER OBSERVED but driver
latency NOT QUALIFIED. The real PR87 module still passed
warm3 and s2idle2 under previously defined touch-validity
criteria, and Gate5 remains installed. No hardware retest
is needed to establish the narration timing error.
Future latency qualification, if needed, should use a tone
and an externally measured physical release instant
rather than synchronous TTS progress messages.

## 2026-10-16 20:56 UTC: physical saved evdev release interval screening COMPLETE

The corrected offline analyzer was rerun on the Surface's real,
previously recorded quick gesture files (three PR87 warm, two PR87
post-s2idle, one independent GET6-free mode4 cold boot) and
successfully analyzed **all six** sessions. Report:
`~/sl4a-release-timing-report.txt`.

| Run | Kernel evdev delta, first contact release → last contact release |
| --- | ---: |
| PR87 warm 1 | 10.092 ms |
| **PR87 warm 2** | **425.775 ms — single REVIEW OUTLIER** |
| PR87 warm 3 | 9.813 ms |
| PR87 after s2idle 1 | 29.440 ms |
| PR87 after s2idle 2 | 19.531 ms |
| GET6-free mode4 cold | 28.981 ms |

**Every recording** observed an original-ID pair → one original ID
→ no contacts (`SEQUENTIAL_RELEASE`). The basic batch analyzer
did not report a new/reappeared ID. Six-sample
**median=24.256 ms, max=425.775 ms**; the nearest-rank
95th percentile is also 425.775 ms due to tiny sample count,
not a reliable population tail estimate. The 100ms review threshold
is arbitrary **screening guidance**, not driver timing specification.

**Do not dismiss the single 425.775ms PR87 warm-2 outlier.**
Crucially, the *then-current voice test* synchronously spoke
`One original finger remains. Lift it now.` after the first
original-ID release. This spoken direction may have encouraged
the human operator to lift the second finger later in that
session. The recorded interval alone **cannot separate physical
operator action, firmware release behavior, or driver delay**.

Added `tools/hardware_evidence/release_outlier_detail.py` to
cross-reference the exact saved warm-2 evdev frame timestamps
with the Python `gesture-progress` cue timestamps for that
same capture. It reports cue timing relative to the
one-contact and zero-contact events without exposing
touch coordinates or relying on wall-clock time. It uses
kernel event timestamps only for *event-to-event* intervals;
Python monotonic observer and cue timestamps are compared
only within their own clock domain. The voice progress
cue is generated **before** speech playback, so even this
comparison cannot prove when fingers physically left
the glass or whether the user waited for a voice instruction.
It may, however, show whether the test program processed
or narrated a now-stale finger state. No hardware retest
or module mutation is required.

On the Surface, after updating the *harness* worktree:

```bash
python3 tools/hardware_evidence/release_outlier_detail.py \
  ~/sl4a-hardware-runs/pr87-exact-warm3-20261016T193705Z/cycle-2-quick
```

**Next engineering decision:** inspect that brief timeline
before suggesting driver contact-retention changes or
claiming pathological release latency. If still ambiguous,
use a controlled touch stimulus plus independent physical
timing, rather than a spoken intermediate instruction.

## Automated, offline release-latency screening (existing physical captures)

Following the operator's repeated report of “One original finger remains”
during **every** two-finger test, added a read-only **batch**
analyzer at `tools/hardware_evidence/release_timing_report.py`.
This augments (does not replace) the older, single-session
`audit_release.py`.

After fetching this harness branch on the physical Surface, run:

```bash
cd ~/SL4A_TouchScreen-host56
python3 tools/hardware_evidence/release_timing_report.py \
  ~/sl4a-hardware-runs/pr87-exact-warm3-20261016T193705Z \
  ~/sl4a-hardware-runs/pr87-exact-s2idle2-20261016T201323Z \
  ~/sl4a-hardware-runs/mode4-quick-20261016T185822Z
```

It reads only saved `operator/{cues.tsv,live-evdev.jsonl}`, selects
verified original two-finger IDs at expansion PASS, and follows
`2→1→0` (or direct `2→0`) through each gated release verdict.
It measures the **kernel evdev SYN_REPORT first-to-last release
interval** where both timestamps exist, otherwise separately
labels the independent observer `monotonic` measurement. It
reports contact-ID replacements/reappearance and missing/incomplete
contact-release evidence **without silently claiming PASS**. It
prints median, nearest-rank p95 and max across measurable
sequential releases, plus an **arbitrary screening** flag for
reported gaps ≥100ms (not a hardware specification or verified
failure boundary). No raw coordinates or touch trace lines
are printed; nothing requires sudo, evdev permissions or module
reload. CI uses synthetic saved guided-session fixtures and
verifies kernel vs observer timing, direct/sequential releases,
tracking anomalies, missing zero-contact result and timestamp
errors.

**Crucial limitation:** recorded timestamps establish when the
Linux evdev pipeline reported each release, not the physical
instant the fingertip left the display. Only an independent
physical reference (e.g., synchronized high-speed video or a
sensor trigger) and/or driver-internal timestamping can locate
true touch-to-event delay. This report's **physical outcomes
remain PENDING until run against the user's saved traces**.
Do not substitute synthetic CI results for field evidence.
If a recurrent >100ms gap or replacement ID is observed,
investigate the exact trace and compare independent mode4/Gate5
control recordings before altering driver contact retention.

## 2026-10-16 20:13 UTC: PR87 true s2idle 2/2 **PASS**; release-voice observation

The operator reran the CI-tested `pr87-exact-head.sh s2idle2`
with source `18f0fe79623e6de4fdf1ae493f82a7048397386a`,
signed `.ko` SHA256
`61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`,
loaded `srcversion=65F0D14FBDFB5E84748373E`, kernel
`7.0.0-34-generic`.

The runner verified a genuine s2idle sleep gap of **158.454s**
in cycle 1 and **324.521s** in cycle 2, corresponding kernel
PM entry/exit logs, the same signed PR driver remaining loaded,
readable controller/HID bindings and protocol statistics, and
two separately completed audible post-wake live evdev tests
(single finger move + 2 original fingers pinch→expand→release).
Both test sessions reported live gate, identity, reset/drop
and evidence checksum **PASS**. After cycle2, the runner
unloaded only the matching experimental module, verified
production Gate5 restored and reported
`PR87 S2IDLE 2/2 PASS`.

**Physical evidence remains on the unit:**
`~/sl4a-hardware-runs/pr87-exact-s2idle2-20261016T201323Z`,
`cycle-s2idle-1-quick`, `cycle-s2idle-2-quick`,
plus verified top-level PM/clock/journal/stats/result checksums.
The terminal transcript does NOT include the raw evdev timing
files or physical finger-off timestamps, so no release latency
is calculated.

**User-raised release observation:** on **every** two-finger
test, the voice said `One original finger remains. Lift it now.`
after `Lift both fingers now.` and before `Detected. Test passed.`.
Source audit shows the instruction is emitted on a recorded
intermediate original pair contact change `{A,B}->{A}` (or B),
while the gate cannot pass until `{}`. Therefore it does
**not mean a lingering finger was accepted as a PASS**, but
speech is emitted synchronously and can describe an already
expired frame by the time the words finish playing. A voice-
only correction now retains this transitional state as a
timestamped `gesture-progress` marker without broadcasting
a stale physical direction; the strict pair identity and
zero-contact acceptance criteria remain **unchanged**.
If the user observes persistent phantom touch or click/drag
after release outside this voice test, analyze the saved evdev
`operator/live-evdev.jsonl` and cue markers before ruling out
a decoder/tracker issue. The new narration source change was
made **after** this physical PASS and does not alter the
tested PR driver revision.

**This exact-head PR still needs cold boot, full matrix,
and default-standard opt-out physical checks.**

## 2026-10-16 first PR87 s2idle attempt: real sleep PASS, gesture INCOMPLETE

User ran `bash tools/experiments/pr87-exact-head.sh s2idle2` on
`7.0.0-34-generic` with exactly pinned PR87 SHA
`18f0fe79623e6de4fdf1ae493f82a7048397386a`.
The tested signed `.ko` was SHA256
`61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`,
loaded `srcversion=65F0D14FBDFB5E84748373E`.
Baseline Gate5 `3326E559A916BE5CB52375D` and both bindings passed.
Operator explicitly typed `S2IDLE` and `YES` for cycle1.

**Physical result:** `systemctl suspend` returned, a
`CLOCK_BOOTTIME - CLOCK_MONOTONIC` gap of **233.101 seconds**
verified genuine suspend/resume. The runner reached the post-wake
audible prompt, which the operator reported hearing. However the
interactive input did not match the confirmation gate: output shows
`Yes` **before the prompt** and `yes` after it. The Python
helper's existing `.upper() == "YES"` **already accepted lowercase**
by design. The exact line Python received is not recorded; an
early/duplicated input may explain its mismatch, but is not proven.
It printed `VOICE INCOMPLETE: Post-wake speech unconfirmed` and
therefore **did NOT execute the post-wake evdev gesture test** or
start cycle2. Its ordinary EXIT cleanup reported
`RESTORE PASS: working production Gate5 bound`.

This event is **not** a driver s2idle/touch failure and **not**
one of the required completed 2/2 lifecycle tests. Record:
one real s2idle interval and PR module/binding survival to the
post-wake prompt, but post-wake touch **UNQUALIFIED**; overall
`INCOMPLETE` with verified safe production rollback.

**Harness improvement:** `speak_operator.py` continues to
accept `yes`/mixed-case/uppercase but now allows **three explicit
attempts** to correct an unmatched input line without failing
the physical test and unloading the temporary driver. It still
refuses all ambiguous/no confirmations and cannot advance a
gesture test without operator-verified audible speech. CI tests
include lowercase, mixed case, an invalid-first/valid-second
sequence, and three invalid attempts. The physical s2idle2 test
must be restarted with the updated harness; no previous physical
PM cycle can be silently counted as a post-wake touch PASS.

## 2026-10-16 19:37 UTC: PR87 exact-head WARM 3/3 **PASS**

Physical log pasted by operator. Target: Surface Laptop 4 AMD
MSHW0231, Ubuntu `7.0.0-34-generic`, production Gate5
`srcversion=3326E559A916BE5CB52375D`, both controller and touchscreen
bound.

- **Exact source:** `18f0fe79623e6de4fdf1ae493f82a7048397386a`
  (GET6 write-only; NOT the independent GET6-free mode4).
- **Same signed test binary in all 3 warm loads:**
  SHA256 `61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`;
  `srcversion=65F0D14FBDFB5E84748373E`.
- **Evidence root:**
  `~/sl4a-hardware-runs/pr87-exact-warm3-20261016T193705Z`.
  The source log reports distinct
  `cycle-1-quick`, `cycle-2-quick`, `cycle-3-quick` evidence
  directories, each with a recorded `operator` provenance folder.
- **All 3 cycles:** `PR87 ACTIVE: verified loaded PR srcversion ...`;
  audible preflight confirmed by user; event-gated single-finger move
  and release PASS; original two fingers detected through
  pinch→expansion→sequential lifting PASS; runner reported
  `All live gesture gates, source identity, resets, frame drops and
  evidence checksums passed`; `RESTORE PASS: working production
  Gate5 bound` at the end of each cycle.
- **Final runner verdict:** `PR87 WARM 3/3 PASS`. The runner
  recorded no change to DKMS or persistent boot options. User hasn't
  supplied the individual counter snapshots or raw evdev files in
  this message, so do not invent numeric delta totals or represent
  them as independently inspected here.

**Qualification:** 3 independent PR87 exact-head warm activations +
3 genuine quick gesture/counter/integrity sessions + 3 driver
restorations **PASS**. This is not yet an s2idle/cold/full
matrix/default control PASS. Keep PR draft pending those tests.

## Why a separate campaign?

The GET6-free mode4 path successfully completed a true cold startup
on the user's hardware, but **this PR does not implement mode4**.
PR87 opts into `std_raw_transition=1 raw_input_beta=1`,
which writes GET_FEATURE6 **without synchronously reading it**,
waits 4.5–5.5ms, and then sets feature5. It must be independently
tested on its exact SHA, with a module whose srcversion differs from
installed Gate5.

Reviewer's 2026-10-16 scope finding about unsolicited report 0x0c
in ordinary/default standard mode was fixed at `18f0fe8`:
default post-creation IRQ handling holds report12 for observation,
not HID publication, and the opt-in MT tracker consumes it without
forwarding it to HID. Executable actual-handler regression tests
exercise opt-out `0x0c`, opt-in `0x0c`, non-`0x0c` standard
reports, raw with/without tracker, pre-HID drain ownership and
watchdog policy. Both kernel builds and host tests passed at
https://github.com/avgbob/SL4A_TouchScreen/actions/runs/38952701397.
These are **host/CI results only**.

## 2026-10-16 first physical warm attempt: INCOMPLETE, safe Gate5 restore

Physical command
`bash tools/experiments/pr87-exact-head.sh warm3` on
Surface kernel `7.0.0-34-generic` first confirmed:

```text
BASELINE PASS: Gate5=3326E559A916BE5CB52375D, both bindings active
PR SOURCE PINNED: 18f0fe79623e6de4fdf1ae493f82a7048397386a
EXPERIMENT READY:
 signed SHA256=61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e
 srcversion=65F0D14FBDFB5E84748373E
=== PR87 WARM CYCLE 1 / 3 ===
PR87 ACTIVE: verified loaded PR srcversion 65F0D14FBDFB5E84748373E
tools/experiments/pr87-exact-head.sh: line 146: protocol: unbound variable
RESTORE: unload only matching PR87 experimental HID
RESTORE PASS: working production Gate5 bound; test touch physically
```

Root cause: `capture()` declared
`local cycle="$1" protocol="$2" out="$session/cycle-$cycle-$protocol"`
in **one** Bash `local` command, so the `out` initializer
expanded `protocol` before it had a value under `set -u`.
The actual driver had loaded before this shell error; **NO
GESTURE CAPTURE OCCURRED**, and no 1/3 or 3/3 PASS is claimed.

The correction declares `cycle/protocol` **before** calculating
`out`. The host suite now executes the *actual shell function*
with `set -Eeuo pipefail`, mocked external collector, verified
argument routing, and before/after evidence paths. The rerun
also runs Kbuild `clean` on the *separate transient PR driver
worktree* before rebuilding/signing, so it cannot append a
second MOK signature to the previously signed `.ko`.
It does **not** clean or alter installed DKMS or the user's
production profile. Warm activation must be retried with the
corrected harness checkout and a fresh evidence session directory.

**This is a test-runner regression, not evidence of a GET6
driver failure.** A completed warm touch/session run has yet to
be observed; the independent mode4 coldboot evidence remains
separate.

## First physical step: exact-head WARM 3/3

The source-qualified test harness lives on the *independent*
`experiment/sl4-std-host56-set5` branch in
`tools/experiments/pr87-exact-head.sh`. It does NOT add test
scripts to the upstream PR driver branch.

```bash
cd ~/SL4A_TouchScreen-host56
git fetch https://github.com/avgbob/SL4A_TouchScreen.git experiment/sl4-std-host56-set5
git switch --detach FETCH_HEAD
bash tools/experiments/pr87-exact-head.sh preflight
bash tools/experiments/pr87-exact-head.sh warm3
```

The first command is read-only. The `warm3` command requires
typing **`WARM`** before driver modification. It fetches the
separate PR source into `~/SL4A_TouchScreen-pr87`, insists the
fetched PR head exactly matches `18f0fe8`, refuses tracked
modifications, builds the PR driver once against the current kernel,
signs it using the *already enrolled* Ubuntu MOK, verifies loaded
srcversion against the PR build (distinct from production), checks
both controller and HID bindings, and executes three independent
spoken `quick` gesture captures via the reused evidence collector.

**Important:** the evidence collector now supports
`--source-root ~/SL4A_TouchScreen-pr87`, so exact Git commit,
signed `.ko` hash and loaded srcversion come from the actual PR
driver checkout, not from the separate host56 harness checkout.
The program restores the original installed Gate5 between every
cycle, and in a shell EXIT trap on ordinary errors/interruption.
No DKMS install, persistent modprobe, systemd activation edit or
cold-boot override. As with every runtime module test, SIGKILL or
machine-wide failure can bypass shell EXIT: normal reboot preserves
the installed Gate5 startup path.

On a fully verified run, a successful verdict must include:
3/3 spoken event-gated one- and two-finger gestures, real increasing
CapImg DATA/observed counters, no newly dropped frames/unexpected
resets, identical signed SHA through all three cycles, actual loaded
PR srcversion in each capture, and restored installed Gate5 source
identity/bindings between and after the three cycles.

Evidence will be retained at
`~/sl4a-hardware-runs/pr87-exact-warm3-<timestamp>/`.
Do not claim 3/3 PASS from CI or from this documentation alone.

## Next physical step: PR87 EXACT-HEAD TRUE S2IDLE **2/2 (PENDING)**

**Prerequisites:** save open work and ensure the same tested PR branch
commit remains `18f0fe79623e6de4fdf1ae493f82a7048397386a`.
The stable production Gate5 mode1 must be loaded and physically
responsive before running. The previous warm test confirmed that
the PR module builds, loads, and restores safely on kernel34;
**that does not count as suspend testing**.

Use the independent, regression-tested external harness:

```bash
cd ~/SL4A_TouchScreen-host56
git fetch https://github.com/avgbob/SL4A_TouchScreen.git experiment/sl4-std-host56-set5
git switch --detach FETCH_HEAD
bash tools/experiments/pr87-exact-head.sh preflight
bash tools/experiments/pr87-exact-head.sh s2idle2
```

The read-only `preflight` verifies the current installed Gate5
module and both live bindings. `s2idle2` requires explicit
**`S2IDLE`** before compiling/signing/loading any experimental
driver. It builds the *same exact PR source* once into a transient,
MOK-signed module. Its signed SHA may or may not be identical to
the previous warm3 SHA due to rebuild/signing; this test explicitly
pins one signed SHA *across both suspend cycles*. The physical
first-person results still need to be observed, not inferred.

For each of TWO sleep cycles, user hears the warning, then types
**`YES`** before `systemctl suspend`. Wake manually and unlock,
return to the same terminal. The runner refuses to count an early
`systemctl` return as a real sleep: it requires `CLOCK_BOOTTIME -
CLOCK_MONOTONIC` sleep gap ≥2 seconds, both kernel
`PM: suspend entry (s2idle)` and `PM: suspend exit` markers,
unchanged loaded experimental driver srcversion and signed module
file, both AMD+HID bindings and usable protocol counters. The
post-wake voice must actually be *heard* and confirmed (another
typed **`YES`**) before the event-gated quick one/two-finger
gesture test. Separate capture files and PM logs are retained
per cycle. After both, the helper unloads only the matching
experimental module, reloads Gate5 controller/HID, and verifies
production identity and binding.

On an ordinary failure or signal it attempts Gate5 restore.
As before, SIGKILL or loss of power can bypass a shell trap;
the installed production boot profile remains unchanged, so
a normal reboot is the fallback. This is deliberately NOT a
persistent DKMS/boot experiment.

An actual PASS requires output `PR87 S2IDLE 2/2 PASS`,
both independent verified sleep gaps, the event-driven guided
gestures after wake, and final Gate5 restore. Local artifact:
`~/sl4a-hardware-runs/pr87-exact-s2idle2-<timestamp>`.
**No s2idle PASS has yet been observed for the current PR**.

## Next acceptance categories after warm 3/3

1. **Exact-head full gesture matrix** (all phases with live evdev
   tracking IDs and release semantics); a short quick PASS is not the
   complete matrix.
2. **Two genuine s2idle suspend/resume cycles**, with actual sleep
   timing, postwake audible confirmation, touch, counters, and the
   same signed module identity before/after resume.
3. **True cold poweroff/power-on** using a separately reviewed
   one-shot systemd boot helper which consumes its override before
   experimental insertion, watches for prior HID probes, and has an
   independent timed rollback that reloads *both* AMD and HID
   controllers. Pin the PR code and running/next-boot kernel first.
4. **Default-standard negative control**: load the PR module
   with `std_raw_transition=0 raw_input_beta=0` on the exact
   MSHW0231, check the bridge does not register the MT tracker,
   verify ordinary HID policy/non-`0x0c` reporting, and restore
   Gate5. Default `0x0c` forwarding is separately guarded by
   compiled host tests; field control must not incorrectly infer
   lack of device output proves the conditional behavior.
5. **Spontaneous post-DONE reset/rearm** remains NOT EXERCISED
   unless it happens without explicitly forcing/reloading a module;
   do not re-label a warm reload as spontaneous-reset coverage.

The PR should remain a draft until relevant exact-head physical
checks and reviewer's remaining concerns are resolved. Source commits
made after `18f0fe8` invalidate the tester's hardcoded SHA pin
until re-reviewed and updated. Do not re-stage unrelated mode4
coldboot tests while doing PR87 tests.
