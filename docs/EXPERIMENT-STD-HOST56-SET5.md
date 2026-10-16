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

DieSchatten's independent 13.5-inch MSHW0231 unit uses a different **raw-mode**
sequence: report 0x56 with all-six-`FF` payload, ~37–40 ms delay, SET5,
and **no GET6**. That combination produced CapImg on his unit; GET6 paths
reset his controller. See
https://github.com/Syax89/SL4A_TouchScreen/issues/85

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
git fetch origin
git worktree add /home/jo/SL4A_TouchScreen-host56 origin/experiment/sl4-std-host56-set5
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
