# SL4A TouchScreen — Linux Kernel Driver

> A reverse-engineered Linux kernel driver for the **Microsoft Surface Laptop 3/4 (AMD)** touchscreen. The SL4/MSHW0231 standard installer now uses the Gate5 standard-transport heatmap bridge for beta multitouch; SL3/MSHW0162 keeps conservative standard HID.

The driver speaks the pre-release **HID-over-SPI Version 0 (V0)** protocol that
these panels use, over the AMD FCH SPI controller (`AMDI0060`). It is a
from-scratch implementation validated against the reference Windows stack and
real hardware — not a fork of an in-tree driver.

## Supported hardware

| Component | Identity | Notes |
|---|---|---|
| Surface Laptop 4 (AMD) | touch controller ACPI `MSHW0231` (HID 045E:0C19) | 72×48 grid, 3456 CapImg cells |
| Surface Laptop 3 (AMD) | touch controller ACPI `MSHW0162` | 78×52 grid, 4056 CapImg cells |
| SPI controller (both) | `AMDI0060` (AMD Cezanne FCH SPI V2, MMIO 0xFEC10000) | PIO mode, 33.33 MHz, mode 0 |

The driver selects device-specific tuning (grid geometry, CapImg sample count,
baseline length) from the ACPI ID at probe time — see [Architecture](Architecture).

## Installed behavior by device

| Device | Standard installer behavior | Status |
|---|---|---|
| **Surface Laptop 4 AMD / MSHW0231** | Normal HID discovery, then write-only GET6 -> 4.5-5.5 ms -> SET5; beta CapImg multitouch is published while `raw_mode=0` | Gate5 field-qualified on one unit |
| **Surface Laptop 3 AMD / MSHW0162** | Conservative standard HID coordinate path | Gate5 sequence not claimed |
| **Either, explicit `--raw`** | Raw transport + heatmap tracker | Experimental |

The historical SET5-only mode-3 bridge remains reproducible but is no longer
the MSHW0231 installer path. See [Standard Touch Mode](Standard-Touch-Mode),
[Multi-touch (Beta)](Multi-touch-Experimental), and
`docs/GATE5-QUALIFICATION.md`.

## Quick start

```bash
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
sudo ./tools/sl4a-touch.sh install     # hardware check, DKMS build, boot service
sudo reboot
```

After reboot the driver binds automatically. Verify with:

```bash
sudo ./tools/sl4a-touch.sh status      # hardware + runtime state
sudo evtest                            # on SL4 Gate5, pick "MSHW0231 Touchscreen" for beta MT
```

Full instructions: [Build & Install](Build-and-Install) · [Usage & Troubleshooting](Building-Usage-and-Troubleshooting).

## How it works, in one picture

```
Linux input subsystem (evdev)
        ▲
   hid-generic / hid-input         ┌───────────────────────────┐
        ▲                          │  raw_mode=1               │
   hid_input_report()              │  heatmap → baseline →     │
        │                          │  peaks → CCL → Hungarian  │
  ┌─────┴──────────┐               │  → MT slots → input_mt    │
  │ spi-hid-core   │◄──────────────┤  (mshw0231-raw.c)         │
  │ V0 protocol +  │               └───────────────────────────┘
  │ IRQ sequencer  │
  └─────┬──────────┘
        │ SPI transfers
  ┌─────┴──────────┐
  │ spi-amd        │   AMD FCH SPI V2 PIO controller
  └─────┬──────────┘
        │ SPI bus (33.33 MHz, mode 0)
   MSHW0231 / MSHW0162 touch controller
```

The two kernel modules, the sequencer state machine and the IRQ model are described in [Architecture](Architecture); the wire format in [Protocol](Protocol) and [Wire Protocol](Wire-Protocol).

## Wiki map

| Page | What it covers |
|---|---|
| [Architecture](Architecture) | Module split, sequencer state machine, IRQ model, sysfs interface, recovery |
| [Protocol](Protocol) | HID-over-SPI V0: discovery, message types, feature exchange, timing |
| [Wire Protocol](Wire-Protocol) | Byte-level framing: headers, bodies, opcodes, PIO continuations |
| [Report Descriptor](Report-Descriptor) | The 936-byte descriptor: collections, reports, PIO read invariant |
| [Touch Pipeline](Pipeline) | Raw multi-touch chain: baseline, peaks, CCL, Hungarian, slots |
| [Config Table](Config-Table) | Pipeline constants and their Linux mapping |
| [Hardware](Hardware) | Both panels, AMD FCH SPI registers, wiring, ACPI power |
| [Standard Touch Mode](Standard-Touch-Mode) | Default mode: report formats 0x40/0x01, why it is stable |
| [Multi-touch (Beta)](Multi-touch-Experimental) | Raw mode: activation, per-device geometry, operational safety |
| [Build & Install](Build-and-Install) | Installer, DKMS, Secure Boot/MOK, module parameters, build from source |
| [Usage & Troubleshooting](Building-Usage-and-Troubleshooting) | Day-to-day usage, debugging, recovery, common issues |
| [Reverse Engineering](Reverse-Engineering) | Methodology, evidence, known gaps |
| [Further Reading](Further-Reading) | Repository docs: reference material, supports, tests |

## Repository documentation

The repo's `docs/` directory holds the evidence-grade material this wiki is
built on: protocol and register references, hardware validation procedures and
the deeper design notes. See [Further Reading](Further-Reading) for the map.

## License and status

GPL-2.0, **beta software**. This is a reverse-engineered driver. Gate5 is a
single-unit MSHW0231 field qualification, not a broad hardware guarantee; the
raw transport and heatmap contact stack remain beta.
