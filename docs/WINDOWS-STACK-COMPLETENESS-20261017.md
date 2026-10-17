# Windows side: complete stack and evidence gap audit (2026-10-17)

> **Authoritative post-history-search update.** Consult this page before calling any
> Windows DLL, firmware, trace or decompilation source "missing." Scope: Surface
> Laptop 4 AMD **MSHW0231 / HID 045E:0C19 (13-inch)**, not 0C18/15-inch.
> This is a **source inventory and research gap report**, not a tested Windows
> driver replacement or authorization to change Gate5/PR #87/#88.

## What “complete Windows side” means

There are two different completion targets:

* **A deployable Windows installation**: correctly matched Windows installation,
  inbox HID/SPI/Heat components, Microsoft Surface AMD driver/firmware MSI,
  local PnP/ACPI/registry settings, and device firmware. One *file* cannot
  recreate a complete Windows installation; Microsoft's supported cumulative
  MSI handles Surface-specific installation, while inbox drivers ship with Windows.
* **A faithful Linux implementation of Windows multitouch behavior**: transport
  activation + actual CapImg segmentation/classification + configuration/quality
  state + contact association/hold/lift + group/postprocessing + **published**
  touch ID/XY/lift results. Having all DLL files alone cannot prove this.

## Verified historical recovery that MUST NOT be redone

