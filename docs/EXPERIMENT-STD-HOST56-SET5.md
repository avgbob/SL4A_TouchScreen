# MSHW0231 standard-transport host-0x56/no-GET6 activation A/B

**Status (2026-10-16):** opt-in mode4 has now physically passed
all four *planned categories*: the gesture matrix across independent
runs, **three successive warm activations**, **two real s2idle/resumes**,
and **one true cold power-off → power-on followed by event-gated
touch gestures**, automatic Gate5 restoration and sealed checksums.
The successful one-shot cold test used exact checkout **`c196f206`**
on kernel **`7.0.0-34-generic`**, whereas prior warm and suspend
qualification used other exact mode4 builds on kernel31. **Do not
treat these independent runs as one unchanged-binary qualification**.
Only the original SL4 AMD 13.5-inch / MSHW0231 is proven; cross-device
compatibility and durability remain unqualified. **Do not promote
mode4 to installer default.** The installed Gate5 mode1 remains the
working production/boot profile; DKMS, MOK, and persistent
modprobe settings were not changed by the cold-boot test.

### 2026-10-16: FIRST REAL MODE4 COLD POWER-ON **PASS**

User completed a full physical shutdown and power-button start using
the one-shot late-boot service. The recorded staged boot
`1cd3ebae-96c0-4d4d-9073-85f8485d8d12` differs from trial/current
`275a12d5-5e6c-42cc-98cd-28b8435eb5a7`; helper was
`ACTIVE_AWAITING_POSTBOOT_TOUCH` and live mode was **4**. The
source checkout was **`c196f2064163a1fc5c7be70b2ba3d51f04e9ec61`**,
Ubuntu kernel **`7.0.0-34-generic`**, existing-MOK-signed module
SHA256 **`5361315c6bfb28a895888e5394622ba078a1f736e7b84d16aa22e5f13b1b66c4`**.

The spoken guide was heard and explicitly confirmed, and the
event-gated `quick` sequence passed one-finger travel/release,
two-finger closing/opening and both releases. The runner verified
no unexpected resets/dropped frames and validated the evdev evidence
checksums. User evidence:
`~/sl4a-hardware-runs/mode4-quick-20261016T185822Z`.
Automatic **Gate5 mode1** restoration was recorded at 18:59:57Z
and the one-shot result printed **`PASS one cold first-HID load,
actual gestures, restored Gate5`**. Root-owned provenance and
**14 successfully checked SHA256 entries** were sealed at
`/var/lib/sl4a-mode4-coldboot`. This is a *reported physical
test transcript*; complete evidence contents remain on the Surface.

The preceding attempted cold boot failed to run mode4 because a
pending Ubuntu update switched the kernel from 7.0.0-31 to
7.0.0-34. That **earlier trial remains INCONCLUSIVE**, not a
touch-driver failure. Its abort revealed the incomplete fallback
that omitted the AMD SPI controller. This was corrected in the
source, and Gate5 touchscreen functionality was separately
confirmed after manually loading `sl4a-spi-amd` on kernel34.

**Upstream scope:** Syax89 draft PR #87 uses a *different* activation
sequence (write-only GET6, ~5ms, SET5) and needs the exact current
PR-head physical cold/warm/resume/default-standard controls.
No mode4 physical evidence is passed off as PR #87 acceptance.
See [physical-unit roadmap](PHYSICAL-UNIT-ROADMAP-2026-10.md).



## Why this is a different A/B

2026-10-16 warm-reload test on the original SL4 AMD 13.5-inch, 7.0.0-31-generic,
installed `sl4a-touch/1.7.0` srcversion `3326E559A916BE5CB52375D`:

| Standard-transport activation | DATA | CapImg `raw_observed` | Reset responses |
| --- | ---: | ---: | ---: |
| Mode 3, bare SET5 | 2461 | **0** | 1 |
| Mode 1, GET6(write-only) + ~5 ms + SET5 (restored) | 1048 | **1036** | 1 |

Mode 3 delivered ordinary touch reports rather than CapImg during this run.
A historical 2026-09-21 mode-3 run did produce CapImg; the difference is
unresolved. Neither observation justifies promoting a universal activation
sequence.

### 2026-10-16 mode 4 hardware result — FIRST WARM RELOAD **PASS: CapImg streaming**

