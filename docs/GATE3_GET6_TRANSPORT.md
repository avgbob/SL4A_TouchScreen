# Gate 3 — GET_FEATURE(6) Transport Qualification

## Status

**Qualified on the recorded Surface Laptop 4 AMD test unit on 2026-09-25.**

The Gate 3 blocker for the standard HID path was the synchronous
`GET_FEATURE` request for HID report ID 6. The request and response header had
already been proven; the remaining failure was the AMD SPI controller's
physical FIFO layout during the 129-byte response-body read.

The final research branch produces a **120-byte HID feature report that is
byte-for-byte identical to the Windows reference capture**:

- ioctl return: `120`
- report ID: `0x06`
- data length: 119 bytes
- byte comparison against the Windows GET6 payload: **PASS**

This closes the GET_FEATURE(6) transport problem on this exact SL4 AMD test
configuration. It does **not** by itself qualify SET_FEATURE(5), raw CapImg
streaming, suspend/resume, other firmware revisions, or other Surface models.

## Test provenance

| Item | Recorded value |
| --- | --- |
| Machine | Microsoft Surface Laptop 4, 13.5-inch AMD |
| CPU | Ryzen 7 Microsoft Surface Edition |
| Touch device | `MSHW0231`, HID VID/PID `045e:0c19` |
| SPI controller | `AMDI0060` AMD FCH SPI V2 |
| Firmware | Surface BIOS 4.501.140 |
| Distribution | Ubuntu 24.04 |
| Kernel | `7.0.0-31-generic` |
| Secure Boot | Enabled; both experimental modules signed with the project DKMS MOK |
| Validation date | 2026-09-25 |
| Driver profile | standard HID transport, Gate-3 observe-only qualification profile |

The qualification load used the standard transport with recovery mutations
disabled so a failed GET6 could not fall into legacy power-cycle/retry behavior:

```text
raw_mode=0
wire_double_opcode=1
gate3_observe_only=1
std_raw_transition=0
std_liveness_ms=0
std_liveness_recover=0
wait_reset_kick_ms=0
skip_std_getfeat=0
```

udev execution was paused during the single-request test so no unrelated
userspace feature query could race the measurement.

## What was already proven before the body fix

Before changing the AMD body transport, all of the following were independently
established:

1. the panel reaches `DONE`;
2. the 936-byte report descriptor is read correctly;
3. Linux creates `/dev/hidraw*` for `001C:045E:0C19`;
4. a generic Linux `HIDIOCGFEATURE` ioctl enters the expected HID GET_FEATURE
   path;
5. the exact GET6 request accepted by the panel is:

```text
02 00 00 03 42 00 04 03 00 06
```

6. the panel answers with a genuine synchronous type-5 header.

The working header observation is:

```text
request:
02 00 00 03 42 00 04 03 00 06

response-header read:
06 ff b2 ff 01 ff ff ff 52 f0 01 5a

parsed synchronous type:
5
```

Therefore the remaining problem was narrowed to the **body transfer only**.
Request framing, report ID, timing, response register selection, and type-5
header parsing were not reopened during the final body investigation.

## Windows reference body

The authoritative Windows trace activity is:

```text
a9265982-0b91-0004-f06e-2aa9910bdd01
```

SpbCx records a 129-byte FromDevice buffer:

```text
ff ff ff ff ff 7a 00 06 77 00 00 00 00 00 00 70
00 00 00 00 02 01 30 00 00 00 48 00 00 00 6f 6f
00 00 4a 4a 00 00 01 f5 e4 c8 43 00 00 00 00 00
00 00 00 00 00 00 00 b4 51 ca 43 00 00 00 00 00
00 32 43 00 00 36 43 00 00 34 43 00 00 80 3f 00
00 32 43 00 00 36 43 00 00 34 43 00 00 80 3f 00
00 b4 42 00 00 2b 43 00 00 c8 42 00 00 a0 41 00
00 2c 43 00 00 31 43 00 00 2f 43 00 00 00 40 00
81
```

Its semantic layout is:

```text
body[0..4]     five transport-prefix bytes: ff ff ff ff ff
body[5..6]     total_length = 0x007a = 122
body[7]        content_id = 0x06
body[8..126]   119 bytes of HID report data
body[127..128] two transport bytes outside the 122-byte semantic content
```

The V0 content parser therefore correctly starts at `body + 5`:

```text
7a 00 06 <119 data bytes>
```

No parser-offset change is part of the final fix.

## AMD FIFO behavior that caused the corruption

The normal combined transaction for the GET6 body is a nine-byte request after
the outer opcode has been consumed by the AMD host driver. The generic AMD path
originally chose the largest first receive that filled the 70-byte FIFO:

```text
TX9 + RX60 + controller-extra1 = 70
```

The failure initially looked like a generic FIFO-overflow or offset error.
Neither interpretation was correct.

The controller produces a special initial FIFO layout for this GET6 body. The
first bytes are interleaved into the request region; after that point the
response becomes contiguous. Long-body streaming itself is not generally
broken.

### Proven first-segment map

With the final physical receive count of 52, the body can be reconstructed as:

```text
body[0..4]   = ff ff ff ff ff

body[5]      = FIFO[3]
body[6]      = FIFO[5]
body[7]      = FIFO[7]
body[8]      = FIFO[9]
body[9]      = FIFO[11]
body[10]     = FIFO[13]
body[11]     = FIFO[15]

body[12..59] = FIFO[16..63]
body[60..63] = FIFO[64..67]
```