Original Git history commit:
[`c94c399618b23588c95711ab4449d9400036ffd0`](https://github.com/avgbob/SL4A_TouchScreen/tree/c94c399618b23588c95711ab4449d9400036ffd0).

* **Original 0C19 processor DLL already in Git history**:
  `docs/decomp/heat_resources_20260716/artifacts/0C19/TouchPenProcessor0C19.dll`
  (9,770,336 bytes; historical SHA-256
  `f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`).
  The user's installed DLL at
  `C:\Windows\System32\DriverStore\FileRepository\surfacetouchpenprocessorupdate.inf_amd64_2f7c805dc6a4f0fa\TouchPenProcessor0C19.dll`
  has matching historical MD5 `de83210b2299aaba5c2c9819f166c0fe`,
  and the historical SHA-256 is independently listed in the recovered metadata.
  Its INF (version 5.127.137.0) registers
  `HKR,Heat,SoftwareProcessor="%13%\TouchPenProcessor0C19.dll"` for
  `HID\MSHW0231&Col02`.
* Companion 0C18 original DLL/INF/CAT are also preserved in
  `docs/decomp/heat_resources_20260716/artifacts/0C18/`; **0C18 is not the
  0C19 target**. Their sections differ; don't substitute its constants.
* **468 complete TouchPenProcessor decompiled C function bodies**:
  `docs/decomp/touchpen0c19_fullheat_20260716/functions/`, indexed and pinned
  in `docs/RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json`, including
  `180601690` classifier and `180606370` quality-gated hold. The user's
  Ubuntu Git repo resolves these objects, and the archive was extracted to
  `~/sl4a-evidence-recovered/`.
* The historical `docs/decomp/heat_resources_20260716/msi/SurfaceUpdate/`
  tree contains **262 tracked payload files** from
  `SurfaceLaptop4_AMD_Win11_22631_26.040.2105.0.msi` (historical version),
  including `amdspi.sys`, `SurfaceHidMiniDriver.sys`,
  `SurfaceDigitizerHidSpiExtnPackage.inf/.cat`,
  both TouchPenProcessor extension INF/CAT/DLL packages,
  `SurfaceTouchFw.inf/.cat` for 13 and 15 inches, and display/TCON packages.
  **262 tracked files is not the original complete .msi**: the historical tree
  does *not* contain the original MSI installer nor either
  `SurfaceTouchFw_5.0.132.139.bin` firmware payload despite hashes documented
  in `docs/SL4_MSI_Mining_Report.md`. Never call this tracked extraction a
  ready-to-install package.
* **Sensor and transport**: report descriptor (936 bytes); CapImg 72 x 48 x
  8-bit raster within 4,304-byte body; 1,422 complete authentic Windows raw
  frames (537 touch + 247 init + 638 boot); original 398,721,024-byte
  `C:\gate2\gate2.etl`, 3,254,430 decoded event entries, 0 lost; actual
  driver lifecycle and 2026-10-16 one-device PR87 cold-first-HID test.
  These do not contain a verified Windows published-contact ID oracle.
* Historical static HeatCore evidence exists in
  `docs/decomp/MULTITOUCH_STATIC_DECOMP.md` and
  `docs/decomp/HEATCORE_REPORT_TABLE.md`, with function addresses; it is
  *not the same thing* as having the full HeatCore binary/exported decompiler
  closure available in current or historical Git trees.

Source hash anchors:
`docs/decomp/heat_resources_20260716/metadata/artifact-sha256.txt`;
`docs/decomp/heat_resources_20260716/REPORT.md`;
`docs/SL4_MSI_Mining_Report.md`.

## What is **actually** missing or unverified, ranked by importance

| Priority | Evidence / file | Current status | Why it matters |
|---|---|---|---|
| **P0** | Original `HeatCore.dll` from **this** Windows installation, exact SHA-256, version/build | **Not yet recovered/hashed in preserved repo or Windows operator scan** | Hosts CapImg transfers, invokes plugin, translates emitted contacts into Windows HID/pointer records. Static HeatCore *summaries* exist, but source `heatcore_20260716/functions/*` (e.g., `1800047f0`, `180015ff0`, `1800351a0`) was **not found at current tips or historical paths queried**. Windows reports on other Surface models place HeatCore.dll in `C:\Windows\System32`; this laptop's System32 was NOT searched by the earlier Windows search. Check exact path FIRST. |
| **P0** | Windows **final** per-frame contact coordinates, IDs, confidence/tip/lift from same gesture as raw heatmaps | **Not established** | Without this, no measurable Windows behavior fidelity. July ETW CSVs lack `Microsoft.Surface.TouchAndPen.Prod` event types; Gate2 provider summary likewise has no named TouchAndPen output. The existing WPR profile `tools/windows_capture/touch_boot.wprp` ALREADY includes provider GUID `3fa102e9-1a62-5490-7af8-6088c2f9e6be`, and `capture_runtime.cmd` targets `TouchBlobCoMX/Y`. Those fields are computed centroids, **not necessarily identical** to OS-visible Contact ID, Tip, Confidence, and final coordinates. A parallel OS-pointer/HID observation may be needed. |
| **P0** | Exact HeatCore plugin-contact-to-final-pointer/HID ABI and publication gating | **Partial code notes, no independently replayable HeatCore implementation** | Windows plugin 0x34 contact record, 0x3A pointer record and 0x21 HID injection record are **different** layouts; tracks/groups and OS IDs must not be equated. Need direct decomp/function-body return edges for `HeatDevice::FinalizeContactFrame(0x1800047f0)`, `HeatHidInjectionProvider::InjectHeatContactFrame(0x180015ff0)`, `HeatPointerInputReporter::ReportTouchContactFrame(0x1800351a0)`. |
| **P1** | Runtime detector config/calibration/gain producers and device firmware identity | **Partial, unverified dynamic source** | 0C19 static matrices and thresholds exist. Offsets `+0xE20/+0xE60/+0xEA0` are statically zero, but producers unknown. Per-device state fills detector gates. Source of calibrated coefficients, background adaptation, panel mapping, and firmware telemetry still require typed xrefs/runtime values; vendor CapImg section `0xff00` is **not** proved to hold detector thresholds. |
| **P1** | Exact Windows `hidspi.sys` / `HidSpiCx.sys`, `HeatCore.dll` runtime versions and hashes, selected OEM driver/INF registrations | **Windows inbox components not in Surface MSI** | Useful to reproduce exact Windows transport and identify actual host/bindings, especially when comparing dynamic execution to the decomp notes. We already have some HID-SPI/HidSpiCx snippets in historical `docs/decomp/clean/`, but no full recovered inbox binary closure. |
| **P1** | Operating `HeatCore.dll` host/loaded module list and PnP/registry `Heat\SoftwareProcessor` values from user laptop | **Capture kit exists; runtime results not verified** | Distinguishes Windows process owning callbacks, active processor version, actual binding, live panel variant, and any dynamically selected parameters. Existing `collect_touch_host.cmd` and `.ps1` are already in repo. |
| **P2** | Actual 13-inch `SurfaceTouchFw_5.0.132.139.bin` payload and *current installed controller firmware version* | **Historical firmware SHA documented; binary not in preserved tracked MSI tree** | Useful only for identifying firmware-versus-host differences; do not assume firmware package bytes equal current flashed state. Hash 13-inch `1b1ac21dbdcceaecc56c69e1120b92f0647c6fb73c7125b861ceb9d089e36d4d`; 15-inch different. |
| **P2** | Original signed installable Microsoft MSI, latest cumulative package | **Not tracked in historical Git**; official current file available separately | Needed for packaging/restoring Windows, not for a Linux tracker port. Microsoft's current Surface Laptop 4 AMD download (2026-08-14) is `SurfaceLaptop4_AMD_Win11_22631_26.072.27963.0.msi`, ~701.8 MB. This is **newer than** historical extracted 26.040.2105.0. |
| **P2** | Microsoft `TouchPenProcessor.pdb`, HeatCore/PnP symbols | **Not verified present** | Would simplify naming indirect callbacks and struct fields, but binary/Ghidra analysis can proceed without them. Embedded TouchPen PDB build path is not evidence that private symbols can be downloaded. |
| **P3 / independent** | Producer/semantic decoder for Feature ID `0x56` | **Unresolved and unrelated to HeatCore's proven Feature ID5 mode path** | Do not add ID56 magic bytes to Linux based on a single Windows trace; PR87/Gate5 testing showed relevant operations without proving its necessity. |

## Component chain, with proof boundary

```text
MSHW0231 capacitive panel / firmware
  -> AMD SPI/GPIO + SPB (amdspi.sys; GPIO driver / SpbCx)
  -> Windows HIDSPI.sys / HIDSPICx.sys + ACPI / HIDCLASS
  -> Col02 CapImg (frame-data 0x0C, Heat reporting Feature ID5)
  -> HeatCore.dll HOST + TouchPenProcessor0C19.dll plugin
        parser -> peak/candidate -> class -> association -> state/hold
        -> 0x34 local contact records (group/track indexes NOT OS IDs)
  -> HeatCore finalization / report/injection
        -> 0x3A pointer input record OR 0x21 injection report
  -> Windows touch/pointer stack: Contact ID, X/Y, Tip, Confidence, count
```

Microsoft's Windows HID touchscreen requirements include Contact ID, X/Y,
Tip, Contact Count and report framing. For ID continuity and lift, the
**published Windows HID/pointer lifecycle** matters, not merely the DLL's
internal track number or raw thresholded sensor blob.

## New history-search verification (2026-10-17)

Queried the repository's *entire tracked tree* of `c94c399` (1,001 blob
entries). Found original `TouchPenProcessor0C19.dll` and `0C18.dll`,
the static configurations, embedded resources and 262-file MSI extraction.
Did **not** find original `HeatCore.dll`, `hidspi.sys`,
`HidSpiCx.sys`, `TouchPenProcessor.pdb`, the uncompressed 13/15
`SurfaceTouchFw_5.0.132.139.bin` payloads, or the original full MSI.
Queried Git history **by specific HeatCore decomp paths**, including
`docs/decomp/heatcore_20260716/functions/180015ff0_FUN_180015ff0.c` and
`180016e10_FUN_180016e10.c`: **no commits found at those exact paths**.
Absence from inspected historical paths is NOT proof no other file name or
off-repository copy exists.

