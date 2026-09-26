# Architecture A Behavior Freeze

> **Historical freeze — superseded, not deleted.** This file records the
> pre-Gate2/Gate3 behavior freeze and its then-current profiles. Gate5 has since
> qualified a different MSHW0231 standard installer profile. Do not use the
> frozen profile list below as current installation guidance; see
> `docs/GATE5-QUALIFICATION.md` and `docs/SUPPORT.md`.

Freeze baseline: `0c45ddbbdf8ee41af3f178b883353439d86e3562` (`main`, 2026-09-22).

Intended tag: `freeze-arch-A`. The connected GitHub interface used to stage this work cannot create tag refs, so a branch with that name was created at the exact freeze SHA. Create the immutable git tag at the same SHA before or when Gate 1 is merged.

## Frozen architecture

The target architecture is Windows-shaped:

```text
ACPI HSPI / MSHW0231
        |
   AMDI0060
   sl4a-spi-amd.ko
        |
   V0 HID-SPI transport only
   sl4a-spi-hid.ko
        |
   Col02 / Heat-facing HID path
        |
   userspace sl4a-heat
   CapImg -> contacts
        |
   uinput -> libinput / Wayland
```

The kernel raw heatmap implementation remains a reference/replay implementation. It is not the product architecture and must not gain new association radii, smoothing policy, heatmap defaults, or installer knobs while this freeze is active.

## Frozen profiles

1. **Standard installer profile**

   `options sl4a_spi_hid raw_mode=N wire_double_opcode=1`

2. **SET5 bridge qualification profile**

   Manual experimental profile documented by `docs/ACTIVATION.md`: `raw_mode=0`, `raw_input_beta=1`, `skip_std_getfeat=1`, `std_raw_transition=3`. This is not an installer default.

3. **Raw installer profile**

   `options sl4a_spi_hid raw_mode=Y raw_input_beta=Y skip_getfeat=Y wire_double_opcode=1`

## Freeze rule

Until Gate 2 produces the Windows golden lifecycle/state-machine artifacts, `main` gets no default-changing modifications to wire framing, reset/power sequencing, post-RDESC feature traffic, or heatmap/contact policy.

Allowed work during the freeze: evidence capture, documentation, replay/host tests, userspace processor scaffolding, and fixes that do not alter the frozen runtime defaults.
