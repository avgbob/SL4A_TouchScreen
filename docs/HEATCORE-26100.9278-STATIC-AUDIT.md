# HeatCore.dll 10.0.26100.9278 — uploaded original binary, static ABI audit

**Audit:** 2026-10-17. **Source:** user-provided `HeatCore.dll`, copied
read-only from `C:\Windows\System32\HeatCore.dll` into a Desktop analysis
directory and then uploaded to the conversation, mounted at
`/mnt/data/HeatCore.dll`. **SHA-256 (independently recomputed with
`sha256sum`):** `b295b095acf574007b894f841ef083e8cb06a72a256ee0bb75b4be80f2fcd5df`;
**size** 401,408 bytes. Operator PowerShell version:
`10.0.26100.9278 (WinBuild.160101.0800)`.

**Method:** offline **GNU objdump `-p`, `-h`, `-d -M intel`** on the
uploaded x64 PE, extraction of RSDS CodeView debug identifier, decoding
`.pdata` 12-byte runtime-function entries, raw string file-offset
identification (here `.rdata` offset matches its RVA), and resolving
RIP-relative string references into code/function ranges. No Ghidra,
Capstone, or PDB was available to this environment. These results are
**disassembly observations** with no dynamic execution and no assumption that
old Windows builds share addresses.

## PE identity and instrumentation

| Property | Measured value |
| --- | --- |
| PE file | PE32+, x86-64 DLL, 8 sections |
| Image base | `0x180000000` |
| `.text` RVA / size | `0x1000` / `0x42f8c` |
| `.rdata` RVA | `0x45000` |
| `.pdata` RVA / size | `0x5c000` / `0x3c54` |
| Exception-function entries | 1,287 |
| PE export | `InitializeHeatFramework` RVA `0x27eb0` (only named PE export) |
| CodeView signature | `RSDS` |
| PDB name | `HeatCore.pdb` |
| RSDS GUID | `31a85ffb-f083-727f-3685-eb1018957e96` |
| RSDS age | `1` |
| Trace-related embedded names | `Microsoft.Windows.Heat.HeatCore`, `Microsoft.Windows.Heat.HeatCore.Test`, `Microsoft.Windows.Heat.HeatCore.Perf` |

The PE COFF TimeDate field is a reproducible-build hash, **not** a
trustworthy build date. Its PDB GUID/age are identifiers, not evidence
that a downloadable private PDB is available.

The import table includes `HID.DLL` functions
`HidP_SetUsageValue`, `HidP_GetCaps`, `HidP_GetSpecificValueCaps`,
`HidP_GetUsageValue`, and `HidP_GetUsageValueArray`; and
`CoreMessaging.dll` `CoreUICreate`. No direct conclusion about final
touch publication should be drawn from import presence alone: this code also
makes indirect/vtable calls.

## Matching-build contact code landmarks

Function boundaries below are based on PE `.pdata`; function associations
are grounded in direct references to the embedded, exact function-name strings
(listed in hexadecimal file/RVA offsets).

| Embedded name | String RVA | Instruction referencing string | Containing PE function RVA range |
| --- | --- | --- | --- |
| `HeatDevice::FinalizeContactFrame` | `0x47a38` | `0xf747` | `0xf730..0xf833` |
| `HeatDevice::FinalizeContactFrameInternal` | `0x4b880` | `0x33d60` | `0x33d50..0x33dcc` |
| `HeatHidInjectionProvider::InjectHeatContactFrame` | `0x47f08` | `0x14a2e` etc | `0x14900..0x14be7` |
| `HeatInjectionProviderManager::InjectHeatContactFrame` | `0x47c88` | `0x13ac5` | `0x13ab0..0x13d0e` |
| `HeatPointerInputReporter::ReportTouchContactFrame` | `0x4ba30` | `0x34f8c` | `0x34f60..0x35134` |
| `DedicatedThreadProcessorHost::FinalizeInternalContactFrame` | `0x49c10` | `0x2cf17` | `0x2cf00..0x2d063` |
| `HeatProcessorAdapter::ExecuteFrameProcessing` | `0x478c8` | `0xa1da` etc | `0xa0bc..0xa3fc` |

