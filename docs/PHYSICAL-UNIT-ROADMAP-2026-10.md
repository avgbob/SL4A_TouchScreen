# Physical-unit roadmap: Surface Laptop 4 AMD / MSHW0231

**Date:** 2026-10-16. **Scope:** one local SL4 AMD 13.5-inch unit,
the independent DieSchatten device, and Syax89's upstream PR #87.
This is an operating plan, not a claim of broad compatibility.

## Exact PR87 true cold first-HID test: one-shot harness + rollback PREPARED

One-shot helper: `tools/experiments/pr87-coldboot-once.sh`.
Operator entry: `tools/experiments/pr87-exact-head.sh coldboot-stage`,
then physical full poweroff and on, then `coldboot-finish`.
Built on prior mode4 one-shot proven design but **PR87 != mode4**:
both PR87 experimental and installed Gate5 use standard mode=1,
so rollback MUST match the exact source `srcversion`, stage/trial
boot ID and stored production identity instead of relying on mode
alone. The same exact PR commit `18f0fe79623e6de4fdf1ae493f82a7048397386a`
is used. Installer, DKMS and persistent modprobe profile remain unchanged.
The temporary boot service drop-in self-consumes before insertion.
A separate 20-minute timer restores Gate5 if gestures do not finish.
Host CI can establish the scripted mock state machine and kernel builds,
but **cannot** demonstrate real power cycling. Missing/mismatched boot
ID, previous HID probe, kernel update, expired stage, signature or hash
mismatch refuse the test. A good run verifies actual post-boot
live single/two-finger gestures before physical PASS and production
Gate5 restoration. See
[exact PR87 acceptance](PR87-EXACT-HEAD-PHYSICAL-ACCEPTANCE.md)
for precise commands, failure categories and recovery.

**PHYSICAL FIRST-HID COLD PASS STILL PENDING.**
Do not label the independent mode4 cold success as PR87 cold PASS.

## PR87 physical negative control: observational PASS after false-negative correction

The exact signed PR87 module was tested with
`raw_mode=N raw_input_beta=N std_raw_transition=0`.
The uploaded terminal reported `ready='ready'`, `seq_state='4'`,
both descriptor counters 1, no extra `MSHW0231 Touchscreen`
input instance, and matching module source identity.
The original checker returned `INCONCLUSIVE` solely because it
expected `ready='1'`. Exact PR source defines textual `ready`
and sequencer DONE=4, so the physical observations satisfy the
intended opt-out control. The runner then **restored Gate5**.
The original verdict is preserved and a read-only saved-verdict
re-review route was added with strict error and identity checks.
**This does not physically prove report 0x0c HID-dispatch behavior.**
**Only the true PR87 first-HID cold-power-on gate remains** from
the defined physical categories; an unforced spontaneous-reset
scenario has not been observed.

## PR87 default-standard negative-control runner: READY FOR PHYSICAL TEST

Added `pr87-exact-head.sh standard-negative`, using the same pinned
PR source and signed module as prior warm/s2idle/matrix qualification.
It opts out via `raw_mode=N raw_input_beta=N std_raw_transition=0`
and requires normal standard HID discovery plus absence of the
`MSHW0231 Touchscreen` heatmap MT input device. A read-only checker
fails closed for missing descriptors, incorrect parameters, module
identity mismatches and leaked bridge registrations. The test
**does not assume** passive `raw_observed=0` or treat device silence as
physical proof of Report `0x0c` dispatch policy. Its host tests use
synthetic sysfs fixtures; a separate compiled production-handler test
covers 0x0c policy. Restores installed production Gate5 on exit
and writes a private local evidence bundle.

**Physical result (later, 21:49 UTC):** the hardware run's captured
flags/descriptor counters/MT-bridge inventory all satisfy the corrected
source contract; its original verifier incorrectly expected ready=1
instead of the driver's literal ready='ready'. See retrospective audit
below. True exact PR87 cold first-HID power-on remains pending.
No PR driver source changes.

## 2026-10-16 21:33 UTC: PR87 exact-head FULL GESTURE MATRIX **16/16 PASS**

**Physical SL4 AMD / MSHW0231**, Ubuntu kernel `7.0.0-34-generic`.
The one-shot `pr87-exact-head.sh full-matrix` activated
the **same exact pinned upstream PR87 source**
`18f0fe79623e6de4fdf1ae493f82a7048397386a`,
signed module SHA256
`61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`,
`srcversion=65F0D14FBDFB5E84748373E`.

All **16** spoken, evdev-gated quick/pinch/contacts phases
passed: 1–5 active fingers, continuous original two-finger
pinch/expand/hold/release, partial one-finger lift and new
contact after release. The newer nonblocking speech harness
did not narrate the previously stale singleton release cue.
The operator transcript explicitly reports passing source identity,
driver reset/drop counters and evidence checksums. The exact
individual counter deltas and raw evdev records were not supplied;
do not invent them.

Run: `~/sl4a-hardware-runs/pr87-exact-matrix-20261016T213332Z`;
capture: `cycle-matrix-full`. Afterward
`RESTORE PASS: working production Gate5 bound` and
`PR87 FULL MATRIX PASS; source pinned, signed module stable,
Gate5 restored.` Four top-level evidence hash entries verified.

**Acceptance state: PR87 warm 3/3 PASS; s2idle 2/2 PASS;
full gesture matrix 16/16 PASS. Outstanding:**
(1) **exact-PR87 true cold first-HID power-on**, and
(2) **default-standard negative/opt-out physical control**.
The previously completed GET6-free mode4 cold trial is a
different exact driver/protocol, not evidence for the PR87 cold gate.
Avoid redundant repeat of the successful warm and s2idle tests.

