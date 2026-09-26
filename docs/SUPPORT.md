# Supported Hardware And Profiles

## Supported Target

This repository is a DKMS driver for the Surface Laptop 3/4 AMD touch
contracts (MSHW0231 on SL4, MSHW0162 on SL3):

| Component | Required identity | Evidence |
| --- | --- | --- |
| Product | Microsoft Surface Laptop 4 AMD (Cezanne) / Surface Laptop 3 AMD | E1 required for a broad release row |
| SPI controller | ACPI `AMDI0060`, MMIO `0xFEC10000`, length `0x100` | `docs/acpi/dsdt.dsl` |
| Touch controller (SL4) | Runtime ACPI `MSHW0231` under `\_SB.SPI1` | Windows capture and target-machine checks |
| Touch controller (SL3) | Runtime ACPI `MSHW0162` under `\_SB.SPI1` | upstream SL3 report |
| SPI resource | Logical CS 0, mode 0, 33.33 MHz, GPIO 0x55 | `docs/acpi/dsdt.dsl` |
| HID descriptor | Microsoft VID `045e`, PID `0c19` on the tested SL4 | captured 936-byte report descriptor |
| Transport | MSHW0231 / MSHW0162 HID-over-SPI V0 | captured protocol traffic |

The controller programs physical ALT_CS 1 for this board even though ACPI
declares logical CS 0. This mapping is controller-specific and must not be
generalized to another AMDI0060 system without hardware evidence.

The module match tables cover exactly MSHW0231/MSHW0162 and AMDI0060;
per-device heatmap geometry is selected by ACPI ID at probe time. Do not install
this DKMS package on another Surface or generic PNP0C51 device except for
explicit investigation with `--force`.

## Installer Profiles

| Profile | Device | Transport | Input behavior | Status |
| --- | --- | --- | --- | --- |
| Standard / Gate5 | SL4 AMD, `MSHW0231` | Normal HID discovery, then write-only GET6 -> 4.5-5.5 ms -> SET5 | Standard HID remains registered and the CapImg tracker publishes `MSHW0231 Touchscreen` multitouch | **Production SL4 multitouch path**; field-qualified on one SL4 unit |
| Standard / conservative | SL3 AMD, `MSHW0162` | Normal HID transport | Standard HID coordinate path | Default for MSHW0162; Gate5 sequence not claimed |
| Legacy raw diagnostic | MSHW0231 / MSHW0162 | Explicit alternate transport used for historical investigation | Diagnostic/research heatmap path | **Not the production multitouch path**; requires `install --raw` |
| Historical mode-3 bridge | SL4 investigation | `raw_mode=N raw_input_beta=Y std_raw_transition=3` | SET5-only CapImg bridge | Historical/diagnostic; superseded by Gate5 mode 1 |

The MSHW0231 standard profile is pinned to:

```text
raw_mode=N
raw_input_beta=Y
wire_double_opcode=1
gate3_observe_only=1
skip_std_getfeat=1
std_raw_transition=1
get_noread=0
getfeat_delay_ms=0
std_liveness_ms=0
std_liveness_recover=0
wait_reset_kick_ms=0
```

Mode 1 writes GET_FEATURE report 6 but intentionally does not synchronously
consume that response before activation; it waits 4.5-5.5 ms and sends
SET_FEATURE report 5 = 1. Full GET6-read experiments and SET5-only mode 3 are
retained as historical evidence, not current installer policy.

## Gate5 Field Qualification Scope

On the tested Surface Laptop 4 AMD / MSHW0231 unit, commit `58f0231` passed:

- true cold power-on activation + real touch;
- three consecutive warm module reload + real-touch cycles;
- two s2idle suspend/resume + real-touch cycles;
- zero observed `frames_dropped` and no unexpected post-DONE controller reset
  in those qualification captures.

This is deliberately narrower than an E1 compatibility claim. Pen, palm
rejection, long mixed-input stress, the full one-through-five-finger matrix,
and the same activation sequence on MSHW0162 remain unqualified. See
`docs/GATE5-QUALIFICATION.md` and `docs/COMPATIBILITY.md`.

## Feature Status

| Feature | Status | Claim |
| --- | --- | --- |
| HID descriptor discovery | Implemented | 936-byte wire descriptor verified on tested SL4 |
| GET_FEATURE ID6 transport | Implemented, including SL4 AMD receive reconstruction | byte-perfect field checkpoint available |
| Gate5 standard-transport CapImg activation | Implemented | field-qualified on one MSHW0231 |
| CapImg capture/tracker | Implemented | beta input-quality qualification in progress |
| Suspend/resume | Explicit _PS3 suspend and _PS0 -> _RST resume | Gate5 path passed 2/2 on tested SL4 |
| Secure Boot | DKMS/MOK signing with complete-pair validation, reuse, import and explicit rotation | full enrollment/reboot/auto-activation path still requires hardware qualification |

## Explicitly Unsupported / Unclaimed

- Surface Pro X and any other `MSHW*` device other than MSHW0231/MSHW0162.
- Other AMD SPI controller IDs, including `AMDI0061` and `AMDI0062`.
- Gate5 mode-1 activation on MSHW0162 until separately tested.
- Pen, palm rejection, or full Windows-equivalent contact classification.
- Treating the single-unit Gate5 campaign as a broad hardware/firmware/kernel
  compatibility guarantee.

Historical mode-3 and earlier freeze documents are intentionally retained. They
describe how the current sequence was discovered; they are not the current
installer contract.