The 468-function TouchPen closure has indirect CFG/vtable calls and no PDB;
"complete exported function bodies" does not mean complete recovered Windows
behavior or resolved runtime state.

## Exact targeted next Windows inspection (read-only)

Use **PowerShell as administrator** on the already-installed Windows.
This checks targeted OS locations that the prior search **omitted**
(`C:\Windows\System32` and `C:\Windows\System32\drivers`). It creates a
small inventory report in the user's Desktop; it does not install, replace,
rename or modify any driver.

```powershell
$names = @(
 'HeatCore.dll','hidspi.sys','HidSpiCx.sys','hidclass.sys',
 'SpbCx.sys','Vhf.sys','amdspi.sys','amdgpio2.sys',
 'TouchPenProcessor0C19.dll','SurfaceHidMiniDriver.sys'
)
$roots = @(
 "$env:windir\System32",
 "$env:windir\System32\drivers",
 "$env:windir\System32\DriverStore\FileRepository"
)
$rows = foreach ($name in $names) {
 foreach ($root in $roots) {
  Get-ChildItem -LiteralPath $root -Filter $name -File -Recurse -ErrorAction SilentlyContinue |
   ForEach-Object {
    $f=$_
    $v=$f.VersionInfo
    [pscustomobject]@{
     Name=$f.Name; Path=$f.FullName; Bytes=$f.Length
     Version=$v.FileVersion; SHA256=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    }
   }
 }
}
$rows = @($rows | Sort-Object Path -Unique)
$rows | Format-Table -AutoSize -Wrap
$rows | Export-Csv "$env:USERPROFILE\Desktop\sl4a-windows-component-inventory.csv" -NoTypeInformation
Write-Host "Matches: $($rows.Count)"
```

