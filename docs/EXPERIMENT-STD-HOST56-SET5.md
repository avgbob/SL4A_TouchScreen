# MSHW0231 standard-transport host-0x56/no-GET6 activation A/B

**Status:** experimental, **not hardware-qualified** on this branch. The
existing Gate5 mode 1 remains the installer default and the only qualified
profile on the original test unit. Do not change the installer, DKMS registration,
or the boot modprobe file for this experiment.

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
changes have host regression tests. A read-only
`tools/hardware_evidence/audit_release.py` checks the saved
`mode4-full-20261016T161746Z` frames to distinguish a valid singleton
from a genuinely substituted tracking ID **before another physical run**.
Do not qualify remaining contacts, cold boot, reloads or suspend until
their respective tests have actually passed.

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