Experiment performed on the same Surface Laptop 4 AMD 13.5-inch, running
Ubuntu kernel `7.0.0-31-generic`. Detached test worktree at `308f914`.
`mode4_host56_source_test.py` passed; both out-of-tree modules built
against installed kernel headers. The transient `sl4a-spi-hid.ko` was
signed with the machine's **existing enrolled Ubuntu MOK**; no DKMS
installation or boot configuration change was required.

The driver reported `std_raw_transition=4` and received exactly one reset
response and one each of DEVICE_DESC/RPT_DESC during initialization:

| Mode 4 counter | After activation, before touch | After 10 s finger test | Delta |
| --- | ---: | ---: | ---: |
| `reset_rsp` | 1 | 1 | 0 |
| `device_desc` | 1 | 1 | 0 |
| `rpt_desc` | 1 | 1 | 0 |
| `data` | 0 | **749** | **+749** |
| `raw_observed` | 0 | **749** | **+749** |
| `irq_count` | 3 | **752** | **+749** |
| `frames_dropped` | 0 | 0 | 0 |
| `getfeat_resp` | 0 | 0 | 0 |

Kernel evidence at 2026-10-16 10:49:43 local:
`SEQ: first V0 0x0c heatmap body observed (len=4302, standard)`.

The sequence is `0x56 FF×6 → usleep_range(37000,40000) → SET5`;
there is **no GET6** in the mode-4 source branch. This proves GET6 is
**not necessary for CapImg activation** on this controller in this warm
reload. Neither a second reset nor a dropped frame was observed.

**Input confirmation:** tester subsequently confirmed that **two-finger
pinch works** with the exact mode-4 build tested here (`308f914`). Therefore
this run establishes both CapImg streaming and a real multitouch gesture,
not merely frame arrival. The logged `standard-mode liveness` messages
(with `std_liveness_ms=0`) are a known inherited watchdog arm outside raw
mode, independently reported in upstream PR #87 review. They did not cause
a reset or observed frame drop during this capture; fix separately and
requalify the resulting code before claiming an exact-revision pass.

**Qualification still pending:** repeated warm reloads, cold boot, s2idle,
pen, sustained input quality, and independently logged post-test Gate5
restoration. The comparison with failed mode 3 changes **both** the
preceding `0x56` write **and** the elapsed delay; this run does **not**
isolate which is necessary. Historical mode-3 success is another
confounder. Do not promote mode 4 to default.

Initial CI for commit `308f914` passed, including host tests and kernel
builds; hardware and regression conclusions are separate.

### 2026-10-16 corrected mode-4 event-gated run: two gestures pass; continuity inconclusive

Physical run `mode4-full-20261016T155826Z` used corrected standard
bridge/watchdog code at checkout `fad839f` and a temporarily signed
mode4 module. Spoken cue preflight, the live evdev monitor, and the
read-only evidence collector started. Actual event-gated observations:

- `quick-one`: single-finger movement **and release PASSED**.
- `quick-pinch`: two-finger closing motion **PASSED**.
- `quick-expand`: the original pair's IDs no longer matched; three
  attempts of continuation failed and the session was correctly
  recorded **INCONCLUSIVE**, not a full mode4 qualification PASS.
- The one-command `qualify` wrapper restored DKMS Gate5 mode 1.

Independent **read-only analysis of saved input events** showed pinch
IDs `[1, 2]`; the first observed contact loss was a frame with
**no contacts +3.114 s** after the pinch PASS. The next spoken expansion
instruction did not begin until **+13.65 s**, and expand GO did not
occur until **+19.67 s**. The original pair therefore disappeared
**during the excessively long spoken gap**, 10.54 seconds before the
next instruction. Later different-ID frames came from repeated
continuation attempts and should not be counted as distinct failures.

The evidence does **not** reveal whether the tester deliberately lifted,
the controller stopped reporting contacts, or the software tracker
released them. It demonstrates why that run cannot be used to judge
uninterrupted touch ID continuity, **not** a proven driver failure.

