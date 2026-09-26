# Quickstart

Get SL4A TouchScreen running on a Surface Laptop 3/4 AMD system.

## 1. Install

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
sudo ./tools/sl4a-touch.sh install
```

The standard installer profile is device-aware:

- **Surface Laptop 4 AMD / MSHW0231:** Gate5 standard transport + CapImg
  multitouch (input-quality beta). Normal HID discovery runs first, then the driver writes GET6,
  waits 4.5-5.5 ms and sends SET5 to start CapImg.
- **Surface Laptop 3 AMD / MSHW0162:** conservative standard HID profile.
  Gate5 activation is not claimed on this device.
- SL4 multitouch is provided by the default standard Gate5 profile.
- `--raw` is retained only as a legacy diagnostic/research transport and is
  not required for multitouch.

## 2. Secure Boot

If Secure Boot is enabled, the installer resolves the **actual DKMS signing
identity** first (including distro defaults and `framework.conf` overrides),
validates the key/certificate pair, and reuses an already-enrolled certificate
when possible. Ubuntu normally uses
`/var/lib/shim-signed/mok/MOK.priv` + `MOK.der`; other DKMS installations
may use `/var/lib/dkms/mok.key` + `mok.pub`.

If the resolved certificate is not enrolled, the installer prints its exact
path and can stage it with `mokutil`. To do that manually, use the path the
installer printed:

```bash
sudo mokutil --import /path/printed/by/the/installer
sudo reboot
```

At MOK Manager select **Enroll MOK -> Continue -> Yes**, enter the one-time
password, then reboot. Do not assume `/var/lib/dkms/mok.pub` on Ubuntu.

## 3. Activate / reboot

The installer creates a late-boot systemd activation unit ordered after
`multi-user.target`. You can also bind the modules manually:

```bash
sudo ./tools/sl4a-touch.sh activate
```

Keep a local console or remote shell available while testing a reverse-
engineered kernel driver.

## 4. Verify

```bash
./tools/sl4a-touch.sh status
cat /sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats 2>/dev/null || true
cat /sys/class/input/input*/name | sort -u
```

On a Gate5 MSHW0231 install, expect the standard HID device plus the CapImg
multitouch node **`MSHW0231 Touchscreen`** (input-quality beta). On MSHW0162, expect the
conservative standard HID path. Selecting `--raw` is a separate legacy
diagnostic choice, not the production multitouch configuration.

For an evidence bundle:

```bash
sudo ./tools/sl4a-touch.sh logs
```

## 5. Recovery

If activation leaves the panel unusable:

```bash
sudo modprobe -r sl4a-spi-hid sl4a-spi-amd
sudo reboot
```

The SL4A modules export no automatic hardware aliases; the installer-created
service is what rebinds them after boot.

## Current Qualification Scope

The Gate5 MSHW0231 path at hardware checkpoint `58f0231` passed one true cold
power-on + touch cycle, three consecutive warm reload + touch cycles, and two
s2idle resume + touch cycles on the tested Surface Laptop 4 AMD, with zero
observed frame drops and no unexpected post-DONE reset in those captures.
The installer/lifecycle path also passed a Secure Boot reboot using the existing
enrolled Ubuntu DKMS MOK, with both modules signed and automatic Gate5
activation after boot.

That is a **single-unit field qualification**, not a broad compatibility
guarantee. Pen, palm rejection, long stress, the full 1-5 finger matrix, and
Gate5 behavior on MSHW0162 remain outside the claim. See
`docs/GATE5-QUALIFICATION.md`, `docs/SUPPORT.md`, and
`docs/COMPATIBILITY.md`.
