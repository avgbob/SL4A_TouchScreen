# Gate 3 — Architecture A transport checkpoint

Gate 2 is closed PASS. The accepted Windows lifecycle/transport reference is
`docs/GOLDEN-SM.md` and
`evidence/windows/gate2/windows-golden.jsonl`.

## Scope

This checkpoint changes only lifecycle and HID-SPI startup sequencing. It does
not tune the heatmap detector/tracker and does not yet change the AMD SPI
controller's long-transfer behavior.

Observed Windows target:

```text
activation:
  _PS0
  _RST

discovery:
  DEVICE_DESC
  936-byte RPT_DESC

post-RDESC:
  SET_FEATURE 0x56
  GET_FEATURE ID6
  read ID6 response
  SET_FEATURE ID5=1

live transport:
  0x0C CapImg bodies

suspend/deactivation:
  _PS3

resume:
  _PS0
  _RST
  rediscovery
```

## Gate-3 branch behavior

On `gate3-arch-A`:

- ACPI activation is explicitly `_PS0 -> _RST`.
- Probe and resume issue DESCREQ directly after activation once IRQ is armed;
  they do not require a RESET_RSP edge to survive the reset interval.
- Suspend executes `_PS3` after SPI/IRQ activity has been quiesced.
- Raw startup defaults to the observed post-RDESC sequence:
  `0x56 -> GET6/reply -> SET5=1`.
- The duplicate DONE-time `0x56` is disabled by default.
- `gate3_observe_only=1` is the default: a failed raw handshake is logged,
  but the old D2/D0/retry/fallback machinery is not allowed to mutate the first
  checkpoint trace.
- Existing heatmap code remains frozen as a diagnostic consumer.

## Deliberately unresolved

Gate 2 also proved that Windows performs large reads as full-length paired SPB
transfers (for example 4309-byte TX + 4309-byte RX for a live 0x0C body).
The current Linux AMD SPI path does not yet reproduce that transaction shape.
This checkpoint intentionally leaves that difference unchanged so the first
hardware run can determine whether lifecycle/handshake parity alone is enough.

## First hardware checkpoint

Build and load the raw profile from this branch. Capture dmesg from module
activation through one finger gesture.

PASS-to-next-step evidence:

1. `GATE3: activation _PS0 -> _RST`
2. DEVICE_DESC and 936-byte report descriptor are received.
3. one `SET_FEATURE 0x56`
4. one `GET_FEATURE 6` and a valid ID6 response
5. one `SET_FEATURE ID5=1`
6. sustained live `0x0C` bodies after a finger gesture

A failure is still useful. With observe-only mode, the first divergence remains
visible without being overwritten by recovery traffic.

## Do not do yet

- no blob/association/ghost tuning;
- no new watchdog/retry policy;
- no requirement for transport-level report 0x40;
- no 4309-byte padded-read/controller patch until this checkpoint shows it is
  still needed.