**Harness correction:** independent gestures retain full audible
countdowns, while connected pinch→expand→hold→lift actions get
immediate spoken transitions; all intervening evdev frames are checked.
A lost pair now stops the connected sequence immediately as
INCONCLUSIVE rather than retrying its last movement. Host behavioral
tests for preserved and interrupted contact chains are green. These
changes have **not yet passed an end-to-end physical run**. The first
two gesture passes remain historical evidence for the previous runner.

See [physical-unit roadmap](PHYSICAL-UNIT-ROADMAP-2026-10.md) for
remaining hardware steps. Do not promote mode 4 to default.

### 2026-10-16 16:17: mode4 reaches full second pinch chain, final release inconclusive

At exact checkout `5cba3b5` with temporary, MOK-signed mode4
binary SHA256 `84086c66654f20163b3db5c34ceb7af9ed82670b2cb36d6567c6e91dde49890c`,
the new voice-controlled `qualify full` successfully event-gated
`quick-one`, `quick-pinch`, `quick-expand`, `quick-lift`, then
`pinch-far`, `pinch-close`, `pinch-hold`, `pinch-expand`.
The 9th phase `pinch-lift` was marked **INCONCLUSIVE** after an
intermediate nonempty contact frame no longer contained both original
tracking IDs. Automatic rollback restored Gate5 mode1.

This is **not yet** proof of a driver tracking-ID defect: the old
harness mistakenly required two original IDs **until directly empty**,
rather than accepting the natural sequential release
`{A,B} -> {A} -> {}` or `{A,B} -> {B} -> {}`.
The gate now accepts only monotonically shrinking original-ID subsets,
rejecting any new/reappearing ID and requiring eventual all-up. These
changes have host regression tests. **Saved physical event audit completed:** the saved session's
expected IDs were `[3, 4]`. The physical evdev events transitioned
`[3,4] -> [4]` at **+2.953s** after the expansion PASS, then
`[4] -> []` at **+2.963s**, with **no new tracking ID**.
The release instruction began at +0.550s and release capture at +2.812s.
This proves the old test verifier **falsely rejected a normal sequential
lift**, rather than demonstrating a driver tracking regression.
The fixed release gate passes this exact state sequence in host tests.

The original recorded phases **1–8 passed live**, and phase 9's
original-pair release was subsequently confirmed by offline audit.
The remaining seven `contacts` phases have not yet been exercised.
The safely restoring `qualify contacts` subcommand is provided to
run those *without repeating the first nine observations*. These are
separate evidence sessions, not one uninterrupted 16-phase PASS.
Cold boot, repeated reload, s2idle and pen remain unqualified.

DieSchatten's independent 13.5-inch MSHW0231 unit uses a different **raw-mode**
sequence: report 0x56 with all-six-`FF` payload, ~37–40 ms delay, SET5,
and **no GET6**. That combination produced CapImg on his unit; GET6 paths
reset his controller. See
https://github.com/Syax89/SL4A_TouchScreen/issues/85

**Independent follow-up (DieSchatten, 2026-10-16):** his live
`wVersionID=0x0004`, matching our recorded value. His IRQ-driven
GET6 response-read experiments with SET5 delayed **1.7 ms or 17.3 ms
after the response** both reset at ~111 ms. This argues against the
post-response interval alone explaining his Linux GET6 failure, although
it does not fully test the timing of our distinct write-only GET6 path.
A shared `wVersionID` does not prove identical internal firmware or panel
subrevisions. See the exact follow-up:
https://github.com/Syax89/SL4A_TouchScreen/issues/85#issuecomment-6215981627

This experiment copies only the missing **feature-write order** onto the
existing **standard HID-over-SPI** transport. A result will not establish
equivalence to his raw transport, power cycle, read register policy or firmware.

### 2026-10-16 16:38 UTC: **all seven remaining contacts PASS on physical mode4**

The operator ran `bash tools/experiments/host56-mode4.sh qualify contacts`
from **checkout `14a8991`**, signed driver SHA256
`f6de86ede8ee9d05adbce85ad842aa0aa2f202d7ad85d1c37976d840a86eef0e`,
kernel `7.0.0-31-generic`. Recorded immutable local evidence:
`~/sl4a-hardware-runs/mode4-contacts-20261016T163800Z`.