Full chronology:
[PR87 exact-head physical acceptance](PR87-EXACT-HEAD-PHYSICAL-ACCEPTANCE.md).

## 2026-10-16 21:06 UTC: PR87 release-voice lag **CONFIRMED**

Read-only evidence comparison of PR87 warm cycle 2
(`pr87-exact-warm3-20261016T193705Z/cycle-2-quick`) against
the old narrated test script:

- Original first-ID release → final-ID release:
  **425.775ms in kernel evdev time**, **425.745ms in Python observer**.
- The `Lift both fingers` prompt was queued **1300.443ms BEFORE**
  the first release, and `lift` phase begin marked **961.236ms AFTER**.
- **Both fingers were already reported absent 536.178ms BEFORE**
  the later `One original finger remains` progress cue was queued.
- The PASS cue was logged **4802.244ms after** the first release:
  **4376.499ms after actual last-release event**, consistent with
  the old **synchronous** intermediate announcement blocking
  consumption of queued input frames.

**Causal boundary:** the stale `One original finger remains` voice
could NOT have caused the earlier 425.775ms inter-release interval,
because its cue occurred only after both contacts had been released.
That interval is a **measured Linux event gap**, not proven delayed
driver reporting relative to physical fingertip separation;
operator timing vs firmware/driver remains unresolved.
No replacement/reappearing tracking IDs were found. The new
harness already suppresses the stale voice instruction
**without changing strict evdev continuity acceptance or PR code**.
A separate external physical finger-off reference is needed
for true hardware release latency attribution.

Detailed log and all six measured intervals:
[PR87 exact-head physical acceptance](PR87-EXACT-HEAD-PHYSICAL-ACCEPTANCE.md).
**Historical outstanding status as of this release-voice investigation:**
exact-head cold first-HID boot, full gesture matrix and standard-mode
opt-out control. The full gesture matrix subsequently PASSED at 21:33 UTC;
see newer entry above.
Production Gate5 remains installed and working.

## 2026-10-16 20:13 UTC: PR87 exact-head genuine S2IDLE 2/2 **PASS**

The user's third PR87 s2idle attempt completed two genuine
sleep intervals of **158.454s** and **324.521s**, with kernel
PM entry/exit markers, retained signed PR module identity
(source `18f0fe79623e6de4fdf1ae493f82a7048397386a`,
signed SHA256 `61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`),
confirmed audible instructions, two event-gated one- and two-finger
postwake gesture PASS captures, and verified Gate5 restoration.
The runner finalized with `PR87 S2IDLE 2/2 PASS` and validated
all reported top-level evidence checksums.

Local run: `~/sl4a-hardware-runs/pr87-exact-s2idle2-20261016T201323Z`.
The two `cycle-s2idle-{1,2}-quick` evidence directories have NOT
been uploaded or independently inspected.

**Operator observation:** every two-finger test utters
`One original finger remains. Lift it now.`, then PASS.
Source inspection confirms the gate sees original pair
`{A,B}` → one surviving original ID → **zero original contacts**
before PASS. This is a normal possible release sequence,
**not** a gate that passes with one contact remaining.
However speech playback may lag after both fingers are
already off. Future harness versions now suppress ONLY that
stale spoken intermediate instruction while retaining the
original `gesture-progress` cue and strict zero-contact
gate; a behavioral test simulates two-to-one-to-zero releases.
The terminal log alone cannot quantify any eventual lingering
contact latency. Diagnose from local operator evdev timestamps
only if actual phantom touch is reported.

**Remaining PR87 separate acceptance:** exact-head cold
first-load, full gesture matrix, and default-standard negative
control. Do not count independent mode4 GET6-free cold testing
toward this PR.

## 2026-10-16 19:37 UTC: upstream PR #87 WARM 3/3 **PASS** (EXACT HEAD)

Separate physical test (NOT GET6-free mode4):
Syax89's draft PR #87 exact source
`18f0fe79623e6de4fdf1ae493f82a7048397386a`,
Ubuntu kernel `7.0.0-34-generic`, MSHW0231,
signed module SHA256
`61ec6f796d60b6e50d1c1888dc693e6cd135d08a023f1bccb0fc5ade15054d8e`,
experiment `srcversion=65F0D14FBDFB5E84748373E`.

After a recovered prior incomplete harness run, all **3 of 3**
genuine separate warm activations passed audible, evdev event-gated
one-finger and original two-finger pinch/expand/lift tests, source
identity, reset/drop counter and integrity checks, and the installed
Gate5 `srcversion=3326E559A916BE5CB52375D` was restored and bound
after each cycle. Evidence:
`~/sl4a-hardware-runs/pr87-exact-warm3-20261016T193705Z`,
with three distinct `cycle-*-quick` capture directories.
The full raw artifacts and per-counter deltas have not been separately
uploaded; do not invent them. Upstream comment:
https://github.com/Syax89/SL4A_TouchScreen/pull/87#issuecomment-6223447635 .

**PR #87 still DRAFT.** Its true cold first-HID load,
2/2 genuine s2idle, full gesture matrix and default-standard
negative control remain unqualified. The independent
`pr87-exact-head.sh s2idle2` runner is code/CI ready;
no physical PR87 suspend result yet. Full distinct-category plan:
[PR87 exact-head physical acceptance](PR87-EXACT-HEAD-PHYSICAL-ACCEPTANCE.md).

## 2026-10-16 18:58–18:59 UTC: mode4 TRUE COLD POWER-ON 1/1 **PASS**

