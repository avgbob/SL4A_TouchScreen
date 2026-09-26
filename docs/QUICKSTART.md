# Quickstart

Get SL4A TouchScreen running on a Surface Laptop 3/4 AMD system.

## 1. Install

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
sudo ./tools/sl4a-touch.sh install
```

The standard installer profile is device-aware:

- **Surface Laptop 4 AMD / MSHW0231:** Gate5 standard transport + beta
  multitouch. Normal HID discovery runs first, then the driver writes GET6,
  waits 4.5-5.5 ms and sends SET5 to start CapImg.
- **Surface Laptop 3 AMD / MSHW0162:** conservative standard HID profile.
  Gate5 activation is not claimed on this device.
- `--raw` remains an explicit experimental raw-transport profile.

## 2. Secure Boot

If Secure Boot is enabled, the installer builds/signs through DKMS and guides
MOK enrollment. If enrollment is still pending:

```bash
sudo dkms generate_mok
sudo mokutil --import /var/lib/dkms/mok.pub
sudo reboot
```

At MOK Manager select **Enroll MOK -> Continue -> Yes**, enter the one-time
password, then reboot.

## 3. Activate / reboot

The installer creates a post-login systemd activation unit. You can also bind
the modules manually after login:

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

On a Gate5 MSHW0231 install, expect the standard HID device plus the beta
multitouch node **`MSHW0231 Touchscreen`**. On MSHW0162, expect the
conservative standard HID path unless you deliberately selected `--raw`.

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

That is a **single-unit field qualification**, not a broad compatibility
guarantee. Pen, palm rejection, long stress, the full 1-5 finger matrix, and
Gate5 behavior on MSHW0162 remain outside the claim. See
`docs/GATE5-QUALIFICATION.md`, `docs/SUPPORT.md`, and
`docs/COMPATIBILITY.md`.
