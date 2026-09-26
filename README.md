# SL4A TouchScreen

Linux touchscreen driver for the **Microsoft Surface Laptop 4 AMD** and
**Surface Laptop 3 AMD**, built around the AMD `AMDI0060` SPI controller and
Microsoft `MSHW0231` / `MSHW0162` HID-over-SPI devices.

[![Status](https://img.shields.io/badge/status-beta-orange)](https://github.com/avgbob/SL4A_TouchScreen)
[![Release](https://img.shields.io/badge/release-1.7.0-brightgreen)](VERSION)
[![CI](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/ci.yml/badge.svg)](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-GPL--2.0-blue)](LICENSE)

> [!WARNING]
> **Beta, reverse-engineered kernel driver.**
> Gate5 is field-qualified on one Surface Laptop 4 AMD unit, not a broad
> hardware/firmware/kernel compatibility guarantee. Keep recovery access
> available when installing or testing.

## What This Driver Does

On **Surface Laptop 4 AMD / MSHW0231**, the standard install path now combines
normal HID-over-SPI discovery with the panel's high-resolution CapImg stream:

```text
ACPI _PS0 -> _RST
        |
RESET_RSP
        |
DEVICE_DESC
        |
936-byte HID report descriptor
        |
register normal HID device
        |
write GET_FEATURE report 6
        |
do not synchronously read the GET6 body
        |
wait ~4.5-5.5 ms
        |
SET_FEATURE report 5 = 1
        |
0x0c CapImg / heatmap frames
        |
beta in-kernel multitouch tracker
        |
MSHW0231 Touchscreen Linux MT input
```

The important difference is that **multitouch no longer requires abandoning the
normal HID discovery path and booting the SL4 into a separate `raw_mode=Y`
configuration**. The driver discovers and registers the real HID device first,
then transitions the panel into the CapImg stream and publishes multitouch from
that stream.

The standard SL4 profile therefore keeps:

- normal HID descriptor discovery and HID registration;
- the real 936-byte report descriptor read from the panel;
- the standard HID device, including the descriptor-created stylus interface;
- the high-resolution CapImg stream for touch;
- the beta multitouch tracker exposed as `MSHW0231 Touchscreen`.

The stylus HID node is created, but **pen behavior is not yet qualified**.

## What This Fork Adds

This fork builds on the original
[Syax89/SL4A_TouchScreen](https://github.com/Syax89/SL4A_TouchScreen)
foundation: AMD FCH SPI support, HID-over-SPI transport work, CapImg acquisition,
and the original raw-touch pipeline.

The current SL4 path adds the pieces needed to make those parts behave as one
repeatable driver lifecycle:

| Area | Current behavior |
| --- | --- |
| **SL4 startup** | Normal HID discovery followed by the Gate5 GET6-write → ~5 ms → SET5 transition |
| **Multitouch** | CapImg frames are processed by the beta tracker while the normal HID transport remains registered |
| **Early-frame race** | Once a DATA header is consumed, its body is drained even if HID registration is still in progress |
| **Warm reloads** | The HID-registration DATA-drain race that could leave a ~4.3 KB frame queued was fixed |
| **Suspend** | Explicit `_PS3` panel power-down |
| **Resume** | Explicit `_PS0 -> _RST`, descriptor rediscovery, then the qualified Gate5 transition again |
| **Installer** | Device-aware: MSHW0231 receives the Gate5 SL4 profile; MSHW0162 keeps the conservative standard profile |
| **DKMS / boot** | Installs through DKMS and enables a post-`multi-user.target` systemd activation service |
| **Diagnostics** | `status`, `logs`, protocol counters, installed-build stamping, and profile verification are built into the tool |

## Current Qualification

The Gate5 production path has been exercised on **one physical Surface Laptop 4
AMD / MSHW0231 unit**.

| Test | Result |
| --- | --- |
| True cold power-on + touch | PASS |
| Warm module reload + touch | 3/3 PASS |
| s2idle suspend/resume + touch | 2/2 PASS |
| Production DKMS install/profile generation | PASS |
| Normal reboot + automatic systemd activation | PASS |
| Installed profile vs running parameters | MATCH |
| Unexpected post-DONE controller resets in qualification captures | 0 |
| Observed transport frame drops in qualification captures | 0 |

The broader **E1 input-quality campaign is still in progress**. Close-contact
tracking, crossing-finger identity, 3-5 finger behavior, palm rejection, stylus
correctness, mixed pen/touch input, long-duration stress, and broader
hardware/kernel coverage are not yet release claims.

See [`docs/GATE5-QUALIFICATION.md`](docs/GATE5-QUALIFICATION.md) for the
qualified activation/lifecycle evidence and
[`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) for the evidence matrix.

## Supported Hardware

| Device | ACPI IDs | Standard installer behavior | Status |
| --- | --- | --- | --- |
| **Surface Laptop 4 AMD** | touch `MSHW0231`, SPI `AMDI0060` | Gate5 standard-transport CapImg multitouch | Field-qualified on one unit |
| **Surface Laptop 3 AMD** | touch `MSHW0162`, SPI `AMDI0060` | Conservative standard HID: `raw_mode=N wire_double_opcode=1` | Gate5 sequence not claimed |

The tested SL4 HID identity is Microsoft VID/PID `045e:0c19`. The SL4 heatmap
geometry is 72×48 cells; SL3 uses its own device-specific geometry selected by
ACPI ID.

Other Surface models, other `MSHW*` touch devices, and other AMD SPI
controller IDs are not supported by this release.

## Install

Read [`docs/SUPPORT.md`](docs/SUPPORT.md) first.

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen

# Read-only hardware/build preflight
./tools/sl4a-touch.sh install --check

# Install the device-aware standard profile
sudo ./tools/sl4a-touch.sh install
```

The installer:

1. checks the supported ACPI hardware;
2. stages and builds the two modules through DKMS;
3. writes the device-appropriate `/etc/modprobe.d/sl4a-spi-hid.conf`;
4. enables `sl4a-touch-activate.service`;
5. activates the driver immediately when safe to do so;
6. verifies the driver is actually bound.

The boot service starts **after `multi-user.target`**, not during early kernel
boot. This keeps the experimental modules out of the fragile early-boot
auto-binding path and leaves a working userspace recovery environment if
activation fails.

### Secure Boot signing

Secure Boot handling is built into the installer. When Secure Boot is enabled,
the installer validates **both** `/var/lib/dkms/mok.key` and
`/var/lib/dkms/mok.pub`, verifies that the private key and certificate are a
matching pair, normalizes a PEM certificate to DER when needed, and checks the
certificate's MOK enrollment status.

If a valid pair already exists, the default is to **reuse it** for the newly
rebuilt DKMS modules. Interactive installs also offer to generate a new pair or
import another existing pair. Use `--rotate-mok` for an explicit scripted key
rotation. Before replacement, existing MOK material is preserved under a
root-only `/var/lib/dkms/sl4a-mok-backup-*` directory.

If only one half of the pair exists, the material is invalid, or the private
key and certificate do not match, the installer will not treat it as usable.
Interactive installs offer repair choices; non-interactive installs stop unless
rotation was explicitly requested. A newly generated or imported certificate
that is not already enrolled is staged through `mokutil`, and driver
activation is deferred until the MOK Manager reboot completes.

The complete Secure Boot install → enrollment → reboot → automatic activation
path is implemented but **has not yet been hardware-qualified as a compatibility
row** on the current SL4 Gate5 campaign.

### Status and logs

```bash
./tools/sl4a-touch.sh status
sudo ./tools/sl4a-touch.sh logs
```

`status` reports the DKMS version, the commit the installed modules were built
from, configured and running profiles, hardware presence, module state, and boot
activation state.

### Manual activation

```bash
sudo ./tools/sl4a-touch.sh activate
```

The activation command refuses to displace another driver already bound to the
target controller/touchscreen.

### Recovery

```bash
sudo modprobe -r sl4a-spi-hid sl4a-spi-amd
sudo reboot
```

See [`docs/ROLLBACK.md`](docs/ROLLBACK.md) for the complete rollback and upgrade
procedure.

## Qualified SL4 Profile

The standard installer writes this profile for `MSHW0231`:

```text
options sl4a_spi_hid \
  raw_mode=N \
  raw_input_beta=Y \
  wire_double_opcode=1 \
  gate3_observe_only=1 \
  skip_std_getfeat=1 \
  std_raw_transition=1 \
  get_noread=0 \
  getfeat_delay_ms=0 \
  std_liveness_ms=0 \
  std_liveness_recover=0 \
  wait_reset_kick_ms=0
```

For `MSHW0162`, the standard installer deliberately remains conservative:

```text
options sl4a_spi_hid raw_mode=N wire_double_opcode=1
```

The explicit `--raw` installer profile remains an **experimental diagnostic
path**. It is not the production SL4 qualification path.

## Why the Gate5 Sequence Matters

During qualification, several similar-looking activation sequences behaved
differently:

- SET5-only can enter CapImg and remains useful historical evidence.
- GET6 write → ~5 ms → SET5 repeatedly entered CapImg.
- Full synchronous GET6 read → SET5 caused a controller reset on the tested
  machine.
- A separate warm-reload reset was traced to the first CapImg DATA body being
  left queued while `hid_add_device()` was still running.

Gate5 fixes the second problem independently of activation timing: after the
driver consumes a DATA header, it drains/processes the corresponding body even
while HID registration is still active. Publication into the HID core remains
suppressed until registration is ready.

That transport-synchronization fix is what made repeated warm activation
reliable on the qualified machine.

## Power Lifecycle

The SL4 production lifecycle is:

```text
BOOT / LOAD
  _PS0 -> _RST
  -> descriptors
  -> GET6 write
  -> ~5 ms
  -> SET5
  -> CapImg

SUSPEND
  stop traffic
  -> _PS3

RESUME
  _PS0
  -> _RST
  -> rediscover descriptors
  -> GET6 write
  -> ~5 ms
  -> SET5
  -> CapImg
```

The tested Gate5 path survived two s2idle resume cycles with real touch after
resume.

## Touch Pipeline

The production SL4 path currently uses the **in-kernel beta heatmap tracker**.

At a high level:

```text
0x0c CapImg
   |
72x48 signal grid
   |
baseline / noise filtering
   |
peak detection + connected components
   |
blob splitting
   |
candidate-to-track assignment
   |
post-association ghost suppression
   |
smoothing / deadband / lift handling
   |
Linux multitouch slots
```

A key tracker change is the ordering of close-contact suppression: candidates
are associated to existing tracks first, then the strict proximity/ghost rule
is applied. That allows two nearby candidates backed by two established tracks
to remain separate instead of being pre-merged simply because they are close.

Detailed processing, thresholds, and tracker behavior live in
[`docs/PIPELINE.md`](docs/PIPELINE.md).

The repository also contains the experimental
[`userspace/sl4a-heat/`](userspace/sl4a-heat/) path. That remains architecture
research; it is **not** the current installed Gate5 production path.

## Known Limits

This release does **not** yet claim:

- Gate5 mode-1 activation on Surface Laptop 3 AMD / `MSHW0162`;
- validated stylus/pen behavior;
- palm rejection;
- complete 1-5 finger qualification;
- Windows-equivalent contact classification;
- long mixed-input stress;
- broad firmware, kernel, or distribution compatibility;
- support for other Surface models or other AMD SPI controller IDs.

## Development / Build from Source

For development without DKMS:

```bash
make -C /lib/modules/$(uname -r)/build M=$PWD/driver modules
sudo cp driver/sl4a-spi-amd.ko driver/sl4a-spi-hid.ko /lib/modules/$(uname -r)/updates/dkms/
sudo depmod -a
sudo ./tools/sl4a-touch.sh activate
```

Modules built manually this way are unsigned unless you sign them yourself.

## Documentation

| Document | Purpose |
| --- | --- |
| [`docs/QUICKSTART.md`](docs/QUICKSTART.md) | Short installation guide |
| [`docs/GATE5-QUALIFICATION.md`](docs/GATE5-QUALIFICATION.md) | Current SL4 Gate5 activation and lifecycle contract |
| [`docs/SUPPORT.md`](docs/SUPPORT.md) | Supported hardware and installer profiles |
| [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) | Evidence / compatibility matrix |
| [`docs/ACTIVATION.md`](docs/ACTIVATION.md) | GET6 / SET5 activation experiments and current Gate5 sequence |
| [`docs/HIDSPI_PROTOCOL.md`](docs/HIDSPI_PROTOCOL.md) | HID-over-SPI V0 transport |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | Heatmap and multitouch pipeline |
| [`docs/PARAMETERS.md`](docs/PARAMETERS.md) | Release, diagnostic, and experimental parameters |
| [`docs/TESTING.md`](docs/TESTING.md) | Reproducible test procedure |
| [`docs/EVIDENCE.md`](docs/EVIDENCE.md) | Evidence ledger and unresolved questions |
| [`docs/ROLLBACK.md`](docs/ROLLBACK.md) | Recovery and rollback |
| [`docs/HARDWARE_VALIDATION.md`](docs/HARDWARE_VALIDATION.md) | Hardware-validation procedure |
| [`docs/AMDI0060_CONTRACT.md`](docs/AMDI0060_CONTRACT.md) | AMD SPI controller boundary |
| [`userspace/sl4a-heat/README.md`](userspace/sl4a-heat/README.md) | Experimental userspace heat-processing work |

Historical Gate3/Gate4/mode-3 documents are intentionally retained. They record
how the final Gate5 sequence was discovered rather than being rewritten to look
like the final result was known from the beginning.

## License

**GPL-2.0**. See [LICENSE](LICENSE).
