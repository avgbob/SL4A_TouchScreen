# Quickstart

Get SL4A TouchScreen running on your Surface Laptop 3/4 (AMD) in 5 steps.

## Prerequisites

- Linux kernel **6.x+**
- Kernel headers installed (`linux-headers` or `kernel-devel` matching `uname -r`)
- **DKMS** (`dkms` package)
- **Git**

## 1. Install

```bash
git clone https://github.com/Syax89/SL4A_TouchScreen.git
cd SL4A_TouchScreen
sudo ./tools/sl4a-touch.sh install
```

Prompts for a profile (standard HID, the supported default, or the
experimental raw multitouch profile) unless `--standard`/`--raw` is given.

## 2. Secure Boot

The installer handles everything automatically — if Secure Boot is enabled,
it generates the DKMS signing key and walks you through enrolling it. You just
need a temporary password (used once at the next boot).

If you skipped the enrollment prompt during installation:
```bash
sudo dkms generate_mok
sudo mokutil --import /var/lib/dkms/mok.pub
sudo reboot
```

At the blue MOK Manager screen: **Enroll MOK → Continue → Yes → enter password → Reboot**.
After login the driver activates automatically.

## 3. Activate

Only after login, with a local console or remote shell available:

```bash
sudo ./tools/sl4a-touch.sh activate
```

The script binds the SL4A controller and HID transport. Keep shell access
available in case recovery is needed.

## 4. Verify

```bash
./tools/sl4a-touch.sh status
```

Shows the installed version, active profile, and whether the driver is
currently loaded and bound — no root required. Or check manually:

```bash
ls /sys/bus/spi/devices/          # the controller enumerates as spi-MSHW0231:00 (or spi-MSHW0162:00)
cat /sys/class/input/input*/name | sort -u    # the touch input node is named "spi 045E:0C19"
```

Look for the input node named `spi 045E:0C19` in the standard installer
profile. The heatmap multitouch pipeline (raw mode or the experimental
standard-transport beta bridge) names its node `MSHW0231 Touchscreen`. If
something looks wrong,
`sudo ./tools/sl4a-touch.sh logs` collects a diagnostic bundle to attach to a
bug report.

## 5. Recovery

If the touchscreen becomes unresponsive after activation:

```bash
sudo modprobe -r sl4a-spi-hid sl4a-spi-amd
sudo reboot
```

The system boots with the in-tree `spi-amd` driver and no SL4A module loaded.
Force-reboot if the unload fails.

## What to Expect

- **Single-touch only** in the standard installer profile (the default).
  Packaged experimental multitouch is available with `--raw`. A separate
  manual standard-transport SET5 beta bridge was used for the targeted SL4 AMD
  tracker qualification; see `docs/STANDARD-SET5-MULTITOUCH.md`.
- The standard input node is **`spi 045E:0C19`**. The heatmap multitouch
  pipeline (raw mode or the beta bridge) uses `MSHW0231 Touchscreen`; the
  controller itself is `spi-MSHW0231:00` (SL3: `spi-MSHW0162:00`).
- A **stylus/pen input node is published** but remains untested — pen input
  behavior has not been qualified.
- **No palm rejection or pen qualification.** All heatmap multitouch profiles
  remain experimental and are not release-qualified.
