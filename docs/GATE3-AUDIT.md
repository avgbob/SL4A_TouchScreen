# Gate 3 Architecture-A audit

This document records the post-Gate-2 audit of the Linux driver against the
accepted Windows ETL, the 936-byte report descriptor, the MSI/INF evidence and
the current Linux HID transport API.

Evidence labels:

- **OBSERVED** — directly present in Gate-2 runtime trace or checked-in binary/
  descriptor evidence.
- **RECONSTRUCTED** — follows from two independent checked-in observations, but
  is not itself an ETW label.
- **LINUX-FIELD** — measured behavior of an earlier Linux driver build.
- **UNKNOWN** — not established by current evidence.

## Executive result

Architecture A is still the right destination, but the earlier Gate-3 model
put too much Windows child-collection policy inside the kernel.

The cleaner boundary is:

```text
ACPI HSPI / MSHW0231
        |
AMDI0060 controller
        |
sl4a-spi-hid.ko
  V0 transport + lifecycle only
        |
one Linux HID device
  936-byte descriptor
        |
HID core + hidraw
        |
sl4a-heat userspace
  filter Col02 report IDs
  GET_FEATURE 6
  SET_FEATURE 5=1
  consume input 0x0C
        |
uinput multitouch
```

Linux does not need to recreate the Windows child-PDO split. Hidraw is a raw
interface for the physical HID device; the userspace processor can filter the
descriptor-defined report IDs that belong to the Heat collection.

## Eight top-level collections

The 936-byte report descriptor contains exactly eight top-level collections.
Windows exposes exactly eight MSHW0231 child collections. The ordering is
therefore highly informative and cross-checks against known child names.

| Descriptor top-level collection | Key reports | Windows mapping | Status |
|---|---|---|---|
| 1 — Vendor FF0B / Usage 0x0B | 0x48, 0x29–0x37 | Col01 Surface Touch Communications | RECONSTRUCTED |
| 2 — Digitizer / Usage 0x0F | 0x07, 0x08, 0x0A, 0x0B, **0x0C**, 0x0D, 0x1A, 0x1C; feature **6** DeviceMode; feature **5** | **Col02 Surface Touch Pen Processor** | RECONSTRUCTED + Heat INF binding |
| 3 — Vendor FF0F / Usage 0x50 | 0x1F, 0x21, 0x22, 0x23 | Col03 Surface Digitizer Utility | RECONSTRUCTED |
| 4 — Vendor FF0F / Usage 0x60 | 0x19 | Col04 Surface Virtual Function Enum Device | RECONSTRUCTED |
| 5 — Digitizer / Pen | 0x01 | Col05 Surface Touch Pen Device | strong cross-check |
| 6 — Digitizer / TouchScreen | **0x40** | Col06 Surface Touch Screen Device | strong cross-check |
| 7 — Vendor FFF4 / Usage 0x01 | 0x54, 0x55, feature **0x56** | Col07 Surface Pen BLE LC Adaptation Driver | RECONSTRUCTED |
| 8 — Vendor FFA1 / Usage 0x60 | 0x58 | Col08 Surface Pen CFU/BLE connection | RECONSTRUCTED |

The critical ownership result is therefore:

- GET6, ID5 and input 0x0C are **Col02**.
- input 0x40 is **Col06**.
- feature 0x56 is **Col07**, not Col02.

## Chronology is not ownership

Gate 2 T2 observed this bus order:

```text
RDESC
0x56
GET6
ID6 response
ID5=1
0x0C
```

The earlier Gate-3 design treated that as one startup handshake. The descriptor
proves that interpretation is too strong: 0x56 belongs to a different top-level
collection from GET6/ID5/0x0C.

The ETL independently supports this split:

- the 0x56 SPB request is submitted under PID 2216;
- GET6 and ID5 are submitted under PID 15596;
- SpbCx executes the actual buffers in System PID 4.

Process names are still UNKNOWN, but the collection split already explains why
the submitters differ. Do not make Col07's 0x56 a prerequisite for the Linux
Heat client merely because it happened first on the shared bus.

## Col02 is a normal HID raw-report path

Descriptor report 0x0C contains:

- report ID: 1 byte;
- SurfaceSwitch field: 16 bits = 2 bytes;
- DeviceIndex constant field: 4297 bytes.

Total HID input report size = **4300 bytes**.

Gate 2's V0 content length is 4302 because the V0 content envelope adds its
two-byte content-length field. The current driver already calls the normal HID
path as:

`hid_input_report(..., &body[7], rl - 2, ...)`

For `rl=4302`, that is exactly the descriptor-sized 4300-byte HID report.

Linux HID core's default transport buffer ceiling is 16 KiB, so 4300 bytes does
not require a custom raw device.

The current driver nevertheless special-cases report 0x0C and withholds it from
`hid_input_report()` on the standard path. That is product policy, not
transport necessity.

## Existing Linux pieces to KEEP

| Piece | Decision | Reason |
|---|---|---|
| AMDI0060 controller driver | KEEP | transport dependency |
| V0 descriptor discovery | KEEP | required transport function |
| 936-byte descriptor capture/fallback | KEEP, fallback remains qualification debt | descriptor is validated |
| `hid_device` + HID LL driver | KEEP | correct Linux transport boundary |
| `.raw_request` feature control | KEEP/FIX | correct userspace control boundary |
| `.output_report` | KEEP | standard HID transport |
| raw frame/type parsing | KEEP | V0 transport |
| request-context fields (`read_resp_type/id`) | KEEP | Gate 2 live reads use prior request context |
| diagnostics/tracepoints | KEEP where transport-scoped | needed for qualification |

## Pieces to MOVE to userspace / fixture