This yields the first 64 logical body bytes exactly.

The controller is programmed with:

```text
physical RX_COUNT = 52
logical first-body bytes delivered to the caller = 64
```

The distinction is intentional: the controller's FIFO view and the logical
HID-over-SPI body are not one-to-one during this first segment.

### Proven continuation map

After the RX52 first segment, the first three-byte continuation command exposes
the next logical byte at FIFO offset 3:

```text
continuation command length = 3
logical body[64]            = FIFO[3]
```

For this **GET6 continuation only**, the first 64 continuation bytes are copied
from:

```text
FIFO + TX_COUNT
```

rather than the generic `FIFO + TX_COUNT + 1` extraction used elsewhere.

This exception must remain tightly fingerprinted to the GET6 transaction.
Globally changing the continuation offset breaks the known-good 936-byte report
descriptor continuation path.

## Final logical report

After transport reconstruction, the HID subsystem returns:

```text
06 77 00 00 00 00 00 00 70 00 00 00 00 02 01 30
00 00 00 48 00 00 00 6f 6f 00 00 4a 4a 00 00 01
f5 e4 c8 43 00 00 00 00 00 00 00 00 00 00 00 00
b4 51 ca 43 00 00 00 00 00 00 32 43 00 00 36 43
00 00 34 43 00 00 80 3f 00 00 32 43 00 00 36 43
00 00 34 43 00 00 80 3f 00 00 b4 42 00 00 2b 43
00 00 c8 42 00 00 a0 41 00 00 2c 43 00 00 31 43
00 00 2f 43 00 00 00 40
```

The qualification harness compared all 120 bytes with the Windows-derived
reference and printed:

```text
ioctl: 120
GET6 BYTE-PERFECT: PASS
```

The result establishes byte-perfect **semantic HID report output**. The two
bytes following the 122-byte semantic body are transport bytes and are not
part of the 120-byte HID feature report comparison.

## Experiments that were closed

The failed A/B tests are important because they bound the final solution and
should not be repeated without new evidence.

| Experiment | Result | Conclusion |
| --- | --- | --- |
| Parse body at `+8` | Failed | The parser's `body + 5` geometry is correct. |
| Global continuation extraction at `TX_COUNT` instead of `TX_COUNT+1` | Broke report-descriptor continuation | Never apply the GET6 continuation rule globally. |
| Add the six Windows ToDevice tail bytes to create a 16-byte request prefix | Failed | SpbCx transfer-buffer padding is not a direct physical TX template. |
| Split body into TX9 followed by RX-only continuations | Failed | TX-only did not capture the missing prefix; stale header bytes remained in FIFO. |
| Reduce first receive from 60 to 54 only | Same malformed initial body | Exact 70-byte FIFO saturation is not the root cause. |
| Reduce first receive to 9 | Continuation jumped ahead | The device/controller advances beyond the number of bytes exported by software. |
| Program RX_COUNT=60 instead of 61 with otherwise normal geometry | Byte-for-byte unchanged failure | The generic `+1` RX count alone is not the cause. |
| Reconstruct first 60 with physical RX55 | ioctl succeeds, later payload corrupt | Initial body map solved; continuation boundary still late. |
| physical RX48 | Four `ff` clocks before body resumes at body[64] | Identified the transition region. |
| physical RX52 | FIFO[64..67] = body[60..63], continuation FIFO[3] = body[64] | Exact body/continuation geometry established. |

## Safety constraints for future refactors

The working behavior depends on preserving scope.

Do not:

- change the V0 parser from `body + 5`;
- globally change AMD continuation extraction from `TX_COUNT + 1`;
- treat the 129-byte Windows SpbCx ToDevice buffer as literal physical TX;
- assume every opcode-0x0b combined transfer uses the GET6 initial FIFO map;
- move the RX52 exception into generic descriptor/read logic without separate
  hardware evidence.

The GET6 special case should be fingerprinted by all of the following:

- opcode `0x0b`;
- nine-byte request body after opcode consumption;
- 129-byte response;
- request bytes `00 00 00 ff 00 04 03 00 06`.

This keeps descriptor traffic and unrelated V0 reads on their established
controller path.

## Gate status

For the targeted Architecture-A standard HID path:

| Gate item | Status |
| --- | --- |
| HID/hidraw device `045e:0c19` | PASS |
| 936-byte HID report descriptor | PASS |
| generic HID GET_FEATURE report 6 request | PASS |
| type-5 GET_FEATURE response header | PASS |
| report ID 6 + 119 data bytes | **PASS, byte-perfect against Windows** |
| SET_FEATURE report 5 activation | Separate gate / not established by this result |
| ~4300-byte report 0x0c raw stream | Separate gate / not established by this result |

The next transport work should begin from this checkpoint rather than reopening
GET6 request framing, parser geometry, response-header handling, 0x56 ordering,
or generic descriptor continuation.

## Related material

- `docs/HIDSPI_PROTOCOL.md` — V0 protocol and synchronous feature behavior
- `docs/AMDI0060_CONTRACT.md` — generic AMD controller boundary
- `docs/AMDSPI_DECOMP.md` — Windows controller decompilation notes
- `docs/EVIDENCE.md` — evidence levels and accepted facts
- `captures/wintrace/surface_init.csv` — authoritative Windows SPB capture
- `tests/wire_frames_test.c` — byte-level request framing pins
