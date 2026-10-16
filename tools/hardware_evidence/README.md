# Hardware Evidence Collection

`collect.sh` is a read-only evidence harness for the Surface Laptop 4 AMD
touchscreen (`AMDI0060` and `MSHW0231`). It discovers ACPI, SPI, input, and
module sysfs nodes at collection time rather than relying on assigned device
paths. It does not install, load, unload, bind, configure, or otherwise alter
drivers or hardware.

`capture_direct_touch.sh` records a bounded `evtest` trace for the standard HID
direct-touch device. It identifies the HID-core node from `045E:0C19` ancestry
and direct-touch/absolute/touch capabilities; it never assumes an `eventN`
number.

`capture_beta_multitouch.sh` records the driver-owned heatmap multitouch bridge.
It requires the exact `MSHW0231 Touchscreen` input name plus multitouch
tracking capability (`ABS_MT_TRACKING_ID`), so a qualification run cannot
silently capture the standard HID node instead of the beta bridge.

`capture_stylus.sh` records a bounded `evtest` trace for the standard HID
stylus. It requires HID `045E:0C19` ancestry, an input name containing `Stylus`,
absolute X/Y, and pen-tool capability; it never assumes an `eventN` number.

`capture_linux_trace_bundle.sh` is the Phase 4 session collector. It provides a
bounded Linux counterpart to the Windows transaction evidence: a UTC-bounded
session window, host provenance, dynamically discovered ACPI/SPI/input state,
and a timestamped journal slice filtered to SL4A/SPI/HID/touch lines. Direct
 touch and stylus `evtest` captures are opt-in.

`run_blinded_session.sh` is the operator-facing wrapper for one opaque blinded
period and case. It calls the existing read-only collector and trace bundle
helpers, writes a worksheet and role-boundary instructions, and generates a
SHA-256 checksum list. It neither accepts nor reveals profile information.

## Audible, operator-guided physical qualification (2026-10)

For **interactive** contact-count and pinch tests, use
[`guided_session.py`](guided_session.py) rather than silently running
a bare `evtest` window. Our earlier ad-hoc terminal-bell countdowns
were not collected into a reusable test runner.

The guide:

- synthesizes **spoken English instructions offline** using
  `espeak-ng` (install with `sudo apt install espeak-ng` if missing) and
  plays them through `paplay`, `pw-play`, or `aplay`; refuses to begin
  unless the operator confirms hearing and understanding the voice;
- speaks a **5-4-3-2-1** countdown before each new gesture and announces
  contact-count/gesture progress without requiring screen scrolling;
- uses a second non-grabbing read-only evdev monitor to check actual
  tracking IDs, finger counts, release, pinch direction and continuity:
  **a timer cannot advance a test**. Missed gestures get up to three
  spoken retries, then the run is INCONCLUSIVE, not PASS;
- saves **UTC and monotonic phase markers**, live event JSONL, the original
  evtest recording, module/case identity, and before/after sysfs counters;
- requests an orderly early stop of the evidence collector after all
  gates pass, so the runner doesn't wait for its worst-case timeout;
- runs audio as the desktop user while invoking the collector under sudo
  for the privileged input-device read;
- requires a new evidence directory and verifies actual `evtest` events,
  not merely input device registration;
- cannot install/reload/unload the kernel module or change the boot profile.

Test the sound output **before** any module activation:

```sh
python3 tools/hardware_evidence/guided_session.py --audio-check
```

One first-pass, single-bundle sequence runs **all** quick, pinch and contact
cues with one audible preflight and one evtest recording:

```sh
python3 tools/hardware_evidence/guided_session.py \
  --protocol full --case warm-01-full \
  --output "$HOME/sl4a-hardware-runs/warm-01-full"
```

For subsequent warm reload/resume cases, use `--protocol quick`;
for a direct-touch control use `--protocol single --input-source direct`;
for pen use `--protocol stylus` (auto-selects stylus input).
The `--demo` option exercises printed cues **without sound/hardware**
for CI or script development only; a demo is not a qualification run.

**Spoken-mode prerequisite:** the earlier sound-check confirmed
the **tones** on this Surface, but that check does not prove `espeak-ng`
speech is installed or intelligible. Run the upgraded `--audio-check`
before activating experimental mode4. The voice-gated workflow has passed
host simulation; it is **pending its first real end-to-end Surface test**.