| Piece | Decision | Reason |
|---|---|---|
| CapImg decode | MOVE to `sl4a-heat` | Heat belongs above transport |
| baseline/C590 | MOVE | software processor |
| blobs/CCL/peaks | MOVE | software processor |
| Hungarian association / coalescing | MOVE | contact interpretation |
| kernel synthetic multitouch device | MOVE to userspace uinput | Windows analogue is software processing |
| `mshw0231-raw.c` | retain as fixture/reference until userspace parity | useful validated work, wrong product layer |

## Pieces to REMOVE from the final transport path

| Piece | Decision | Reason |
|---|---|---|
| suppressing standard-path 0x0C before HID core | REMOVE | prevents hidraw Architecture A |
| raw_mode suppressing HID-device creation | REMOVE from final product path | bypasses normal HID boundary |
| fused kernel `0x56 -> GET6 -> ID5` startup policy | REMOVE from final product path | mixes Col07 and Col02 ownership |
| kernel SET5 bridge as product behavior | RETIRE after userspace client works | qualification hack |
| Heat-specific watchdog/fallback policy | RETIRE/MOVE | not transport responsibility |

## Feature-report transport audit

The generic HID LL callback now has the right intended role for Col02:

- SET_FEATURE accepts a numbered HID feature buffer and strips byte 0 before
  encoding the V0 content.
- GET_FEATURE returns the numbered HID ABI shape
  `[report_id][payload...]`.
- non-feature raw requests are rejected rather than silently encoded as feature
  traffic.
- a successful SET_FEATURE preserves `read_resp_type/id` before the device can
  assert its next data IRQ.

For GET6 the descriptor says 119 data bytes. Hidraw therefore expects 120 bytes
including report ID 6. The V0 reply's total content length is 122 =
two-byte length field + report ID + 119 data bytes, which maps cleanly to the
HID buffer.

For ID5 the descriptor says one data byte. Userspace sends `[05 01]`. The V0
transport adds the content envelope and alignment. Gate 2 itself observed an
ID5 frame with zero alignment bytes, so userspace does not need the old
`0C EE 5B` capture residue.

## V0 read context

Gate 2 live 0x0C reads after T2 carry the prior Col02 request context:
SET_FEATURE / report 5 / response register 4.

The old in-kernel ID5 helper set that context, but:

- the generic HID SET_FEATURE path did not; and
- the standard bridge erased it immediately afterward.

Gate-3 transport fixes now make generic SET_FEATURE preserve that context and
stop the bridge from erasing it. This is necessary for the reference
nine/ten-byte read-approval shape.

## Power/lifecycle audit

### What is observed

- activation contains `_PS0 -> _RST`;
- T2 disable contains `_PS3`;
- sleep contains all-FF 0x56 STOP followed by `_PS3`;
- resume contains `_PS0 -> _RST`;
- Gate-2 resume does **not** perform RDESC/GET6 replay.

### Current Linux mismatches

- system resume currently forces descriptor rediscovery;
- system suspend does not send the observed Col07 0x56 STOP;
- module remove/probe-failure cleanup sends a legacy wire SET_POWER SLEEP
  command not observed as the Gate-2 sleep sequence;
- hot unload/reload can therefore contaminate a lifecycle-parity experiment.

The first clean qualification of a new lifecycle build should be staged and
activated from a clean boot, not by unloading an older experimental module and
immediately rebinding.

Do not add the Col07 STOP command to the transport merely to match chronology:
its owner is not the Heat/Col02 transport policy. Collection ownership must be
settled first.

## 0x56 status

Report 0x56 belongs to descriptor collection 7. Its six-byte semantic payload
varies between captures:

- older fixture: `BD 0C EE 5B 44 4C`
- Gate 2: `D9 D7 FC 6E 79 4C`

Generation/source remains **UNKNOWN**.

This is further reason not to hardcode 0x56 inside Col02/Heat startup.

## AMD SPI long-transfer status

Gate 2 proves SpbCx submitted equal-size large TX/RX buffers (for example
4309/4309). It does not expose physical controller TX_COUNT/RX_COUNT, so it
does not prove how many request bytes were clocked on SPI.

Keep the Linux segmented-read issue open. Do not patch the controller solely
from the SpbCx buffer lengths.

## Revised Gate-3 sequencing

The next architecture checkpoint should no longer be raw_mode's fused startup.

Recommended sequence:

1. standard V0 transport creates the normal Linux HID device;
2. verify hidraw exists and the 936-byte descriptor is readable there;
3. stop suppressing descriptor-defined input 0x0C from HID core;
4. a minimal userspace Col02 client opens hidraw;
5. userspace GET_FEATURE ID6 and validates 119 data bytes;
6. userspace SET_FEATURE ID5=1;
7. verify 4300-byte report-ID-0x0C records arrive through hidraw;
8. only then port CapImg -> contacts into `sl4a-heat`;
9. qualify suspend/resume separately, with the userspace client responsible for
   re-establishing whatever Col02 state evidence requires.

Col07 feature 0x56 is a separate follow-up and is not a Heat-stream acceptance
criterion unless new evidence proves the dependency.

## Remaining UNKNOWNs

- process names for Gate-2 PID 2216 and PID 15596;
- source/generation rule for the six-byte 0x56 payload;
- exact Col07 purpose/ownership on Linux;
- physical AMD SPI TX_COUNT/RX_COUNT corresponding to large SpbCx buffers;
- exact userspace re-arm behavior required after Linux resume;
- whether forwarding Col02's SurfaceSwitch field causes a useful or ignorable
  per-application evdev node (hidraw availability is independent of this);
- whether every supported SL3/SL4 firmware uses the same collection ordering.

These unknowns do not block the transport-only + hidraw + userspace-Heat
architecture.