These functions' **logging labels and associated bodies** were found on this
exact uploaded build. Several are wrappers which dispatch through a vtable;
the precise indirect callback target and final HID/pointer publication are
**not determined merely by the string reference**.

**Historical-address regression:** the old static report cited
`0x1800047f0` finalization, `0x180015ff0` HID injection, and
`0x1800351a0` pointer reporter. None is a **function start** in the
uploaded DLL's `.pdata`: the RVA `0x47f0` is inside
`0x47a0..0x486d`; `0x15ff0` inside `0x15f3c..0x16c99`; and
`0x351a0` inside `0x35140..0x352e3`. These old addresses **cannot be
transplanted into 26100.9278 unchanged**. Use the newly identified starts
above, checking caller context as needed.

## Direct HID injection format conversion — strongest result

At function RVA **`0x14900`**, the input frame's type field is compared
at `[rdx+0x10]`. Branches handle at least three distinct formats:

| Input frame type (at +0x10) | Input source stride | Output record stride | Conversion |
| --- | --- | --- | --- |
| `1` | `0x3a` (58 bytes) | `0x21` (33 bytes) | Copied inline at `0x14955..0x149c4` |
| `2` | `0x3c` (60 bytes) | `0x23` (35 bytes) | Helper starts `0x3ac50` |
| `3` | `0x48` (72 bytes) | `0x1d` (29 bytes) | Helper starts `0x14bf0` |

For type 1, instruction-level source-to-output contact-field map
(*offsets relative to the beginning of each contact record; not assumed
semantic names*):

| Source offset/size (0x3A record) | Output offset/size (0x21 record) | Instruction RVA |
| --- | --- | --- |
| `+0x0A` / u8 | `+0x00` / u8 | `0x14987` |
| `+0x08` / u16 | `+0x01` / u16 | `0x1497e` |
| `+0x13` / u32 | `+0x03` / u32 | `0x1498e` |
| `+0x23` / u32 | `+0x07` / u32 | `0x14995` |
| `+0x2B` / u32 | `+0x0B` / u32 | `0x149aa` |
| `+0x17` / u32 | `+0x0F` / u32 | `0x1499c` |
| `+0x27` / u32 | `+0x13` / u32 | `0x149a3` |
| `+0x2F` / u32 | `+0x17` / u32 | `0x149b1` |
| `+0x33` / u16 | `+0x1B` / u16 | `0x149b8` |
| `+0x35` / u32 | `+0x1D` / u32 | `0x149c1` |

The code zeros output record buffers before copying these fields.
Type-1's packet builder puts marker `1` at output header byte 0,
contact **packet count** at byte 1, and the input frame's `+0x08`
WORD into output header bytes 2–3. Output contact records start at
packet offset `+4`. Type 1 and type 2/3 output processing includes
a vtable transmission call; identifying that interface by dynamic type
or vtable remains future work.

For type-1 and type-2 processing, the function uses `cmp ...,5` to send
up to **five contacts per packet** before resetting packet count.
Do **not** mistake this for a maximum of five tracks, fingers, or the
source record's capacity. The processor has independent larger track
capacity.

The type-2 helper at `0x3ac50` copies source u16 `+0x08`
to output `+0x01` and source u8 `+0x0a` to output
`+0x00`, along with other fields. The type-3 helper at
`0x14bf0` copies a different selection. Exact meanings
(contact identity, coordinate units, pressure, history or confidence)
**are not proved by field width alone**.

## Windows touch pointer reporting — decoded field movement

