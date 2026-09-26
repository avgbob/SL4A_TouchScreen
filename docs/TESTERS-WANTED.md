# Testers Wanted — Surface Laptop 4 AMD / MSHW0231

The Gate5 production path is working on one qualified Surface Laptop 4 AMD /
MSHW0231 unit. The next most valuable step is **independent hardware testing**.

Latest release:
https://github.com/avgbob/SL4A_TouchScreen/releases/latest

Testing hub:
https://github.com/avgbob/SL4A_TouchScreen/discussions/10

Structured hardware report:
https://github.com/avgbob/SL4A_TouchScreen/issues/9

## Who should test

Please consider testing if you have a **Surface Laptop 4 AMD**, especially a
machine exposing:

```text
MSHW0231
AMDI0060
```

Check without installing anything:

```bash
grep -E 'MSHW0231|MSHW0162|AMDI0060' /sys/bus/acpi/devices/*/hid 2>/dev/null
```

Then run the read-only project preflight:

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
./tools/sl4a-touch.sh install --check
```

## What is already working on the qualified unit

- normal HID-over-SPI discovery
- real 936-byte report descriptor
- Gate5 activation: GET_FEATURE report 6 write → ~4.5–5.5 ms → SET_FEATURE report 5
- CapImg multitouch through the in-kernel tracker
- cold boot + touch
- repeated warm reload + touch
- s2idle suspend/resume + touch
- DKMS install
- Secure Boot with the existing enrolled Ubuntu DKMS MOK
- signed modules after reboot
- automatic boot activation
- zero observed transport frame drops in the qualification captures

## Install for testing

If the preflight reports supported hardware and you are comfortable testing a
beta out-of-tree kernel driver:

```bash
sudo ./tools/sl4a-touch.sh install --standard
```

Keep recovery access available and read `docs/SUPPORT.md` and
`docs/ROLLBACK.md` first.

## Results that are especially useful

Please record:

- exact Surface model
- distro
- `uname -r`
- Secure Boot state
- ACPI IDs
- cold-boot result
- suspend/resume result
- one-finger behavior
- two-finger behavior
- close two-finger behavior
- crossing-finger behavior
- rapid lift/re-contact
- 3/4/5-finger behavior if comfortable
- stylus behavior if you own a pen
- any ghost contacts, finger merging, tracking-ID swaps or dropouts

Failures are just as valuable as successes.

Useful diagnostics:

```bash
./tools/sl4a-touch.sh status
sudo ./tools/sl4a-touch.sh logs
```

## Current qualification scope

Gate5 transport/lifecycle is field-qualified on **one physical MSHW0231
Surface Laptop 4 AMD**. The broader E1 input-quality campaign is still open,
including close-contact continuity, crossing/identity retention, 3–5 finger
behavior, palm handling, stylus validation/coexistence, and broader
firmware/kernel coverage.

If you test it, please share the result where you found the project or in the
relevant Surface Linux discussion so the result is visible to other owners.