**Physical Surface Laptop 4 AMD / MSHW0231**, Ubuntu kernel
`7.0.0-34-generic`. This is the **second** controlled one-shot attempt,
after correcting the prior kernel31→34 mismatch and incomplete Gate5
fallback; the first attempt remains **INCONCLUSIVE** and must not be
relabelled as a failure of experimental mode4.

**Qualified exact experimental source:** `c196f2064163a1fc5c7be70b2ba3d51f04e9ec61`.
**Existing-MOK-signed mode4 binary SHA256:**
`5361315c6bfb28a895888e5394622ba078a1f736e7b84d16aa22e5f13b1b66c4`.
Stage boot ID `1cd3ebae-96c0-4d4d-9073-85f8485d8d12`;
power-on trial and current boot ID
`275a12d5-5e6c-42cc-98cd-28b8435eb5a7`.
The operator confirmed a **complete power-off → power-button on**
by typing `COLD` after the boot-ID and driver identity checks;
the helper reported `ACTIVE_AWAITING_POSTBOOT_TOUCH` with
`Live mode: 4`. The one-shot bootstrap had also recorded that no
previous HID driver instance appeared in the kernel log before
the experimental first HID load.

**Actual spoken and evdev event-gated `quick` session:**
`~/sl4a-hardware-runs/mode4-quick-20261016T185822Z`.
The operator confirmed *hearing* the synthesized voice; the runner
detected single-finger movement + release, original two-finger
pinch/continuing expansion + sequential releases, and announced
`All gestures were detected`. Its verdict explicitly said
`All live gesture gates, source identity, resets, frame drops and evidence checksums passed`.
Do not mistake a timer or an ordinary `evtest` device listing
for this operator-driven verification.

**Recovery and sealed evidence:** at 18:59:54Z the one-shot service
unloaded **only the matching mode4 instance**; at 18:59:57Z it
reported `ROLLBACK Gate5 mode1 restored` and
`PASS one cold first-HID load, actual gestures, restored Gate5`.
All **14 reported** SHA256 items verified, including staged binary,
module/source identity, stage/trial boot IDs, before/after sysfs,
before-HID and after-AMD kernel journals, final result and events.
Root-owned local evidence: `/var/lib/sl4a-mode4-coldboot`;
the test also preserved a user-owned `mode4-quick` capture bundle.
The transcript did **not** publish each individual counter delta,
so cite the runner's verified reset/drop verdict instead of
inventing measurements. Evidence folders remain on the tester's
computer and have not been uploaded to GitHub.

| mode4 milestone | Exact revision / kernel | Physical result |
| --- | --- | --- |
| Gesture matrix across independent sessions | prior mode4 test revisions / kernel31 | PASS (previous evidence) |
| Three consecutive warm activations | prior tested mode4 signed build / kernel31 | **3/3 PASS** |
| Two real s2idle suspend/resumes with postwake touch | `dc39813` / kernel31 | **2/2 PASS** |
| One-shot real cold power-on with live touch | **`c196f20` / kernel34** | **1/1 PASS** |

**Boundary:** this closes the last **planned category** of mode4
lifecycle testing on the user's physical MSHW0231. The milestones
were collected on **different exact builds and two kernels**;
it is NOT proof that a single immutable binary passed the entire
matrix, other users' hardware works, stylus is qualified or
long-term durability is established. **Leave installed Gate5 mode1
as the production default**; mode4 remains opt-in.

**Different branch and activation:** Syax89 PR #87
(`upstream/std-capimg-mt`, reviewed head historically
`2bf81e8`) uses **GET6(write-only) → ~5ms → SET5**; our mode4
uses **0x56 FF×6 → 37–40ms → SET5 without GET6**.
The mode4 success cannot count as exact-head PR #87 physical
coldboot, reload or resume acceptance. Next work is independently
qualifying the current PR #87 head, checking it again before any
upstream-ready claim.

## 2026-10-16: Gate5 touchscreen functionality RESTORED on kernel 7.0.0-34

**Physical operator confirmation:** After `sudo modprobe sl4a-spi-amd`,
the platform driver bound to `sl4a_spi_amd_v2_multi` and the MSHW0231
touchscreen bound to `sl4a_spi_hid`. Protocol statistics confirmed
`data=121`, `raw_observed=109`, `frames_dropped=0`, and `irq_count=125`.
The operator subsequently explicitly confirmed **"it works"** in response
to checking actual touch input (tapping, dragging and scrolling).

**Verdict:** normal Gate5 input functional on newly booted kernel
`7.0.0-34-generic` after manual AMD-controller recovery; no driver
reinstall or reboot required. This **does not** qualify the abandoned
GET6-free mode4 cold boot or prove all multitouch/pen scenarios on
kernel34. The boot-abort recovery defect was the omission of
`sl4a-spi-amd`; both source fallback and staging guard are now patched.
Retain incident evidence. A future one-shot coldboot trial must be
staged against the currently running and next-selected same kernel and
must retain the independent rollback path.

## 2026-10-16: AMD controller loaded manually; both driver bindings RECOVERED

**Physical hardware follow-up on kernel `7.0.0-34-generic`:**
after the first cold-boot attempt stopped on the known signed
module/kernel mismatch, the HID module was present (`mode1`) but
the AMD controller and MSHW0231 touchscreen were unbound. The user
ran the minimal recovery action **`sudo modprobe sl4a-spi-amd`**,
followed by `sleep 3`, without DKMS reinstall, HID removal or reboot.

The command exited without errors. Subsequent physical-unit output
proved **both expected bindings are established**:

```text
/sys/bus/platform/drivers/sl4a_spi_amd_v2_multi
/sys/bus/spi/drivers/sl4a_spi_hid
reset_rsp=1
device_desc=1
rpt_desc=1
data=121
getfeat_resp=0
frames_dropped=0
irq_count=125
wire_patches=1
poll_missed=0
raw_observed=109
```

