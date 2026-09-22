> Repository path: `docs/SL4_MSI_Mining_Report.md`
>
> Provenance: recovered August 2026 analysis of `SL4-MSI-MINE.zip`. The body below is preserved unmodified; this header only records its repository destination and provenance.

# Surface Laptop 4 AMD – Microsoft MSI Mining Report

Source bundle analyzed: `SL4-MSI-MINE.zip`

## Immediate conclusions

### 1. The August 2026 Surface package does not contain a newer AMD SPI transport driver

The `amdspi.sys` in the current Microsoft Surface Laptop 4 AMD MSI is byte-for-byte identical to the `amdspi.sys` previously exported from the working Windows installation.

- SHA-256: `7b7df209364b1092ba9fac00b2cb12622819de3c21a64d924860ac4c297231cb`
- File version: `1.0.0.101`
- PE build timestamp: 2020-11-04
- Embedded PDB path: `E:\Drivers_-_FCH_-_IO\amdspi\Dbuild101\CloneRepo\Source\Windows\amdspi\x64\Release\amdspi.pdb`

The AMD INF is also identical:

- SHA-256: `0ec4d29d51d3810f89c2aab532c5b371ee91e46ad37aef122f26ba14e89696e2`

The Surface Digitizer HID-SPI extension INF is also identical:

- SHA-256: `20e13d29d2fc8e56156882ed6a191cddee03711c69731494026bcec279e03a86`

So the newer Microsoft MSI does not hide a later AMDI0060 implementation.

## 2. The MSI directly proves the Windows Heat processing binding for MSHW0231

The 13-inch Surface Touch Pen Processor extension contains:

- Match: `HID\MSHW0231&Col02`
- Registry binding: `HKR,Heat,SoftwareProcessor,REG_SZ,"%13%\TouchPenProcessor0C19.dll"`
- Driver version: `5.127.137.0`
- Extension ID: `{57812147-5605-4605-A884-CC5B7A0FBA45}`

`TouchPenProcessor0C19.dll`:

- SHA-256: `f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`
- Size: 9,770,336 bytes
- Version: `5.127.137.0`
- PE timestamp: 2020-09-01
- PDB path: `C:\w\69\b\Release\x64\bin\TouchPenProcessor.pdb`

Important exports include:

- `CreateHeatProcessor`
- `SurfaceHeatProcessor::GetProcessorCapabilities`
- `HandleRegionConfigMessage`
- `HandleSystemContextMessageDisplayChange`
- `HandleSystemContextMessageHingeAngle`
- `HandleSystemContextMessageInputStitching`
- `OnDeviceAttached`
- `OnDeviceDetached`
- `OnDeviceReset`

Strings include `TelemetryUpdateFromFW`, `TelemetrySectionReceived`, `CalibrationMapsNotCompatible`, and `FwSendingTelemetryCount`.

This is strong evidence that Windows treats Col02 as a Heat/CapImg software-processing path, not merely as a normal HID touch collection.

## 3. Product 0x0C19 config table registration is confirmed

The DLL registers product ID `0x0C19` with config-table VA:

`0x1808E0460`

This exactly matches the base documented by the SL4A reverse-engineering project.

The same registration routine maps `0x0C18` to a different table, consistent with the separate 15-inch MSHW0230/TouchPenProcessor0C18 package.

## 4. Most documented SL4A constants are verified — but one is definitely wrong

At the 0x0C19 config base:

| Offset | Current Microsoft DLL |
|---|---:|
| +0x8C0 | 0.6112089753 |
| +0x8C4 | **0.7553579807** |
| +0x8D0 | 0.9665120244 |
| +0x8D4 | 0.2281399965 |
| +0x8DC | 0.5450090170 |
| +0x8E0 | 1.2180980444 |
| +0x8E4 | 1.5492459536 |
| +0x8E8 | 1.8454920053 |
| +0x8EC | 2.1612279415 |
| +0x958 | 0.1700000018 |
| +0xC98 | 36.0 |
| +0xECC | 0.0399999991 |

SL4A currently documents +0x8C4 as `0.754732`.

The exact IEEE-754 representation of `0.754732` (`1e 36 41 3f`) does **not occur anywhere** in this DLL.

By contrast, `0.7553579807` appears repeatedly in the per-product config records.

This looks like a documentation/transcription mismatch rather than floating-point rounding.

## 5. Two ranges currently described as runtime-zero data are not zero

The SL4A config documentation currently labels several ranges as zero in the static DLL and populated at runtime.

That is true for:

- `+0xE20 .. +0xE48` — all zero
- `+0xE60 .. +0xE98` — all zero
- `+0xEA0 .. +0xEC0` — all zero

But it is **not** true for two other documented ranges.

### +0xD40 .. +0xD78

This is structured static byte data, not a zero-filled 10×11 float matrix.

For the 0x0C19 table, the beginning is:

`20 27 FF FF  2C FF FF FF  14 FF FF FF  1B FF FF FF ...`

Interpreting those 32-bit words as floats produces NaNs.

The corresponding 0x0C18 table has a different structured pattern:

`25 FF FF FF  2A 31 FF FF  12 FF FF FF  19 1E FF FF ...`

Across many product config tables, this area changes in organized groups of byte indices and `0xFF` sentinels. It is therefore much more consistent with a product-specific index/geometry/adjacency structure than a Mahalanobis float matrix.

Exact semantics still need code-xref recovery.

### +0xED0 onward

This range is also static and highly structured.

For 0x0C19:

- +ED0 = 0.12
- +ED4 = 0.06
- +ED8 = 0.055
- +EDC = integer 20

Then follows a 20-entry pair table:

| x | stored integer |
|---:|---:|
| .025 | 41 |
| .030 | 59 |
| .035 | 80 |
| .040 | 105 |
| .045 | 133 |
| .050 | 164 |
| .055 | 198 |
| .060 | 236 |
| .065 | 277 |
| .070 | 321 |
| .075 | 369 |
| .080 | 419 |
| .085 | 473 |
| .090 | 531 |
| .095 | 591 |
| .100 | 655 |
| .105 | 722 |
| .110 | 793 |
| .115 | 867 |
| .120 | 944 |

The integer column is essentially:

`round(65536 * x^2)`

Examples:

- `0.025² × 65536 = 40.96 → 41`
- `0.050² × 65536 = 163.84 → 164`
- `0.100² × 65536 = 655.36 → 655`
- `0.120² × 65536 = 943.7184 → 944`

So this is plainly a fixed-point quadratic lookup table or a structure containing one. It is **not** an all-zero runtime regional-sensitivity map.

The 0x0C18 table contains the same quadratic lookup but differs at one preceding parameter (+ED8 = 0.045 instead of 0.055), further suggesting product/panel-specific tuning.

## 6. The 13-inch and 15-inch touch firmware payloads differ

Both packages carry a file named:

`SurfaceTouchFw_5.0.132.139.bin`

and both are 390,458 bytes, but their hashes differ:

13-inch / MSHW0231-associated package:

`1b1ac21dbdcceaecc56c69e1120b92f0647c6fb73c7125b861ceb9d089e36d4d`

15-inch package:

`b14132f39589f267463783627c34828323dd3f35104ae2bf67e183e43b573404`

So equal firmware version labels do not mean identical panel payloads.

## 7. SurfaceSystemTelemetryDriver is present but requires further xref work

`SurfaceSystemTelemetryDriver.sys`:

- SHA-256: `19dee00fe1d6a328b844c79d519c1a853ab95d9c38f451ee57de3b839c9b2b0e`
- Version: `2.27.137.0`
- PDB: `C:\w\1443\b\Release\x64\bin\SurfaceSystemTelemetryDriver.pdb`

Interesting strings/imports:

- `SMF_DATA_BLOB`
- `C0Blob`
- `ACPI`
- `\DosDevices\C:\SmfTelemetrySpec.txt`
- `ExGetFirmwareEnvironmentVariable`
- `RtlDecompressBuffer`
- file/registry APIs

However, the TouchPenProcessor DLL itself exposes firmware-telemetry behavior through its Heat processor interfaces. The exact claim that the missing calibration coefficients specifically flow through SurfaceSystemTelemetryDriver should therefore be treated as not-yet-proven until the producer/consumer path is traced.

## Best next targets

1. Test SL4A **standard HID mode** on a clean Linux boot before touching raw mode.
2. Do not load the old linux-surface `spi-hid` module again.
3. Recover code xrefs/consumers for the `+D40` structured index table.
4. Recover the consumer of the `+ED0` fixed-point quadratic LUT.
5. Capture the Windows inbox `hidspi.sys`, `HidSpiCx.sys`, and `HeatCore.dll` later; they are not in the Surface MSI.
6. Compare the recovered data with labelled raw CapImg frames before changing SL4A raw-mode tuning.

The current MSI materially validates the SL4A reverse engineering, but it also exposes at least two documentation/config-table discrepancies that are worth reporting upstream.