`HeatPointerInputReporter::ReportTouchContactFrame` is associated with
function range **`0x34f60..0x35134`** by a direct string xref at
`0x34f8c`. Code at `0x35032..0x350b3` loops over input records
with **`0x20`-byte** (32-byte) stride and writes output records
with **`0x3a`-byte** (58-byte) stride.

The output's first QWORD is initialized to `0x3a` at `0x35040`.
Input u16 at `source+0` is copied to output `+8` at `0x35048`.
Input flags byte at `source+2` is masked/tested for **`1,2,4`**
(`0x35050`, `0x3505c`, `0x35064`) and the corresponding low
bits preserved in output byte `+10` (`0x3506c`).

Additional observed output fields:

| Input (per 0x20 record) | Output (per 0x3A record) | Observation |
| --- | --- | --- |
| `+4..+11` QWORD | `+11..+18` and `+19..+26` | QWORD duplicated |
| `+12..+19` QWORD | `+27..+34` and `+35..+42` | QWORD duplicated |
| `+20..+23` DWORD | `+43..+46` | Direct copy |
| `+24..+27` DWORD | `+47..+50` | Direct copy |
| `+28..+29` WORD | `+51..+52` | Direct copy |
| n/a | `+53..+57` | Zero-initialized |

This is **exact instruction-grounded layout movement**, not yet a complete
semantic ABI (e.g., the duplicated QWORD fields must not be called
Windows screen X/Y or predicted-history fields without matching types).
Most importantly, **the reporter preserves the three low-order flag bits
from its input**, so any multi-finger persistence analysis must trace
which stage sets/clears those bits, not assume Linux's tracker state and
Windows report state are identical.

## Reproduction / offline audit commands

```bash
sha256sum HeatCore.dll
file HeatCore.dll
objdump -h HeatCore.dll
objdump -p HeatCore.dll
objdump -d -M intel --start-address=0x180014900 --stop-address=0x180014be7 HeatCore.dll
objdump -d -M intel --start-address=0x180034f60 --stop-address=0x180035134 HeatCore.dll
objdump -d -M intel --start-address=0x180033d50 --stop-address=0x180033dcc HeatCore.dll
objdump -d -M intel --start-address=0x180014bf0 --stop-address=0x180014c54 HeatCore.dll
objdump -d -M intel --start-address=0x18003ac50 --stop-address=0x18003acb0 HeatCore.dll
```

PDB CodeView identifier may be extracted by scanning for ASCII `RSDS`,
then reading 16 UUID bytes in little-endian GUID representation and a
32-bit age, followed by a NUL-terminated filename.
On this exact build: `HeatCore.pdb`, GUID
`31a85ffb-f083-727f-3685-eb1018957e96`, age 1.

No machine's drivers, Windows registry, input injection, or PR #87/Gate5
implementation were modified in this audit; only static file reads.

## What's still required for Windows-output equivalence

1. Obtain type information or reconstruct the indirect targets of
   `0x14900`'s report-sending vtable method and `0x34f60`'s
   downstream pointer reporter call; interpret *source* types and
   field meanings from their producers, rather than names or guesses.
2. Trace origin of flags `1/2/4` and source `+0` u16 contact identifier
   back through `HeatDevice` and the 0C19 plugin's `0x34` records.
3. Capture/locate **OS-visible** contact IDs, positions and Tip/lift
   synchronized to sensor frames. `TouchBlobCoMX/Y` from TraceLogging
   are not automatically final published HID coordinates.
4. Verify actual Windows runtime configuration producers and any
   dynamic calibration values; decompilation and raw frames by themselves
   cannot prove behavioral equality.

**Future-agent warning:** The source DLL has been uploaded and analyzed.
Do not claim `HeatCore.dll` was never located, or reuse the 2026-07
HeatCore absolute address map on Windows build 26100.9278.
Use this report **together with** `docs/WINDOWS-STACK-COMPLETENESS-20261017.md`
and `docs/RESEARCH-INDEX.md`.