**Verdict:** AMD SPI controller restoration **PASS**; MSHW0231
binding and standard-mode CapImg transport initialization **PASS**;
**actual finger-to-desktop evdev/GUI movement NOT YET VERIFIED** by
this particular transcript. The single stats snapshot includes
121 DATA packets and 109 raw observations with no dropped frames,
but contains no after/before delta explicitly tied to a live touch
gesture. Do not equate successful driver binding with end-to-end
multitouch qualification. Ask for a quick real touch confirmation
or a before/after counter + event-gated capture if the user still
sees no response.

**Root cause of current no-touch state supported by evidence:** the
original cold-boot `fallback()` loaded only HID, omitting
`sl4a-spi-amd`. Before manual recovery, both devices were unbound
and `protocol_stats` did not exist; after loading AMD they bound
and transport counters became available. Separately the cold trial
itself remains INCONCLUSIVE due to the unrelated kernel31→34
migration; this manual recovery is not a coldboot PASS.

**Pending:** do not rearm experimental mode4 until functional
finger input on stable production Gate5 is established. The source
fallback has been fixed to load AMD before HID and the new staging
guard checks both bindings plus readable stats.

## 2026-10-16: confirmed incomplete fallback — AMD controller absent

The user's read-only checks on booted kernel **`7.0.0-34-generic`**
showed **only** `sl4a_spi_hid` loaded, with no
`sl4a_spi_amd` in `lsmod`. Platform
`/sys/bus/platform/devices/AMDI0060:00/driver` was **UNBOUND**;
ACPI `MSHW0231:00/physical_node/driver` was also **UNBOUND**;
`/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats` did not exist
before or after finger movement. Kernel output showed HID loading but
no successful touch initialization. Both DKMS modules were reported
installed for kernel34, and the HID `srcversion` of the loaded and
installed module matched (`3326E559A916BE5CB52375D`).

This **confirms the missing AMD SPI controller is sufficient to
explain why touch is nonfunctional**, independently of Gate5 mode1
being present. It is consistent with the specific boot-abort
`fallback()` bug (only `modprobe sl4a-spi-hid`), and the source
fallback has now been corrected to load AMD first and inspect both
bindings. No physical module recovery outcome has yet been submitted.
**Do not call the touchscreen restored until actual contact events
are verified.**

One further safety fix prevents `coldboot-stage` from arming if
`sl4a_spi_amd_v2_multi` and `sl4a_spi_hid` are not both bound,
or if `protocol_stats` is unreadable, even when mode1 is present.

**Immediate physical recovery, pending observation:**

```bash
sudo modprobe sl4a-spi-amd
sleep 3
readlink -f /sys/bus/platform/devices/AMDI0060:00/driver
readlink -f /sys/bus/acpi/devices/MSHW0231:00/physical_node/driver
cat /sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats
```

No reboot, DKMS reinstall, experimental mode4 insertion, or HID
unload is needed for this first safe attempt. If bindings remain
absent, collect module loader error/kernel log before modifying
another component.

## 2026-10-16 ~18:15 UTC: IMPORTANT — Gate5 parameter 1 is NOT functional recovery

Following the aborted one-shot boot on newly installed kernel
`7.0.0-34-generic`, the user explicitly reports **the touchscreen
does not work**. Previous statements that the fallback "restored a
working Gate5" were **incorrect**: `std_raw_transition=1` only
establishes which module parameter is loaded, not controller binding,
HID input device creation, or actual contact events.

Source audit identified a concrete boot-abort recovery defect:
`fallback()` previously executed only
`modprobe sl4a-spi-hid`, **not** the normal
`modprobe sl4a-spi-amd` → HID activation sequence. Thus an HID
module could be loaded and report mode1 while no AMD SPI controller
was driving MSHW0231. Whether this is what happened on the unit
must be determined from **read-only** `lsmod`, ACPI/platform SPI driver
bindings, DKMS module revision, protocol counters and kernel logs.
A pending-kernel driver-build incompatibility is an alternative.

A source correction now loads AMD first, HID second and checks
both binding names before reporting a recovered driver, with a host
regression test. **This correction is not retroactive to the
already-running physical boot.** Stop mode4 cold-boot staging until
the user confirms real touchscreen functionality again.
No cold-boot PASS, functional Gate5 recovery PASS, or broad kernel34
compatibility may be claimed from the existing log.

## 2026-10-16 18:10 UTC: first one-shot mode4 cold-boot attempt INCONCLUSIVE

The physical tester staged the signed mode4 module at 18:08:35Z,
source checkout **`0c2fbf1ee9fa6fabeb0f7fe9d6f350329e92bd64`**,
signed module SHA256
`44d05f0a5e36eaaed3bcbc08897c7c77e2ded65e69c7aa1f4ce22947a9d6b83c`.
After actual full poweroff and new power-on, the one-shot late-boot
activation service ran at 18:10:35Z. Recorded stage and trial boot IDs
differed (`9a6e7959-92d2-4400-bd0a-7340aa488f50` vs
`1cd3ebae-96c0-4d4d-9073-85f8485d8d12`).

The boot hook consumed/removed its temporary service override, then
reported **`ERROR changed kernel / stale experiment`** and returned
to installed Gate5. A subsequent `coldboot-finish` printed
`Status: INCOMPLETE`, `Live mode: 1`; safe rollback left the
already loaded Gate5 in place. No rollback timer existed because the
hook exited **before** the experimental driver or timer could be armed.
Kernel events and stage/boot exact kernel strings were not in the
supplied diagnostic, so do not assert a definite kernel change yet.
The stage-to-boot timestamps are only **120 seconds apart**, suggesting
kernel mismatch (possibly a newly installed kernel selected on reboot)
over a genuine 24-hour expiration, unless the system clock moved.

