# Windows OS pointer observation: 2026-10-17

**Scope:** first successful operator-run, **application-visible** WM_POINTER
observation using [`tools/windows_capture/capture_os_pointer_contacts.ps1`](../tools/windows_capture/capture_os_pointer_contacts.ps1).
This is **not** a raw HID dump, internal HeatCore track dump, or a
frame-synchronized CapImg/HeatCore oracle.

## Source and provenance

* Original user-uploaded CSV: `sl4a-os-pointer-20261017-152502.csv`
  (local analysis copy; **not added to public Git**).
* SHA-256: `2dc25d05653c82400afe935a3e92753c68566eecd6b55347395a4876c7702878`.
* 6,230 parsed events, **no missing values**.
* Capture: **2026-10-17 19:25:38.425362 UTC** to
  **19:26:47.097432 UTC**, duration **68.672 seconds**.
* Event type: 6,210 `UPDATE`, five each of `ENTER`, `DOWN`,
  `UP`, and `LEAVE`; zero `CAPTURE_CHANGED`.
* All 6,230 events have `PointerType=2` (Windows PT_TOUCH).
* Exactly five unique application pointer IDs (1388–1392).
  **All five had exactly one DOWN and exactly one UP**;
  chronological active-set sweep peaked at two simultaneous IDs
  and ended with **zero active contacts**.
* The Windows-only compatibility workflow
  [run 39061999726](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39061999726)
  passed parser and C# compile tests, but the direct Windows-user run
  and uploaded CSV establish the first actual event-collection success.

## Contact lifetimes measured from DOWN to UP

| Windows pointer ID | Duration | Movement update events |
| --- | ---: | ---: |
| 1388 | 11.559 s | 1,155 |
| 1389 | 7.226 s | 723 |
| 1390 | 7.211 s | 719 |
| 1391 | 16.758 s | 1,677 |
| 1392 | 19.347 s | 1,936 |

### Two separately resolved two-finger gestures

* Pair **1389, 1390**: both active together **7.194 seconds**;
  `UP` events **17.661 ms apart**.
* Pair **1391, 1392**: both active together **16.433 seconds**.
  Pointer **1391** lifted first; pointer **1392** continued for
  **2.914 seconds**, with **291 further UPDATE events** following
  the 1391 lift, then emitted its own `UP` and `LEAVE`.
* No duplicate DOWN, orphan UP, ID swap evident at this
  *application-event* level; no missing UP in these sessions.

These are positive *Windows app-level* observations of independent
two-contact lifetimes and balanced release. The final staggered release is
particularly relevant to the Linux first-finger persistence bug. It does
**not** prove which internal HeatCore `0x34` record, `0x3a`
report flags, or `0x21` HID output field generated a given OS pointer
ID. The Windows `WM_POINTER` ID is not assumed to equal the
private TouchPenProcessor track number or HID Contact ID.

## Evidence boundaries and next use

1. **The OS-facing capture WORKED.** Do not ask for this same trial
   again just to establish that Windows emits DOWN/UPDATE/UP.
2. **No time-matched raw CapImg session was supplied with this CSV**.
   The existing 1,422 Windows sensor frames represent other recording
   windows; do not compare individual fingers frame-to-frame as if
   synchronized.
3. **Gesture proximity/peak merge and classifier parity remain unmeasured.**
   The trace proves two independent OS pointers in each two-finger
   interval, not that they remained separable at arbitrarily close
   distances.
4. **The input listener owns a foreground Windows Forms window**.
   This is not a global HID sniffer; lifting/transfer outside the
   window could affect event delivery.
5. Useful next capture only if testing full parity: simultaneously
   run Windows raw/provider WPR and this already-validated pointer logger,
   record the timing of prescribed multi-finger gestures, preserve
   original ETL plus private CSV, and explicitly align timing sources
   before interpreting frame-by-frame identity changes.
6. **No raw screen coordinates are published in this document.**
   Store original CSV privately with its SHA-256 and avoid
   automatically committing Windows input traces to GitHub.

See [HEATCORE-26100.9278-STATIC-AUDIT.md](HEATCORE-26100.9278-STATIC-AUDIT.md)
for structural contact flag/ID movement in the exact uploaded Windows DLL,
and [WINDOWS-STACK-COMPLETENESS-20261017.md](WINDOWS-STACK-COMPLETENESS-20261017.md)
for outstanding HeatCore configuration/semantic questions.
