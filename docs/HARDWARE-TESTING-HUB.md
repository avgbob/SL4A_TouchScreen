# Hardware Testing Hub — Surface Laptop 4 AMD / MSHW0231

The Gate5 production path is working on one qualified Surface Laptop 4 AMD /
MSHW0231 unit, and the project now needs **independent hardware results** more
than additional same-machine testing.

**Latest release:** https://github.com/avgbob/SL4A_TouchScreen/releases/latest

**Tester guide:** https://github.com/avgbob/SL4A_TouchScreen/blob/main/docs/TESTERS-WANTED.md

**Structured tester issue:** https://github.com/avgbob/SL4A_TouchScreen/issues/9

## Who I’m looking for

If you have a **Surface Laptop 4 AMD**, especially one exposing
`MSHW0231 + AMDI0060`, please try the read-only preflight:

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
grep -E 'MSHW0231|MSHW0162|AMDI0060' /sys/bus/acpi/devices/*/hid 2>/dev/null
./tools/sl4a-touch.sh install --check
```

If the hardware matches and you’re comfortable testing a beta out-of-tree
kernel driver:

```bash
sudo ./tools/sl4a-touch.sh install --standard
```

## Most useful data right now

- exact Surface model
- distro and kernel
- Secure Boot state
- ACPI IDs
- cold boot + touch
- suspend/resume + touch
- one/two-finger behavior
- close two-finger approach/separation
- pinch and crossing fingers
- 3/4/5 fingers
- edge/corner contacts
- stylus and stylus+finger if available
- ghost contacts, merging, tracking-ID swaps, dropouts, jitter, or resets

**Failures are as useful as successes.**

The current transport/lifecycle path has passed cold boot, repeated warm reload,
s2idle resume, DKMS install, Secure Boot with an existing enrolled Ubuntu DKMS
MOK, signed reboot, and automatic Gate5 activation on the qualified machine.
Broader input-quality and hardware coverage are still intentionally open.

Reply in the discussion with quick results, or use the Hardware test Issue form
for a structured report.