**Blinding caution:** these are expressly **unblinded hardware
engineering sessions**. They reuse the read-only collector but include
actual activation/driver metadata. Do not call them E1 blinded sessions
or infer compatibility from a single physical test. The [roadmap](../../docs/PHYSICAL-UNIT-ROADMAP-2026-10.md)
separates upstream PR87 exact-head acceptance, mode4 and future E1 tests.

## Usage

Run from the repository root. No privilege escalation is performed or needed
for the normal collection:

```sh
./tools/hardware_evidence/collect.sh
./tools/hardware_evidence/collect.sh --output /tmp/sl4a-evidence
./tools/hardware_evidence/capture_direct_touch.sh --duration 20 \
  --output evidence/run-1/p1-one-touch.evtest.txt
./tools/hardware_evidence/capture_beta_multitouch.sh --duration 20 \
  --output evidence/run-1/p1-beta-multitouch.evtest.txt
./tools/hardware_evidence/capture_stylus.sh --duration 20 \
  --output evidence/run-1/p1-pen.evtest.txt
./tools/hardware_evidence/capture_linux_trace_bundle.sh --duration 20 \
  --capture-direct-touch --capture-beta-multitouch --capture-stylus \
  --output evidence/run-1/p1-input-session
./tools/hardware_evidence/run_blinded_session.sh --period p1 --case one-touch \
  --duration 20 --capture-direct-touch --capture-beta-multitouch --capture-stylus \
  --output evidence/run-1/p1-one-touch
```

The blinded-session output directory must be new. Its `collection/` and
`trace/` subdirectories retain helper artifacts, while `operator/worksheet.txt`,
`session-status.txt`, `ROLE_BOUNDARIES.md`, and `checksums.txt` support the
operator and assessor workflow. The period label is restricted to `p1`, `p2`,
or `p3`; case names are opaque identifiers. No profile names or mappings belong
in the command or output tree.

The output directory must not already exist. It is created with owner-only
permissions. If kernel log access is restricted, the `dmesg` artifact records
the resulting error. Run the collector with access to privileged kernel logs
only when that log evidence is required; the collector itself never invokes
`sudo`.

The capture output must be a new file in an existing directory. It contains
the selected sysfs identity and capabilities followed by raw `evtest` output.
`evtest` is used only when already installed; the helper neither installs it
nor changes drivers. The caller may need existing permission to read
`/dev/input/eventN`; no privilege escalation is attempted. If a requested
input capture fails, the trace bundle now exits non-zero so the parent session
records `trace-failed` rather than reporting a misleading completed session.

The trace bundle directory must also be new. Its duration is limited to 1-3600
seconds and defaults to 20. `journalctl` and `/dev/input` can require privilege;
the caller may run this helper under `sudo`, but the helper never invokes it.
Restricted journal access is retained in `kernel/journal-sl4a-session.txt`.

## Artifact Layout

```text
sl4a-hardware-evidence-<UTC timestamp>/
  manifest.txt                     collection identity and artifact list
  provenance/                      kernel, OS, command line, DMI, Secure Boot
  modules/                         DKMS status, modinfo, loaded modules, parameters
  sysfs/                           discovered ACPI and SPI nodes and state attributes
  input/                           discovered input nodes and libinput/evtest availability
  kernel/dmesg-last-300.txt        bounded recent kernel-log slice
```

The Phase 4 bundle has this session-oriented layout:

```text
sl4a-linux-trace-<UTC timestamp>/
  manifest.txt                     format, UTC bounds, options, SHA-256 artifacts
  provenance/                      host, OS, kernel command line, matched modules, DMI
  sysfs/                           dynamically discovered ACPI and relevant SPI state
  input/                           dynamically discovered SL4A HID candidates and evtest trace
  kernel/journal-sl4a-session.txt  filtered, timestamped, line-capped journal window
```

`manifest.txt` is line-oriented: its header identifies format version, UTC
session bounds, requested options and direct-touch result, collector identity,
and safety contract. The
`artifacts_sha256` section lists SHA-256 and relative path for every artifact
except the manifest itself (a file cannot contain a stable checksum of itself).

The SPI evidence includes driver-exposed state attributes when present:
`ready`, `protocol_stats`, `baseline_status`, and `lifecycle_status`. Missing
or unreadable paths are recorded as evidence, not treated as collector errors.
