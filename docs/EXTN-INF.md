# SurfaceDigitizerHidSpiExtnPackage 2.4.137.0 — Directive Audit

Source: literal `SurfaceDigitizerHidSpiExtnPackage.inf` recovered from the saved SL4 Windows/Surface package. Source SHA-256: `20e13d29d2fc8e56156882ed6a191cddee03711c69731494026bcec279e03a86`.

This document describes only what the file itself proves. It does not infer runtime HID-SPI transactions.

## Bottom line

The SL4-family digitizer extension **does not install a second transport driver and does not use `.Filters` / `AddFilter`**. It binds as an Extension-class package to five Surface ACPI hardware IDs and writes four hardware-key values.

The Heat software-processor binding is in a separate `SurfaceTouchPenProcessorUpdate` extension on `HID\MSHW0231&Col02`, preserved separately in `evidence/windows/SurfaceTouchPenProcessorUpdate_13.inf`.

## Directive inventory

| INF directive / section | Literal value | Effect proved by the file | Linux equivalent / action |
|---|---|---|---|
| `Class` | `Extension` | Extends an existing device stack rather than supplying the base HIDSPI service | None by itself |
| `ClassGuid` | `{e2f84ce7-8efa-411c-aa69-97454ca4cb57}` | Windows Extension class | None |
| `ExtensionId` | `{17F19A0B-64D7-4662-8C91-C90097D12608}` | Identifies this extension package | None |
| `DriverVer` | `03/24/2020,2.4.137.0` | Exact package version recovered for SL4 family | Evidence only |
| `Standard.NTamd64` matches | `ACPI\MSHW0134`, `0162`, `0230`, `0231`, `0235` | Same extension policy applies to these Surface HIDSPI devices | Scope any Linux quirk only where hardware evidence supports it; do not generalize to PNP0C51 |
| `SurfaceDigitizerHidSpiExtnPackage.NT` | empty | No CopyFiles/service install in the base DDInstall section | No extra Linux driver implied |
| `.NT.HW AddReg` | `SurfaceDigitizerHidSpiExtnPackage.HWAddReg` | Writes device hardware-key policy values | See rows below |
| `HKR,,FriendlyName` | `Surface Digtizer HidSpi Extn Package` | Cosmetic device name | None |
| `HKR,,SelectiveSuspendEnabled` | DWORD `1` | Enables Windows selective-suspend policy for this devnode | Linux analogue is runtime PM/autosuspend policy; **no code change until Gate 2 shows lifecycle behavior** |
| `HKR,,SelectiveSuspendTimeout` | DWORD `2000` | Supplies a 2000-ms Windows selective-suspend timeout value | Possible runtime-PM autosuspend analogue; do not copy blindly |
| `HKR,,SuppressInputInCS` | DWORD `1` | Requests suppression of input in Windows Connected Standby policy | Linux s2idle/input gating is the closest concept, but exact semantic mapping is unproven and belongs to Gate 2 |

## Explicit absences

The recovered 2.4.137.0 file contains **no** `Include`, `Needs`, `CopyFiles`, `AddService`, `Services`, `AddFilter`, `.Filters`, `UpperFilters`, `LowerFilters`, `Heat`, `SoftwareProcessor`, report-descriptor override, feature-report command, or wire-protocol data.

Therefore the earlier idea that the SL4 `SurfaceDigitizerHidSpiExtnPackage.inf` itself might attach a filter is rejected by the literal file. Other Surface packages using the same family name are not evidence for this SL4 package.

## Separate Heat binding

`evidence/windows/SurfaceTouchPenProcessorUpdate_13.inf` is a distinct Extension-class package. It proves:

- match: `HID\MSHW0231&Col02`
- `DriverVer = 09/01/2020,5.127.137.0`
- `ExtensionId = {57812147-5605-4605-A884-CC5B7A0FBA45}`
- `HKR,Heat,SoftwareProcessor,REG_SZ,"%13%\TouchPenProcessor0C19.dll"`

That is the direct package-level evidence for the Windows-shaped userspace Heat architecture.

## What this INF does **not** answer

It does not answer whether Windows calls `_RST`, the runtime ordering of `_INI/_PS0/_PS3`, post-RDESC feature traffic (ID5/ID6/0x56), or whether finger-down produces report `0x40`, CapImg into Heat, or both. Those remain Gate 2 lifecycle-capture questions.