For installed PnP bindings, additionally use
`Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceID -match 'MSHW0231|MSHW0230|AMDI0060' } | Select-Object DeviceName,DeviceID,InfName,DriverVersion,DriverProviderName`.
The exact `Heat\SoftwareProcessor` live registry value can be exported after
identifying the target PnP key. **Never modify the values during audit**.

For tracing final output, **inspect existing ETLs first** for provider GUID
`3fa102e9-1a62-5490-7af8-6088c2f9e6be`. If genuinely unavailable,
reuse `tools/windows_capture/touch_boot.wprp` +
`capture_runtime.cmd` + `export_runtime.cmd`, with deliberate 1-finger,
2-finger, close-finger, lift gesture timestamps, and gather the matching
Windows OS-facing pointer/HID contacts. Preserve exact ETL and exporter data.
Do not conflate TouchBlobCoMX/CoMY centroid with published Touch contact ID.

## External references (checked 2026-10-17)

* [Microsoft: Surface Laptop 4 AMD official driver MSI](https://www.microsoft.com/en-us/download/details.aspx?id=102923), 2026-08 package `26.072.27963.0`.
* [Microsoft: HID-over-SPI driver stack](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/architecture-and-overview-for-spi): OS HIDSPI, SPB controller, GPIO, ACPI, HIDSPICx roles.
* [Microsoft: touchscreen mandatory HID collections and contact lifecycle](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/touchscreen-required-hid-top-level-collections): Contact ID, Tip, X/Y, Contact Count and lift requirements.
* [Microsoft: Virtual HID Framework](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/virtual-hid-framework--vhf-): generic Windows virtual HID source-driver model (not proof Surface HeatCore uses VHF for its specific egress).
* Earlier reports of `C:\Windows\System32\HeatCore.dll` exist in Microsoft Q&A Surface threads, **other device models only**: verify on this SL4; do not infer its presence here from those cases.

## Required future-work rules

1. Open this file, `AGENTS.md`, `RESEARCH-INDEX.md`, the historical index,
   and `RESEARCH-CONTRADICTIONS.md` **before** new captures/files requests.
2. "Binaries absent" was **false for 0C19 and 0C18**. Correct D14 and D20
   instead of repeating that misinformation.
3. **No new raw-only capture.** First locate the OS-facing contact oracle and
   Windows HeatCore host; then port the actual recovered functions in isolated
   research PR #12 with real-frame and adversarial tests.
4. Keep all production Gate5 and upstream PR #87/#88 source and rollback paths
   separate from this evidence/comparison work.
