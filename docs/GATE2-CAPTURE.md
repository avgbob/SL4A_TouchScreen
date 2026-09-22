# Gate 2 — Windows Golden Lifecycle Capture

Gate 0 is frozen at `0c45ddbbdf8ee41af3f178b883353439d86e3562`.
Gate 1 is closed at `882813fd8bf6cd5311f3abb3961eb34e9a3b1e2f`.
No Linux runtime change is permitted by this gate.

## Purpose

Produce one accepted-or-rejected Windows ETL answering the only lifecycle/reporting questions that can still justify a Linux transport change.

The capture is **accepted only if all four questions are answered from decoded trace evidence**:

1. **Reset** — `_RST` is observed on cold start and disable→enable, or the trace contains sufficient ACPI/HIDSPI lifecycle evidence to state that HIDSPI started without a traced `_RST`.
2. **Power** — at least one of `_INI`, `_PS0`, or `_PS3` is decoded; otherwise the ACPI provider must be proven active while those methods remain absent and D-state transitions are recovered from Kernel-Power.
3. **Post-RDESC** — state whether feature/report traffic corresponding to ID5, ID6/DeviceMode, and/or `0x56` appears before first live input.
4. **Finger-down** — state whether report `0x0C` reaches Col02, report `0x40` reaches the touchscreen collection, or both, and identify the reader/consumer process where the trace allows it.

If ACPI method decoding is missing, the capture is rejected. Missing evidence is not converted into an inferred Linux policy.

## Existing profile spine

`tools/windows_capture/touch_boot.wprp` already includes the required providers:

- ACPI Driver Trace Provider
- Microsoft-Windows-Kernel-Acpi
- Microsoft-Windows-Kernel-PnP
- Microsoft-Windows-Kernel-Power
- Microsoft-Windows-SPB-ClassExtension
- Microsoft-Windows-GPIO-ClassExtension
- Microsoft-Windows-Input-HIDCLASS
- Microsoft-Windows-Kernel-Process
- Microsoft-Surface-SurfaceHidMiniDriver
- Microsoft-Surface TouchAndPen production provider
- Surface Serial Hub / SMF / Service / OemPanel / PowerTracker providers

The Kernel-Process provider emits process and image-load events, allowing the trace to associate `TouchPenProcessor0C19.dll` with its host process when those events are present.

## Capture commands

From **Administrator PowerShell** in the repository checkout:

```powershell
cd <repo>\tools\windows_capture

powershell -ExecutionPolicy Bypass -File .\gate2_capture.ps1 -Phase Preflight
powershell -ExecutionPolicy Bypass -File .\gate2_capture.ps1 -Phase Arm -PowerOff
```

The second command starts a file-mode WPR trace using `-shutdown` persistence and then performs a full `shutdown.exe /s` rather than a hybrid shutdown. Power the Surface back on manually.

After sign-in, open **Administrator PowerShell** and run:

```powershell
cd <repo>\tools\windows_capture
powershell -ExecutionPolicy Bypass -File .\gate2_capture.ps1 -Phase Resume
```

The script drives the exact scenario:

```text
T0  WPR armed -> full shutdown -> power on
T1  desktop idle 10s
T2  pnputil disable ACPI\MSHW0231\A -> 5s -> enable -> 5s
T3  one finger down / drag / up
T4  two-finger pinch/spread / up
T5  Sleep >=15s -> resume -> one finger
T6  evidence export -> WPR stop
```

Each step is marked twice:

- `wpr -marker SL4A_GATE2::...` for ETL-clock correlation;
- `C:\gate2\marker_*.txt` and `markers.tsv` for independent wall-clock evidence.

Microsoft documents WPR file-mode `-shutdown` as persisting recording/session information over reboot and `wpr -stop` as the merge/save step after boot.

## Artifacts that must be preserved

Copy the resulting `C:\gate2` directory into `evidence/windows/gate2/` without editing the capture products. It should contain at least:

- `gate2.etl`
- `capture-manifest.json`
- `markers.tsv`
- `providers-current.txt`
- `pnputil-MSHW0231.txt`
- `pnp-device-properties.txt`
- `setupapi-MSHW0231-slice.txt`
- `powercfg-a.txt`
- `reg-MSHW0231.txt`
- report-descriptor dump, or an explicit `report-descriptor-NOT-RECOVERED.txt`

The descriptor helper runs **after** T5 so it cannot alter the initialization/first-input sequence. If user-mode `IOCTL_HID_GET_REPORT_DESCRIPTOR` cannot recover it, the same-boot report descriptor must be reconstructed from the ETL RDESC transaction before Gate 2 can pass.

## Decode output contract

The ETL itself is not the Gate-2 result. The required normalized output is:

`evidence/windows/gate2/windows-golden.jsonl`

One JSON object per observed event. Minimum vocabulary:

```json
{"t_ms":1842,"ev":"ACPI_METHOD","name":"_RST","dev":"HSPI","phase":"T0","src":"etl","status":"OBSERVED"}
{"t_ms":1855,"ev":"IRQ","gpio":"0x55","phase":"T0","src":"etl","status":"OBSERVED"}
{"t_ms":1857,"ev":"SPB_READ","n":4,"note":"RESET_RSP","phase":"T0","src":"etl","status":"OBSERVED"}
{"t_ms":4100,"ev":"HID_FEATURE","id":5,"dir":"set","phase":"T0","src":"etl","status":"OBSERVED"}
{"t_ms":9200,"ev":"HID_INPUT","id":12,"coll":"Col02","proc":"<observed process>","phase":"T3","src":"etl","status":"OBSERVED"}
```

Rules:

- `status` is `OBSERVED`; `INFERRED` is forbidden.
- Unknown timestamps are represented as `"t_ms":null` only when the underlying event is directly observed but cannot be placed on the normalized zero point.
- Absence claims require an explicit provider/interval audit in `docs/GOLDEN-SM.md`.
- Do not fill a missing ACPI method from expected Windows behavior, ACPI source, Microsoft documentation, or Linux behavior.

## Final deliverable

After decode, create `docs/GOLDEN-SM.md` with:

- exact trace SHA-256;
- provider coverage / dropped-event status;
- T0–T6 marker times;
- Windows state-machine transitions;
- answers to Reset / Power / Post-RDESC / Finger-down;
- an explicit **PASS** or **REJECT**.

Only a PASS can authorize a later Linux reset/power/wire change. Every such change must cite one observed golden transition.