**All seven actual event-gated phases passed** with audible, confirmed
instructions: 1, 2, 3, 4, and 5 fingers with verified release, selective
two-finger→one-finger→all-up, and lift/recontact with a new ID. The
collector's final report stated source/signature integrity, actual MT
events, reset and frame-drop checks, and evidence checksums **PASS**.
The runner restored the unchanged production Gate5 **mode 1** after
the session.

This completes the **planned behavioral gesture coverage across two
separate mode4 hardware runs**: the previous `quick`+multi-stage pinch
observations and offline-confirmed normal release, plus this 7/7
contact run. It is not one 16/16 uninterrupted session or a lifecycle
qualification. It also does **not** validate Syax89's separate GET6
write-only PR #87 SHA or the other contributor's distinct raw transport.

**Next:** repeated warm activation, two suspend/resume tests, and a true
cold-boot test only after implementing a safe, rollback-equipped opt-in.
The `qualify-warm3` wrapper builds/signs once, then runs **three
separate warm activations**, each with a short audible event-verified
`quick` capture and immediate Gate5 rollback. Do not mark the three
warm cycles as passed until their physical logs and checksums exist.

### 2026-10-16 16:49–16:55 UTC: **three successive warm activations PASS**

The physical `qualify-warm3` session used exact source `3fb72d4`,
temporary signed module SHA256
`71a03f648c17699610f1f02ae5d59baf813fb75c0dffa78ca428b8edb005d680`
and kernel `7.0.0-31-generic`. That module was built and signed
**once**, and the same digest was printed before all three independent
warm activations. On each activation the host observed mode4,
`reset_rsp=1`, `device_desc=1`, `rpt_desc=1` and
`frames_dropped=0`. Each voice-directed `quick` sequence
(one-finger move/release, original-ID pinch/expand/release) passed
its live evdev gates. Each collector reported source/module integrity,
post-activation stable reset/drop counters, and checksums **PASS**.
After each capture the wrapper restored **the installed unchanged
Gate5 mode1**, including after cycle three.

- Cycle 1: `mode4-quick-20261016T164955Z`
- Cycle 2: `mode4-quick-20261016T165148Z`
- Cycle 3: `mode4-quick-20261016T165325Z`

All are beneath `~/sl4a-hardware-runs/`. This closes
**mode4 warm reload 3/3** for that tested source and binary, not
suspend/resume, cold boot, upstream PR #87, or DieSchatten's raw
transport. No kernel reinstall or MOK registration occurred.

**Historical s2idle test design (now physically PASSED 2/2):** the
`qualify-s2idle2` helper verifies that `[s2idle]` is selected,
asks for confirmation before each platform suspend, detects actual
suspend elapsed time using `CLOCK_BOOTTIME − CLOCK_MONOTONIC`,
requires kernel suspend-entry and exit markers, then runs one spoken
event-gated `quick` capture after each resume *without unloading
the temporary module between sleeps*. Restores Gate5 mode1 at the end
or on any ordinary script failure and retains independent evidence.
Rebooting is still handled by the unchanged production boot profile.

### 2026-10-16 17:34–17:39 UTC: **genuine s2idle/resume 2/2 PASS**

The same Surface Laptop 4 AMD, running kernel `7.0.0-31-generic`,
executed the corrected audio/clock-aware
`qualify-s2idle2` from **exact checkout `dc39813`**. The
transient MOK-signed mode4 binary SHA256 was
`de10c9769ec97b51a91dd86fcef6570e9f1dd205f4a82303339d773c8d7e7304`.
This is the same driver functionality as prior mode4 evaluations,
but the source SHA and signed file hash of **this** s2idle
qualification are recorded separately.

`CLOCK_BOOTTIME - CLOCK_MONOTONIC` confirmed actual suspend
intervals of **5.238s** and **23.315s**, and the harness verified
kernel `PM: suspend entry (s2idle)` and `PM: suspend exit`
markers, with mode4 still active on return. Both postwake spoken
prompts were heard and acknowledged, followed by a successful live
`quick` run: one-finger movement and release; two-finger pinch,
same-ID expansion, and release. No forbidden reset or dropped-frame
delta was detected; the collectors and main-session checksums
verified successfully.

- Main s2idle evidence: `mode4-s2idle2-20261016T173414Z`
- First postwake evdev trace: `mode4-quick-20261016T173525Z`
- Second postwake evdev trace: `mode4-quick-20261016T173808Z`

