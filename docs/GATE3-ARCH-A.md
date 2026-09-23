# Gate 3 — Architecture A transport checkpoint

Gate 2 is closed PASS. The accepted Windows capture is the evidence source, but
this branch also carries this audit because the first Gate-2 normalization
compressed several lifecycle details.

## Scope of the first checkpoint

The first hardware checkpoint is **enumeration / disable->enable parity**. It is
not yet a suspend/resume qualification run.

Observed Windows T2 activation target:

```text
_PS0
_RST
DEVICE_DESC
936-byte RPT_DESC
SET_FEATURE 0x56
GET_FEATURE ID6
read and validate ID6 response
SET_FEATURE ID5=1
live 0x0C transport
```

The Gate-3 raw profile therefore explicitly requests:

```text
wire_double_opcode=0
read_frame_variant=0
skip_getfeat=0
raw_no_enable=1
gate3_observe_only=1
```

This intentionally differs from the older Linux field-qualified raw dialect.
A failure is useful evidence: the point is to measure the Windows-observed
shape without a fallback silently replacing it.

## What Gate 2 actually established

### ACPI

Cold boot contained two `_PS0` evaluations; the second is immediately followed
by `_RST`. T2 disable/enable also contains an earlier `_PS0` before disable,
then `_PS3`, and later enable `_PS0 -> _RST`.

The activation transition this checkpoint copies is therefore specifically the
observed **activation `_PS0 -> _RST` pair**, not a claim that those are the only
ACPI calls Windows makes.

### T2 post-RDESC sequence

For the disable->enable lifecycle, the captured order is:

1. 936-byte report descriptor
2. `SET_FEATURE 0x56`
3. `GET_FEATURE ID6`
4. valid ID6 response (content ID 6, total content length 122)
5. `SET_FEATURE ID5=1`
6. live `0x0C` bodies

Gate 3 stops before ID5 in observe-only mode if the ID6 reply is absent or does
not match that observed response shape.

### Command padding and the 0x56 payload

The final three bytes of the 14-byte ID5 frame are outside ID5's one-byte
semantic payload. Gate 2 observed multiple values in those pad bytes
(`D7 FC 6E`, `00 00 00`, and `A1 01 00`), so they are **not** a universal
ID5 key/check trailer.

The six bytes inside report `0x56` are different: they are semantic report
payload. Older checked-in capture evidence used `BD 0C EE 5B 44 4C`; the Gate-2
golden run used `D9 D7 FC 6E 79 4C`. The source/generation rule for those six
bytes is currently **UNKNOWN**. The existing builder is therefore a historical
fixture, not proven byte-exact Windows behavior for every boot.

This unresolved payload is a Gate-3 audit item; do not hide it by calling the
current builder "Windows-identical."

### SPB transfer sizes

Gate 2 records SpbCx transfer-descriptor buffers, including 4309-byte TX and
4309-byte RX buffers for live raw reads. It does **not** expose the AMD
controller's physical TX_COUNT/RX_COUNT for those requests. Therefore the trace
does not prove that 4309 request bytes were physically clocked on SPI.

The current Linux short-request/segmented-controller issue remains open and is
not changed by the first checkpoint.

## Suspend / resume is a separate contract

The T5 trace is not a replay of T2:

- before sleep Windows sends an all-FF `SET_FEATURE 0x56` stop frame;
- then `_PS3` executes;
- resume executes `_PS0 -> _RST`;
- no 936-byte RDESC read was observed after resume;
- no GET_FEATURE ID6 was observed after resume;
- ID5 writes occur with differing pad bytes;
- a keyed `0x56` appears later before the post-resume raw stream.

The current Linux resume implementation still forces rediscovery and therefore
does **not** claim Windows resume parity. Do not use suspend/resume as the first
Gate-3 acceptance test.

## Caller ownership is still open

The SPB request events around T2 show different submitting PIDs:

- `SET_FEATURE 0x56`: PID 2216
- GET6 / ID5 path: PID 15596
- SpbCx buffer execution: PID 4 (System)

The names/roles of PID 2216 and PID 15596 have not yet been resolved. Until
they are, do not assume all post-RDESC feature traffic belongs in the kernel
HID-SPI transport. It may cross the HID/Heat software-processing boundary.

## Branch behavior for the first checkpoint

- explicit ACPI activation `_PS0 -> _RST`;
- IRQ is armed before direct DESCREQ;
- raw checkpoint uses single-opcode writes and reference read-approval shape;
- post-RDESC T2 ordering is `0x56 -> GET6/reply -> ID5=1`;
- ID6 must validate before ID5 in observe-only mode;
- duplicate DONE-time `0x56` is disabled;
- legacy watchdog and generic ACPI recovery cannot rewrite a failed first trace;
- heatmap detector/tracker stays frozen.

## PASS-to-next-step evidence

For a fresh activation / re-enable run:

1. `GATE3: activation _PS0 -> _RST`
2. DEVICE_DESC received
3. 936-byte report descriptor received
4. exactly one checkpoint `SET_FEATURE 0x56`
5. GET_FEATURE 6 plus a valid ID6 response
6. SET_FEATURE ID5=1 only after that response
7. sustained live `0x0C` bodies after a finger gesture

A failure at any step is the result. Do not inject a legacy fallback and then
call the later success parity.

## Do not do yet

- no blob/association/ghost tuning;
- no new retry policy;
- no requirement for transport-level report 0x40;
- no controller padded-read patch inferred from SpbCx buffer lengths;
- no claim that suspend/resume matches Windows;
- no hardcoding of the Gate-2 `0x56` six-byte payload as a universal key.
