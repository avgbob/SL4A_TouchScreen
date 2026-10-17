# October 17, 2026 — first coordinated WPR + V2 capture: source verification

The operator completed a synchronized WPR/SPI/TouchAndPen + Windows
Win32 pointer V2 data-collection run. This report is metadata-only:
**we have not yet read the raw WPR CSV, original ETL, or the new
pointer events; none of those large/private data files were uploaded
with the initial seven-file capture-status bundle.**

## Confirmed by the user-uploaded original logs

- Local run name: `SL4A-Correlated-20261017-183111`
  (the machine uses OneDrive Desktop redirection).
- WPR profile accepted, WPR session ACTIVE by
  **2026-10-17T22:31:13.3628031Z**.
- Guided pointer V2 child completed exit code **0** by
  **22:33:11.0920083Z** (exact pointer start and individual touch
  timestamps require `pointer/events.csv`).
- WPR stopped successfully, original ETL retained by
  **22:33:23.6294706Z**.
- `tracerpt` CSV export ended successfully
  **22:34:09.2578920Z**.
- Original ETL: **221,773,824 bytes**,
  SHA-256 `23ee9ad0df5703458a15bd4741acdb910041f84edeef908cce73f0775c7acb30`.
- Tracerpt CSV: **656,619,526 bytes**,
  SHA-256 `56c9f4b3b9ee7fe526667de208dce59f8a150f7372448a218783e11075502131`.
- `pointer/events.csv`: 1,507,662 bytes, SHA-256
  `530c574a1aae4b07c8d611d32ea2ddf4962fc8da1c78997f0b6665c9a2c7a474`
  (**listed in manifest, not yet supplied**).
- `pointer/samples.csv`: 40,410 bytes; SHA-256
  `88d98e8dfd8a248724ebebdcf3ab4b4e59dceb663fd99135ca09503477421800`
  (**not yet supplied**).
- `pointer/SUMMARY.txt`: 2,853 bytes; SHA-256
  `0afb10594f7124dbb876ed3b49da0fc3e41237e6de83dea9be28d63ec3c844d3`
  (**not yet supplied**).
- Manifest, profile, timing markers, WPR stop, tracerpt, WPR profile,
  and pointer-process logs were uploaded; hashes of all locally
  available logs match the entries in `manifest.json`.

## Evidence gates (checked 2026-10-17)

| Gate | Status | Why |
| --- | --- | --- |
| WPR profile accepted | **PASS** | `wpr-profiles.log` |
| WPR active alongside pointer recorder | **PASS (time overlap)** | UTC coordinator events + pointer exit 0 |
| ETL saved | **PASS (metadata and logs)** | `wpr-stop.log` and original ETL hash manifest |
| CSV export completed | **PASS (logs)** | `tracerpt.log` |
| Pointer UP/DOWN and operator M markers | **NOT YET EVALUATED** | `pointer/events.csv` absent from uploaded seven files |
| Raw `0x0C` CapImg bodies actually decoded | **NOT YET EVALUATED** | `pinch-runtime.csv` not uploaded; provider enablement insufficient |
| Same-clock mapping and matched M/CapImg frames | **OPEN** | WPR Clock-Time may not equal pointer UTC |
| Diagnosis of hardware vs Windows classifier | **OPEN** | No synchronized raw/processed comparison completed |

## Next step: local extraction avoids uploading hundreds of megabytes

On the Windows Surface, run
[`build_pinch_evidence_bundle.py`](../tools/windows_capture/build_pinch_evidence_bundle.py)
with the supporting
[`analyze_correlated_pinch.py`](../tools/windows_capture/analyze_correlated_pinch.py)
and [`decode_v0_capimg.py`](../tools/decode_v0_capimg.py).
It streams the ~657 MB original tracerpt CSV **locally**, verifies
source hashes and the V0 `0x0C` sensor payload format, writes a
coverage report, and ZIP-compresses the pointer logs plus valid
recovered heatmaps. It **does not include the original ETL or 657 MB CSV**
in the upload ZIP, and **does not contact any external service**.
Full, user-facing PowerShell command is in
[tools/windows_capture/README.md](../tools/windows_capture/README.md).

Only after the raw coverage and time-alignment gates pass can the
physical two-finger M annotations be correlated with sensor peak
separation and `TouchPenProcessor0C19` classifier output.
No Gate5, PR #87 or kernel changes were made.
