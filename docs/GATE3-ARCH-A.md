# Gate 3 — Architecture A split checkpoint

Gate 2 is closed PASS. The post-Gate-2 audit is in
`docs/GATE3-AUDIT.md`.

## Goal

Gate 3 is the **architecture split**, not Windows byte-for-byte qualification.
The kernel should become a V0 HID-SPI transport and userspace should own Heat
processing.

Target:

```text
ACPI HSPI / MSHW0231
        |
   AMDI0060
   sl4a-spi-amd.ko
        |
   V0 HID-SPI transport
   sl4a-spi-hid.ko
        |
   one Linux HID device
   936-byte report descriptor
        |
   HID core + hidraw
        |
   sl4a-heat
   Col02 GET6 / SET5
   input 0x0C -> CapImg -> contacts
        |
   uinput -> libinput / Wayland
```

Linux does not need to recreate Windows child PDOs. Hidraw exposes the raw
reports of the physical HID device; userspace filters report IDs belonging to
the reconstructed Col02 collection.

## Why this changed

The Gate-2 bus chronology was initially read as one kernel startup handshake:

`0x56 -> GET6 -> ID5 -> 0x0C`.

The 936-byte descriptor shows that interpretation is wrong:

- GET6, ID5 and 0x0C belong to top-level collection 2 (Windows Col02 / Heat).
- 0x40 belongs to top-level collection 6 (Windows touchscreen).
- 0x56 belongs to top-level collection 7, not Col02.

Gate 2 also shows different submitting PIDs for 0x56 versus GET6/ID5. Therefore
chronological interleaving on one SPI bus is not proof of one owner.

## Gate-3 kernel requirements

1. Standard V0 discovery creates the normal Linux HID device.
2. The real 936-byte descriptor is supplied to HID core.
3. Every descriptor-valid input report, including ID 0x0C, is forwarded through
   `hid_input_report()` on the standard path.
4. `.raw_request` exposes HID feature GET/SET semantics correctly:
   - numbered GET returns `[report_id][payload]`;
   - SET accepts `[report_id][payload]`;
   - successful feature SET preserves the V0 request context used by later
     body reads.
5. Kernel Heat processing is optional legacy/qualification behavior only; it
   must not steal raw reports from HID core.
6. No Col07 0x56 policy is required for the Col02 Heat acceptance checkpoint.
7. Suspend/resume parity is qualified separately after the split.

## Gate-3 userspace checkpoint

A minimal `sl4a-heat` transport client must:

1. locate the MSHW0231 hidraw node (VID 045e, PID 0c19);
2. read/verify the report descriptor;
3. issue GET_FEATURE ID6 and receive report ID 6 + 119 data bytes;
4. issue SET_FEATURE ID5 with one-byte payload `01`;
5. read full 4300-byte numbered input report 0x0C from hidraw;
6. save raw frames for replay/verification.

At this checkpoint it does **not** need to synthesize multitouch yet. Capturing
correct Col02 frames through hidraw is enough to prove the architecture split.

## Gate-3 PASS

Gate 3 passes when, on the real SL4:

- standard transport enumerates and binds a HID driver/hidraw;
- userspace GET6 works through the generic HID LL `raw_request`;
- userspace SET5=1 works through that same boundary;
- sustained report-ID-0x0C frames arrive through hidraw;
- the kernel beta Heat processor is not required for those frames to reach
  userspace.

## Legacy diagnostic paths

The following remain temporarily for comparison/replay, but are not the
Architecture-A acceptance path:

- `raw_mode=Y`;
- `std_raw_transition`;
- `raw_input_beta`;
- `mshw0231-raw.c` contact synthesis;
- fused kernel 0x56/GET6/ID5 startup;
- raw handshake retry/fallback policy.

Do not delete them until userspace raw-frame capture and replay are proven.

## Gate 4

After Gate 3 proves the boundary, Gate 4 qualifies lifecycle/wire behavior
against the Windows golden evidence:

- activation `_PS0 -> _RST`;
- descriptor/discovery behavior;
- read-approval shape and request context;
- power/suspend/resume behavior;
- any remaining AMD SPI transaction-shape mismatch.

Gate 4 must keep collection ownership separate. Col07 report 0x56 is not a
Col02 Heat requirement unless new evidence proves a dependency.

## Open items

See `docs/GATE3-AUDIT.md` for the full list, especially:

- 0x56 six-byte payload source is unknown;
- process names for Gate-2 request submitters remain unresolved;
- Linux resume currently rediscovering descriptors does not match Gate-2 T5;
- module hot-unload still uses legacy power-down traffic and should not be the
  basis of a clean lifecycle-parity trace.