**Source-side fix committed:** separate `INCONCLUSIVE_KERNEL_MISMATCH`,
`INCONCLUSIVE_STAGING_EXPIRED` and invalid timestamp verdicts with
exact expected/running kernels in the log; provide **read-only**
`coldboot-diagnose` including staged kernel, current `uname -r`,
staged module vermagic, age, boot IDs and hooks. Staging now refuses
when Ubuntu's known `/boot/vmlinuz` (or `/vmlinuz`) boot-default
symlink points at a different installed kernel from the running one,
rather than wasting a one-shot boot. The existing state machine
continues to fail closed and preserve Gate5. Updated host tests
reproduce distinct mismatch vs expiry and check no experimental
`insmod` or timer activation on either.

**Next physical action is READ-ONLY**, not another power cycle:

```bash
cd ~/SL4A_TouchScreen-host56
git fetch https://github.com/avgbob/SL4A_TouchScreen.git experiment/sl4-std-host56-set5
git switch --detach FETCH_HEAD
bash tools/experiments/host56-mode4.sh coldboot-diagnose
```

Inspect saved/running kernels and staging age before considering
restaging. No additional cold-boot evidence can be claimed yet.
The 16-gesture matrix, warm 3/3 and s2idle 2/2 are unaffected.

## 2026-10-16 cold-boot next step: reviewed one-shot stage (first physical attempt inconclusive; keep unchanged recovery profile)

**Safety rationale:** installed `sl4a-touch-activate.service` activates
after `multi-user.target` by design (early automatic ACPI binding
previously caused boot failures). Do NOT edit that service's original
unit, existing Gate5 `/etc/modprobe.d/sl4a-spi-hid.conf`, installed
DKMS modules, Secure Boot MOK, initramfs or boot loader. The experimental
one-shot helper adds **only**
`/etc/systemd/system/sl4a-touch-activate.service.d/90-mode4-once.conf`
with a replacement `ExecStart` targeting a root-owned helper.

**Staging** requires working loaded Gate5 mode1, an enabled known
activation unit with no competing drop-ins, correct MSHW0231 ACPI
hardware, correct kernel vermagic and signed mode4 module, manual
typed `ARM`, and complete root-only evidence staging. Stage copies
the signed module into `/var/lib/sl4a-mode4-coldboot/signed-mode4.ko`
without altering DKMS. **After staging, fully POWER OFF** using
`sudo systemctl poweroff`. Manually press the physical power button
after shutdown. A warm reboot would NOT qualify true cold startup.

**Next-boot one-shot:** the replacement boot service first refuses to
run on the staging boot. On the next boot it consumes/removes its own
drop-in *before driver insertion*, then arms an **independent 20-minute
systemd rollback timer**. It attempts a first mode4 HID load only if
**no HID module was loaded earlier** and the signed binary SHA256,
source version, kernel and staging age match. If the driver already
autoloaded earlier, the trial is **INCONCLUSIVE**; no warm swap is
permitted just to manufacture a pass. The trial's claimed first HID
load and boot ID are recorded.

**After login**, `coldboot-finish` checks that the current boot is the
new one and the exact signed mode4 is still loaded; operator confirms
`COLD` (physical power-off/power-on), then it runs the *existing
spoken and live event-gated* `quick` protocol. On success it records
one exact-build cold-start PASS and immediately restores installed
Gate5 mode1. On a normal failure it restores Gate5 and marks the
run INCONCLUSIVE. If the terminal dies, the independent timer attempts
recovery. If the machine must be hard rebooted, the already-consumed
drop-in is absent and **the original Gate5 startup service resumes**
automatically. No cold PASS is asserted without physical operator
confirmation, preserved trial boot identity, first HID insertion and
actual gesture/checksum evidence.

**Operator sequence (on the Surface):**

```bash
cd ~/SL4A_TouchScreen-host56
git fetch https://github.com/avgbob/SL4A_TouchScreen.git experiment/sl4-std-host56-set5
git switch --detach FETCH_HEAD
bash tools/experiments/host56-mode4.sh coldboot-stage
# Read the displayed safety instructions, type ARM if accepted.
sudo systemctl poweroff
# Wait until actually off, then press the physical power button.
# Log in to the SAME user desktop/terminal:
cd ~/SL4A_TouchScreen-host56
bash tools/experiments/host56-mode4.sh coldboot-finish
# Type COLD only if physically powered off; follow spoken quick cues.
```

Before shutdown, cancel safely with `bash
tools/experiments/host56-mode4.sh coldboot-cancel`. For inspection
`coldboot-status` is read-only. If boot unexpectedly fails, use a
recovery shell to remove just
`/etc/systemd/system/sl4a-touch-activate.service.d/90-mode4-once.conf`,
reload systemd if appropriate, and reboot normally; never remove the
Gate5 original service or DKMS modules.

