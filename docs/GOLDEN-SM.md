# Gate 2 — Windows Golden State Machine

**Verdict: PASS**

This verdict applies to the lifecycle/transport contract in `docs/GATE2-CAPTURE.md`. It does **not** claim that a transport trace can observe every report synthesized above HID-SPI by `TouchPenProcessor0C19.dll`.

## Trace identity

- ETL: `C:\gate2\gate2.etl`
- Size: 398,721,024 bytes
- SHA-256: `4583C62F0A7AC1B2099AA904FF8F61BF1DE065A2A2EF1AB58397950E57906552`
- tracerpt summary: 3,254,430 events processed, **0 events lost**
- Decode source used for the final audit: compact extraction of the golden ETL, preserving ACPI method events, HIDCLASS snapshots, SPB/GPIO event families and raw transfer buffers in the Gate-2 windows.
- Normalized observed rows: `evidence/windows/gate2/windows-golden.jsonl`

The original `markers.tsv` remains part of the capture directory. The compact extractor used those markers to label the decoded rows as `COLD_BOOT_12S`, `T2_DISABLE_ENABLE`, `T3_ONE_FINGER`, `T4_TWO_FINGER`, `T5_SLEEP_RESUME`, and `T5_POST_RESUME_FINGER`.

## 1. Reset — PASS

Windows invokes `\\_SB.SPI1.HSPI._RST` in both required lifecycle paths:

| Phase | _RST start (UTC) | _RST finish (UTC) | observed elapsed |
|---|---|---|---:|
| cold boot | 23:45:37.4835342 | 23:45:37.7839972 | 306 ms |
| disable -> enable | 23:47:45.5341525 | 23:47:45.8347428 | 301 ms |
| sleep -> resume (additional evidence) | 23:49:18.3391801 | 23:49:18.6400543 | 301 ms |

The disable path also executes `_PS3`; enable executes `_PS0` immediately before `_RST`.

**Answer:** `_RST` is not optional Windows behavior on this machine. It is directly observed on cold start and disable->enable, and again on resume.

## 2. Power — PASS

Directly observed HSPI AML methods include:

- cold boot: `_INI`, `_PS0`, then `_RST`;
- disable: `_PS3`;
- enable: `_PS0`, then `_RST`;
- sleep: `_PS3`;
- resume: `_PS0`, then `_RST`.

No D-state policy is inferred from the DSDT here; these rows are runtime ETL observations.

## 3. Post-RDESC feature sequence — PASS

The physical device re-enumerates as `ACPI\MSHW0231\a`, VID `045E`, PID `0C19`, service `hidspi`, 8 collections, report descriptor length `0x3A8` (936 bytes).

During T2 enable, the observed order is:

1. **23:47:45.9542598** — 945-byte SPB response containing the 936-byte report descriptor.
2. **23:47:46.0775664** — `SET_FEATURE 0x56`:
   `02 00 00 03 C2 00 03 0A 00 56 D9 D7 FC 6E 79 4C 00 00`
3. **23:47:46.1621671** — `GET_FEATURE ID6`:
   `02 00 00 03 42 00 04 03 00 06`
4. **23:47:46.1627954** — ID6 response: content length 122, content ID 6, 129 SPB bytes including the five-byte read preamble.
5. **23:47:46.1801229** — `SET_FEATURE ID5=1`:
   `02 00 00 03 82 00 03 04 00 05 01 D7 FC 6E`
6. **23:47:59.8330305** — first audited T3 full raw body: content ID `0x0C`, content length 4302.

The three command shapes are decoded using the repository's existing HID-SPI V0 wire definitions. The per-boot key/trailer bytes differ from some older captures; only the command/content fields are treated as protocol semantics.

**Answer:** after RDESC and before the first live gesture body, Windows sends **SET_FEATURE 0x56 -> GET_FEATURE ID6 (+ reply) -> SET_FEATURE ID5=1**.

## 4. Finger-down path — PASS at the transport boundary

Full SPB bodies in the gesture windows were exhaustively audited:

| Window | ID 0x0C bodies | ID 0x08 bodies | ID 0x40 bodies |
|---|---:|---:|---:|
| one finger | 255 | 12 | 0 |
| two finger | 376 | 22 | 0 |
| post-resume one finger | 216 | 0 | 0 |

A representative one-finger body is a 4309-byte SPB read whose payload starts:

`FF FF FF FF FF CE 10 0C ...`

After the five-byte read preamble, `CE 10` is the little-endian content length 4302 and the next byte is content ID `0x0C`.

The full 4309-byte body reads are serviced in **System/kernel PID 4**; observed worker threads include 1036/1044 during T3 and additional kernel threads in later windows.

**Transport answer:** finger activity is directly observed as **0x0C on the HID-SPI/SPB path to the Col02/raw heat collection**. No full `0x40` body is present on SPB in any audited gesture window.

**Scope limit:** this does **not** establish that report `0x40` is absent above the transport. `TouchPenProcessor0C19.dll` may transform Col02/raw input into a touchscreen report in software; that upper-layer synthesis is not visible as an SPB body in this capture. Its status remains **UNKNOWN**, not inferred absent.

## Golden transition contract for Gate 3

Gate 3 may now use these observed Windows transitions as the compatibility target:

1. Cold/rebind/resume lifecycle must preserve the observed ACPI ordering, including `_PS0 -> _RST` on activation and `_PS3` on deactivation/sleep.
2. Descriptor discovery completes before the observed post-RDESC feature sequence.
3. The observed post-RDESC sequence is `SET_FEATURE 0x56 -> GET_FEATURE ID6 -> SET_FEATURE ID5=1`.
4. The transport-level live raw stream is content/report ID `0x0C`; do not require transport-level `0x40`.
5. Any future claim about `0x40` must be made at the software-processor/HID upper layer, not inferred from SPB.

## Gate decision

All four Gate-2 questions now have an evidence-grounded answer at the layer the ETL can observe. **Gate 2 = PASS.**

This authorizes Gate 3 work under Architecture A: shrink the kernel side toward transport-only HID-SPI and move heat processing to userspace `sl4a-heat`. It does not authorize unrelated wire, reset, or heatmap-policy experimentation; later changes must cite the observed golden transitions above.
