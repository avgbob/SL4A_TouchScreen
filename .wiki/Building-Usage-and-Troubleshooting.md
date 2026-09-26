# Building, Usage and Troubleshooting

> **Beta software:** this is a beta, reverse-engineered kernel driver.
> Use it at your own risk. It is provided "as is", without warranty; the authors
> and contributors accept no responsibility for problems or damage from its use.

## Install or update

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
sudo ./tools/sl4a-touch.sh install
sudo reboot
```

The unified installer checks for `MSHW0231`/`MSHW0162` +
`AMDI0060`, builds `sl4a-spi-amd` and `sl4a-spi-hid` with DKMS for
every installed kernel with an available build tree, removes obsolete
`sl4a-touch` DKMS versions, installs `sl4a-touch-activate.service`
for boot activation, and activates the modules at **Step 7** — it binds
them as soon as it finishes. Two cases skip that first activation and
leave it to the boot unit: an unenrolled Secure Boot MOK key, and a
profile that changes the load-time-only `raw_mode` (the modules then keep
the previous profile until the next boot). Replacing the AMD SPI
controller while running can freeze the system, so a reboot is the
recovery path after a failed experiment, not a required step of a normal
install.

The installer chooses the compiler required by the running kernel. With
Secure Boot enabled it resolves the signing identity DKMS is actually
configured to use, validates the matching key/certificate pair, and reuses an
already-enrolled certificate when possible. If enrollment is required, use the
**certificate path printed by the installer** with `mokutil --import`; Ubuntu
normally uses `/var/lib/shim-signed/mok/MOK.der`, not
`/var/lib/dkms/mok.pub`.

## Uninstall

```bash
sudo ./tools/sl4a-touch.sh uninstall
sudo reboot
```

The uninstaller removes the service and DKMS installation, but intentionally
leaves loaded modules active until reboot.

## Input devices

After a successful MSHW0231 Gate5 boot, the standard HID device remains
registered and the in-kernel CapImg multitouch tracker also publishes
`MSHW0231 Touchscreen` (input-quality beta) under `/dev/input/eventN`; use that node for Gate5 multitouch testing. On
MSHW0162 conservative standard installs, use the HID-stack coordinate node.
The pen node is published but remains unqualified.

## Development

Use a local build as a compile check:

```bash
make LLVM=1 -C /lib/modules/$(uname -r)/build M=$PWD/driver modules
```

Use `LLVM=1` only for a clang-built kernel. To test modified driver code, run
`sudo ./tools/sl4a-touch.sh rebuild` (compile check) or
`sudo ./tools/sl4a-touch.sh install` from the checkout and reboot. Do not use
`rmmod`, `insmod`, or a systemd restart to replace `spi-amd` on a live system.

## Debugging and recovery

For a boot freeze or initialization failure, run
`sudo ./tools/sl4a-touch.sh logs` — it collects a full bundle
(hardware, DKMS, modprobe config, service state, module parameters, sysfs
stats, Secure Boot state, and driver-related dmesg lines).

Do not use direct ACPI GPIO calls as a recovery method. A full reboot is the
only supported recovery after a controller freeze or a raw-mode test.

## Common issues

- **No touchscreen after install/update:** reboot, then inspect `systemctl status sl4a-touch-activate`
  and `journalctl -b -k`.
- **Touchscreen dies after a cold boot:** on MSHW0231 first verify that the
  installed profile is the Gate5 mode-1 profile and collect `protocol_stats`
  plus dmesg. Qualified activation uses `_PS0 -> _RST`, descriptor discovery,
  write-only GET6, a 4.5-5.5 ms delay and SET5. Error-work recovery is a
  separate `_PS3 -> _PS0` path.
- **Secure Boot rejects modules:** re-run
  `sudo ./tools/sl4a-touch.sh install --standard` and use the active DKMS MOK
  certificate path it prints. If that certificate is not enrolled, stage that
  exact path with `mokutil --import`, complete MOK Manager on reboot, then
  verify with `./tools/sl4a-touch.sh status`.
- **`raw_mode=1` does not stream or leaves touch unusable:** this is the
  expected failure shape of the beta raw path; reboot and return to the
  default `raw_mode=0`.
- **Service appears failed immediately after a kernel update:** this can occur
  when headers for the running kernel were removed. The loaded driver can keep
  running; reboot into the updated kernel and verify `dkms status`.