**Acceptance remains PENDING until the real hardware run.**
No user machine was altered by preparing these source files in GitHub.
An independent exact-head `upstream/std-capimg-mt` (PR #87) test
must follow and must not inherit the mode4 result.

## Latest result — 2026-10-16 17:34–17:39 UTC: mode4 **s2idle 2/2 PASS**

**Physical test:** Surface Laptop 4 AMD / kernel `7.0.0-31-generic`,
exact checkout **`dc39813`**. Temporary existing-MOK-signed mode4
driver SHA256:
`de10c9769ec97b51a91dd86fcef6570e9f1dd205f4a82303339d773c8d7e7304`.
Main immutable session:
`~/sl4a-hardware-runs/mode4-s2idle2-20261016T173414Z`.

Both suspends used the **same loaded mode4 module** (no module reload
between cycles). The corrected harness observed genuine
`CLOCK_BOOTTIME - CLOCK_MONOTONIC` sleep gaps,
checked `PM: suspend entry (s2idle)` and `PM: suspend exit`
kernel markers, confirmed the driver remained in mode4, and
required a **heard spoken post-wake checkpoint** before gesture tests.
The full short event-gated `quick` gesture chain passed after **each**
resume; source identity, counters, resets, dropped frames and
capture checksums passed in both trace bundles.

| Cycle | Actual measured suspend | Event-gated post-wake trace | Result |
| --- | --- | --- | --- |
| 1 | **5.238 seconds** | `mode4-quick-20261016T173525Z` | PASS |
| 2 | **23.315 seconds** | `mode4-quick-20261016T173808Z` | PASS |

Final transcript confirmed `S2IDLE 2/2`, all main-session
`SHA256SUMS.txt` entries verified, **Gate5 mode 1 restored** and
the permanent boot profile unchanged.

**Qualification summary, exact physical-unit code only:** full planned
gesture coverage (across independent sessions); **warm reload 3/3**;
**real s2idle 2/2**. The three completed lifecycle groups are
independently evidence-backed, but **true cold power-on in mode4 is
still untested**, as are unrelated upstream PR #87 and other machines.
Do not default-enable mode4.

**Next:** design/review a safe *one-shot true cold-power-on* experiment
with an independently timed, boot-persistent rollback and recovery
path before changing any startup configuration. A normal reboot or
poweroff presently loads the working Gate5 mode1 and **is not** a
mode4 cold boot test. Do not alter DKMS, Secure Boot keys or boot
parameters casually for this last test.

## 2026-10-16 17:06 UTC: FIRST s2idle attempt INCONCLUSIVE (script timing race)

The tester ran `qualify-s2idle2` from exact checkout **`81a633c`**
with freshly signed temporary mode4 module SHA256
`b4e108dfd449169a294ea1e73c682185bb1accd5c105ceefec587f6d07a64e88`.
The first spoken **pre-sleep** cue played successfully and the operator
confirmed sleep. The transcript then reported:

```
=== ENTERING REAL S2IDLE CYCLE 1/2 ===
SUSPEND CLOCK CHECK: 0.000s of boottime-not-monotonic elapsed
SUSPEND CLOCK CHECK: FAIL; actual sleep time unproven
```

**No post-wake voice, live touch checks, or second suspend were ever
executed.** The script restored installed Gate5 mode1 successfully.
`0.000s` does not prove the firmware or driver failed to resume; the
harness incorrectly assumed `systemctl suspend` returning meant the
system had already completed suspension. A suspend request can be
queued/return before true sleep; the immediate clock sample can thus
preempt the actual sleep. Kernel PM logs from the device are needed to
determine whether/when the OS actually slept.

**Historical incident (subsequently corrected and physically passed 2/2):** poll
`CLOCK_BOOTTIME - CLOCK_MONOTONIC` until a proven >=2-second suspend
gap appears, bounded to 75 seconds of awake time. On timeout,
preserve kernel PM log and fail INCONCLUSIVE with voice when possible.
On verified wake, collect kernel PM entry/exit, then give a fresh
spoken prompt with **mandatory YES confirmation that it was heard**,
retrying an unavailable audio service rather than silently advancing.
Only after this explicit post-wake audio checkpoint can the spoken
event-gated `quick` test begin. Keep production Gate5 boot profile
unchanged and do not claim 1/2 or 2/2 s2idle acceptance yet.

## Latest result — 2026-10-16 16:49–16:55 UTC: mode4 warm reloads **3/3 PASS**

**Hardware:** original Surface Laptop 4 AMD 13.5-inch, kernel
`7.0.0-31-generic`. **Exact Git checkout:** `3fb72d4`.
**Exact enrolled-MOK-signed temporary module SHA256:**
`71a03f648c17699610f1f02ae5d59baf813fb75c0dffa78ca428b8edb005d680`.
The wrapper built and signed once, and printed the *identical hash* before
each of the three separate driver activations. On every activation
`std_raw_transition=4`, `reset_rsp=1`, `device_desc=1`,
`rpt_desc=1`, `frames_dropped=0` before touch.
Each of three **separate** short spoken/actual-evdev sessions passed
one-finger movement+release, same-two-finger pinch, expansion and release.
Each collector reported source/signature identity, no post-activation reset
or dropped frame during gestures, and checksum checks PASS. After each
cycle the **unchanged installed Gate5** driver was reloaded and
`std_raw_transition=1` independently confirmed.

| Warm activation | Original evidence folder | Result |
| --- | --- | --- |
| 1 | `mode4-quick-20261016T164955Z` | PASS, Gate5 restored |
| 2 | `mode4-quick-20261016T165148Z` | PASS, Gate5 restored |
| 3 | `mode4-quick-20261016T165325Z` | PASS, Gate5 restored |

All under `~/sl4a-hardware-runs/`. **Warm-reload acceptance: 3/3
PASS for exact tested code `3fb72d4` only.** Do not treat these as
true cold power-ons, S0ix/s2idle resume evidence, or acceptance of
upstream PR #87, which uses a different activation sequence/SHA.

**Next physical task:** two s2idle/resume cycles with mode4 intentionally
remaining loaded over actual platform sleep, audible post-wake event-verified
`quick` check for each cycle, startup/resume sysfs and journal evidence,
and final Gate5 rollback. Reboot while mode4 is temporary still loads the
production Gate5 boot profile. Mode4 cold-boot qualification needs a
separate controlled persistent opt-in; do not change boot config yet.

## Latest result — 2026-10-16 16:38 UTC: all remaining contacts PASSED

**Physical Surface, exact checkout `14a8991`**, signed mode4 binary SHA256
`f6de86ede8ee9d05adbce85ad842aa0aa2f202d7ad85d1c37976d840a86eef0e`.
Original immutable evidence folder:
`~/sl4a-hardware-runs/mode4-contacts-20261016T163800Z`.

The focused `qualify contacts` session completed **7/7 audio-cued,
event-gated phases** with explicit pass acknowledgments:
`contacts-one`, `contacts-two`, `contacts-three`,
`contacts-four`, `contacts-five`, `contacts-one-lift`, and
`contacts-recontact`. The run's own final integrity verdict reports
live input gates, exact source/binary identity, no disallowed resets or
frame drops, and checksum validation **PASS**. The original installed
Gate5 mode1 was automatically restored; the persistent modprobe profile
was unchanged. All these observations refer to **one warm module
activation**, not a cold-boot or suspend test.

Combined with 2026-10-16 16:17 event-gated `quick` and `pinch`
phases 1–8 plus the independently audited original-pair
`[3,4] → [4] → []` release at phase 9, we have **coverage of the
entire planned 16-gesture behavioral matrix across separate runs**.
Do **not** claim a single uninterrupted 16/16 session or merge-ready
lifecycle qualification, and do not transfer mode4 evidence directly to
Syax89 PR #87's distinct GET6-write-only source.

**Next hardware batch:** three clean *warm reloads* with the same
mode4 kernel driver SHA and a short voiced `quick` verification
after each, then two s2idle/resume cycles with identical identity,
counters and rollback discipline. Genuine mode4 cold boot requires an
explicit safe persistent opt-in and rollback; a normal reboot would
instead load Gate5 mode1.

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

### 2026-10-16 15:52 UTC: live-monitor smoke PASSED on Gate5

The physical Surface tested the voice-guided monitor at local checkout
`6de0b1a` with installed `std_raw_transition=1`. Spoken TTS preflight was
confirmed, the read-only monitor opened `/dev/input/event15` and reported
READY, and its `quick-one` phase correctly detected one-finger movement
and the subsequent release before announcing PASS. The working driver was not
changed. This establishes physical **audio + monitor + evdev startup and
single-touch gating**, not the full test collector, two-finger ID continuity,
or mode4 qualification. Original operator terminal transcript is retained
outside the repo.

The preceding mode4 guided run at 15:39 UTC did *not* reach a gesture:
the monitor failed with `sudo: a password is required`; its collector status
`completed` must not be treated as a gesture pass. The current runner now
refreshes privilege before the live monitor is opened and handles credentials
after hands are off.

**Next physical unit use:** the read-only Gate5 one-finger monitor has
passed, so run **one** `bash tools/experiments/host56-mode4.sh qualify full`
from the refreshed experimental checkout. This builds/signs mode4, temporarily
loads it, begins the `full` spoken/event-gated recording with the `quick`
sequence first, and restores Gate5 using a subshell EXIT trap even if a
phase fails. Do **not** run redundant `capture quick` and `capture full`
separately on the first qualification. Each phase must be observed before
the next starts; a failure stops and preserves evidence. This is still
unqualified on the new runner until the physical recording passes.
Gate5/PR87 exact-head qualification remains a separate lane.

### 2026-10-16 ~16:02 UTC: corrected-mode4 guided run partially PASSED

Physical checkout `fad839f` loaded a temporary, enrolled-MOK-signed
`std_raw_transition=4` module, digest
`f50dfa33d59221bc985a095d8f9359e12969a31ffcfaab9a07e19e9a3943cda4`.
Spoken voice, live evdev monitor and read-only collector all started.
The event-gated `quick-one` (movement + lift) **PASSED** and
`quick-pinch` (two-finger closing motion) **PASSED** on this corrected
mode4 implementation. On `quick-expand` the monitor reported *tracking
IDs changed*, repeated the **same continuation** three times and correctly
terminated as INCONCLUSIVE. The original Gate5 mode1 was restored
automatically. These are **two qualified gesture-level observations**, not
a complete acceptance or a demonstrated kernel tracking defect.

**Test design defect confirmed in source:** the runner delayed a connected
same-finger expansion by playing a full voiced 5–1 countdown, multiple long
prompts, and an acknowledgement while expecting that pair to remain down.
Moreover, a continuation retry retained the old pair without restarting
the initial pinch. It cannot determine from the terminal transcript whether
the physical user lifted/repositioned during the gap or the kernel lost its
tracking IDs; the saved `live-evdev.jsonl` can establish *when* the
transition occurred but not the operator's hand position.

Fixes on the experimental branch:
- Continuous pinch→expand→hold→lift prompts are short and **skip the full
  countdown**. Normal independent tests still count down aloud.
- The verifier consumes **every frame since the preceding accepted pair**
  including events during spoken instructions; no interval is thrown away.
- Changing contact IDs or losing contacts during a connected gesture is an
  irreversible **INCONCLUSIVE**, not a retry of expansion against stale IDs.
- Host tests simulate a successful uninterrupted contact chain and a
  finger lift **during the voiced transition**, rejecting the latter.
- Read-only `audit_voice_gap.py` summarizes the already-preserved original
  evdev evidence and phase timestamps without requiring another physical
  test or exposing gesture coordinates.

**Saved evidence audit completed (2026-10-16):** local run
`mode4-full-20261016T155826Z` reported original pinch IDs `[1, 2]`.
The *first* loss was an all-contacts-up frame **+3.114 s after pinch
PASS**. The next expansion instruction began **+13.65 s** after PASS,
and expand GO was **+19.67 s** after PASS. Thus the observed loss occurred
**10.54 seconds before the next instruction began** and **16.56 seconds
before its GO**. The input event stream contains 234 frames during the
voice instruction interval, confirming the monitor was receiving events.
Later attempts contributed 1,271 frames with different tracking IDs;
these do **not** establish 1,271 separate physical failures.

**Interpretation:** the old operator/voice timing makes this run invalid
as a continuous-finger endurance test. The evidence proves the original
pair disappeared **during the voice gap**, but alone cannot decide
whether the tester lifted their fingers, the kernel tracker released
them, or the controller stopped sensing them. Do **not** diagnose a
driver MT-ID regression from the interval or count data alone.

**Next physical action:** with the corrected no-long-countdown runner
at an exact green-CI SHA, perform **one** new
`bash tools/experiments/host56-mode4.sh qualify full` from a refreshed
worktree. The first four actions are the shortest proof of continuity
and remaining multi-contact tests continue only on verified success.
This is a fresh hardware qualification; the prior two successful
gesture-level observations remain historically valid but do not
qualify sustained tracking. Gate5 rollback remains automatic.

### 2026-10-16 ~16:18 UTC: continuous gestures reached final two-finger release

The latest physical run at checkout `5cba3b5`, evidence
`mode4-full-20261016T161746Z`, used a Secure Boot-signed, temporary
mode4 module (signed binary SHA256
`84086c66654f20163b3db5c34ceb7af9ed82670b2cb36d6567c6e91dde49890c`).
The one-finger gesture, the full **quick pinch→expand→release**, then the
second **far→close→hold→expand** chain were each event-gated and
advanced successfully. On `pinch-lift` (test 9 of 16), the test runner
rejected `Different tracking IDs before release` and stopped as
**INCONCLUSIVE**. Installed Gate5 mode 1 was automatically restored.
No full 16-test or cold/s2idle acceptance has been claimed.

**Verified harness issue:** the old release verifier required the
original **two-ID set** until an entirely empty frame, which wrongly
rejects a natural two-finger lift that emits
`{A,B} → {A} → {}` or `{A,B} → {B} → {}`.
A new gate permits only monotonically shrinking **subsets of the original
IDs**, ultimately requiring the empty frame. New, substituted, or
previously released-and-reappearing IDs remain hard failures.
Independent host tests cover both valid sequential release and real
tracking-ID substitution.

**Saved-evidence audit CONFIRMED (2026-10-16):** from
`mode4-full-20261016T161746Z`, final expansion's original IDs
were **[3, 4]**. The release instruction began +0.550s after expansion
PASS and the release phase began +2.812s. The recorded evdev sequence
is **[3,4] → [4] at +2.953s → [] at +2.963s**. Of the 20
frames examined, **no unexpected new tracking ID** was observed
during release. The old gate definitively **false-rejected a normal
sequential two-finger lift**. This closes the specific release-identity
question on the original evidence (not an end-to-end full qualification).
A fixed validator and host regression test already passed CI.

To save physical-unit time, **do not rerun the eight working gestures**
simply to reach the seven untouched `contacts` cases.
Finish those with a separate spoken `qualify contacts` session on
the same experimental driver path, with Gate5 restored automatically.
Keep the first eight observations and this audit independently labeled;
do not claim one uninterrupted full 16-test run has passed.

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
- Independent new-contact gestures receive full audible countdowns;
  consecutive same-two-finger movements get **immediate spoken transitions**
  without a 5-second pause. A broken contact chain cannot be "retried"
  by reattempting only the final movement.

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
- [x] **Mode4 runner CI green at `8f35baf7f9`**, including whitespace,
      ordinary + sanitizer host tests, Ubuntu and current-kernel module builds:
      [workflow run](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/38926965135).
      Reverify if the branch head changes before a physical run.
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

### Upstream PR review responses (software only)

The five test/diagnostic findings from Syax89's 2026-10-16 review are
corrected on their **separate existing draft branches** and green in fork CI:

- **#87**, `2bf81e8`: GCC 14 host kernel-stub warnings exempted narrowly;
  production DATA handler stays extracted and `-Werror` stays enabled.
  [CI](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/38925909979).
- **#88**, `9cc5cc0`: 3456-byte fixture teardown fixed; replay-only
  ghost-radius now uses the production active-slot scale.
  [CI](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/38925926108).
- **#89**, `879a13d`: correct rotation-help warning string, single
  temporary DKMS config prefix substitution, real last-drop-in-wins test.
  [CI](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/38925987371).

All three CI gates include normal and sanitizer host suites and two external
module builds. These results **do not qualify** hardware lifecycles or
Secure Boot installation. Replies with the SHA and CI proof were posted
to the respective upstream PRs; they remain draft for independent review.

**New first physical step:** run the read-only
`tools/hardware_evidence/verify_live_monitor.py` smoke check on the
**currently working Gate5**, before building or reloading mode4. It tests
spoken instructions, sudo, exact input-node selection, live one-finger
movement and release; it does NOT modify the module, MOK or DKMS profile.
Only proceed to the full mode4 battery after this smoke check passes.

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

**Current next physical action:** mode4 true cold-power-on qualification
requires a reviewed boot-time, automatically self-reverting one-shot setup.
Do not repeat already-passed mode4 quick/contacts/warm/s2idle test
batches merely to reach this stage. PR87 exact-head hardware
qualification is an independent track and follows only with its
own proven loader and exact-source evidence.