All under `~/sl4a-hardware-runs/` on the physical laptop. **Both
cycles used the same loaded temporary module**; no reload was
performed between suspends. The final cleanup restored the installed
Gate5 driver, verifying live `std_raw_transition=1`.

**Mode4 lifecycle status on the original test machine:** behavioral
matrix complete across two sessions, warm **3/3**, real s2idle **2/2**.
Still pending: **true cold power-on with mode4 selected during early
boot**. Rebooting or power-cycling with the unchanged installed profile
will load Gate5 mode1, so cannot validate mode4 cold startup. Neither
these results nor DieSchatten's separate raw transport is a substitute
for the exact-head acceptance Syax89 requested for PR #87.

## Opt-in mode 4

```text
ACPI MSHW0231 -> _PS0/_RST -> DEVICE_DESC -> 936-byte RPT_DESC
    -> SET_FEATURE report 0x56 = FF FF FF FF FF FF
    -> usleep_range(37000, 40000)
    -> SET_FEATURE report ID 5 = 1
    -> DONE; observe 0x0c CapImg and MT events
```

- `std_raw_transition=4`, `raw_mode=N`, `raw_input_beta=Y`.
- No GET6 write or read. No host Bluetooth address is replayed; the
  `spi_hid_wire_vendor_stop()` builder is reused for its pinned all-FF
  bytes, not for a claim that `FF×6` means "stop".
- Exact MSHW0231 ACPI match-data required. The SL4 geometry fallback
  **does not qualify** unknown/DT hardware.
- If writing report 0x56 fails, SET5 is withheld. No speculative retry,
  fallback or watchdog is added.
- Modes 1–3, existing DATA-drain handling, and the standard installer
  stay unchanged.

## Safe live A/B on the original Surface

You need a working keyboard or mouse; changing touchscreen modules can
interrupt touch. Run on the Surface Laptop 4 in Ubuntu, **not from another
computer**. These commands compile a temporary module in a separate worktree;
they **do not overwrite** the installed DKMS `.ko.zst`, the MOK identity,
or `/etc/modprobe.d/sl4a-spi-hid.conf`.

```bash
cd /home/jo/SL4A_TouchScreen
git fetch https://github.com/avgbob/SL4A_TouchScreen.git experiment/sl4-std-host56-set5
git worktree add --detach /home/jo/SL4A_TouchScreen-host56 FETCH_HEAD
cd /home/jo/SL4A_TouchScreen-host56

# Host test before module reload; does not touch hardware.
python3 tests/mode4_host56_source_test.py

# Compile for the RUNNING kernel, sign with an already-enrolled Ubuntu MOK
# if Secure Boot is enabled; fail BEFORE unloading on missing prerequisites.
bash tools/experiments/host56-mode4.sh prepare

# Switch only this running kernel to temporary mode 4; boot config unchanged.
bash tools/experiments/host56-mode4.sh activate

# One-finger then two-finger contact during the 10-second window; inspect
# raw_observed, data, reset_rsp, frames_dropped and initial kernel messages.
bash tools/experiments/host56-mode4.sh capture

# Explicitly restore original Gate5 DKMS module and confirm mode 1.
bash tools/experiments/host56-mode4.sh restore
```

If `activate` fails, the script attempts to reload the original installed
module. A **reboot** also restores original Gate5 because the persistent
modprobe configuration is unchanged. Never run `install`, `rebuild`, or
edit the persistent modprobe configuration as part of this comparison.

## Stop / go criteria

- **Pass candidate:** `std_raw_transition=4`, `raw_observed` increases
  while touching, two-finger input works, `reset_rsp` does not increase
  after initialization, and `frames_dropped` stays at zero.
- **Fail:** ordinary one-finger HID works but `raw_observed=0`, or extra
  resets/errors occur. Preserve logs and restore Gate5.
- **Inconclusive:** no data under two-finger-only test; also use a
  one-finger movement to confirm data transport, as in the 2026-10-16
  experiment.

A single passing warm reload does not qualify cold boot, repeated reload,
s2idle, pen, input quality or other firmware revisions. Hold upstream PR #87
in draft pending comparisons and compatibility policy.
