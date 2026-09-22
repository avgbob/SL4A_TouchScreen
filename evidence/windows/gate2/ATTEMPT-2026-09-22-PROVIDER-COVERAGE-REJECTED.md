# Gate 2 boot-autologger attempt 2026-09-22 — REJECTED (provider coverage)

This is an evidence-profile rejection. It is **not** evidence that Windows omitted reset, ACPI power methods, feature traffic, or HID/CapImg input.

## Trace identity

- ETL SHA-256: `5071fe9db0f865bab2103cfdac8ac9518c54c7581584e8a87dc1915358c10048`
- ETL bytes: `14,680,064`
- tracerpt elapsed time: `826 sec`
- tracerpt buffers: `14`
- tracerpt events: `107`
- tracerpt events lost: `0`

The local phase log covers T0 through T6, including disable/enable, one-finger, two-finger, Modern Standby, post-resume finger, and final stop.

## What the ETL actually contains

Decoded events are dominated by:

- Microsoft-Surface-SurfaceService `{1e8d5623-6573-47f2-b69e-eea8923ce036}`
- Microsoft-Surface-SurfaceOemPanel `{3d53356d-424b-496a-a094-2154d8d2b304}`
- WPR/ETW internal providers and PerfInfo marks

The following Gate 2 target provider GUIDs are absent from the ETL itself (raw GUID-byte scan and tracerpt XML/summary):

- ACPI Driver Trace Provider `{dab01d4d-2d48-477d-b1c3-daad0ce6f06b}`
- Microsoft-Windows-Kernel-Acpi `{c514638f-7723-485b-bcfc-96565d735d4a}`
- Microsoft-Windows-Kernel-PnP `{9c205a39-1250-487d-abd7-e831c6290539}`
- Microsoft-Windows-Kernel-Power `{331c3b3a-2005-44c2-ac5e-77220c37d6b4}`
- Microsoft-Windows-SPB-ClassExtension `{72cd9ff7-4af8-4b89-aede-5f26fda13567}`
- Microsoft-Windows-GPIO-ClassExtension `{55ab77f6-fa04-43ef-af45-688fbf500482}`
- Microsoft-Windows-Input-HIDCLASS `{6465da78-e7a0-4f39-b084-8f53c7c30dc6}`
- Microsoft-Windows-Kernel-Process `{22fb2cd6-0e7b-422b-a0c7-2fad1fd0e716}`
- Microsoft-Surface-SurfaceHidMiniDriver `{2fea7205-b0b1-41ca-8609-5a1d16f3132f}`
- Microsoft-Surface-TouchAndPen-Prod `{3fa102e9-1a62-5490-7af8-6088c2f9e6be}`

This is not a tracerpt naming/manifest issue: the target GUID byte sequences do not occur in `gate2.etl`.

## Why this invalidates the Gate 2 contract

The trace cannot prove or disprove:

1. cold / disable-enable `_RST`;
2. `_INI/_PS0/_PS3` or D-state sequencing;
3. post-RDESC ID5 / ID6 / 0x56 traffic;
4. 0x0C Col02 vs 0x40 touch input and reader/process.

All four remain OPEN.

## Registration vs logging

The boot autologger registry did contain all 20 configured provider subkeys, including the missing target GUIDs, and the TouchInitCollector ETW session was Running. Therefore the failure is provider runtime logging configuration, not omission from the WPRP registration.

The original WPRP left `NonPagedMemory` at its default false for kernel/driver event providers. Microsoft WPR guidance requires kernel-mode TraceLogging providers to use nonpaged memory. The corrected profile separates kernel/driver providers into a bounded nonpaged collector and user/user-hosted providers into a paged collector.

A runtime provider smoke test must pass before another cold-boot Gate 2 run is allowed.
