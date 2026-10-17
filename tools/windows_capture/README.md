# Windows capture kit — historical research reference

## After the successful October 17 correlated capture — extract a small evidence ZIP

The original coordinated recording **succeeded** and preserved
`pinch-runtime.etl` (~222 MB) and `pinch-runtime.csv` (~657 MB).
The first upload contained only manifest/coordinator logs;
**the actual V2 pointer events and WPR CSV were not yet submitted**.
Do not re-record the same gesture. See
[confirmed capture metadata and remaining gates](../../docs/WINDOWS-CORRELATED-CAPTURE-STATUS-20261017.md).

To extract validated raw sensor frames from the large CSV *locally*,
open an ordinary Windows PowerShell window and paste:

```powershell
$desktop = [Environment]::GetFolderPath('Desktop')
$run = Join-Path $desktop 'SL4A-Correlated-20261017-183111'
$kit = Join-Path $desktop 'SL4A-Correlated-Kit'
New-Item -ItemType Directory -Force -Path $kit | Out-Null

$base = 'https://raw.githubusercontent.com/avgbob/SL4A_TouchScreen/main/tools/'
foreach ($name in @('analyze_correlated_pinch.py',
                    'build_pinch_evidence_bundle.py')) {
    Invoke-WebRequest ($base + 'windows_capture/' + $name) -OutFile (Join-Path $kit $name)
}
Invoke-WebRequest ($base + 'decode_v0_capimg.py') -OutFile (Join-Path $kit 'decode_v0_capimg.py')

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 (Join-Path $kit 'build_pinch_evidence_bundle.py') --run-dir $run
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python (Join-Path $kit 'build_pinch_evidence_bundle.py') --run-dir $run
} else {
    throw 'Python 3 is required for offline extraction; no need to recapture the touchscreen.'
}
```

The script checks manifest hashes, reconstructs `0x0C` SPI
sensor frames by activity and direction, strictly decodes 72x48
CapImg sections, and retains a coverage report even when
no raw frames can be recovered. **It does not upload anything.**
It packages (if present) `pointer/events.csv`, `samples.csv`,
`SUMMARY.txt`, coordinator logs, provider counts, raw frame hashes,
and compressed decoded frames into:

`SL4A-Correlated-20261017-183111\offline-analysis\SL4A-correlated-evidence.zip`

**Upload that ZIP here**, not the 657 MB WPR CSV or original ETL.
Keep the originals on the Surface. The ZIP can itself contain
touch positions and heatmaps; share it privately rather than
committing it to public GitHub.

The script requires Python 3.10+; the original recording does
not need Python. The parser, missing-sensor-report handling,
hash rejection, and ZIP contents have automated tests on
[Windows correlated collector Actions](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/windows-pinch-correlated.yml).

---

## New priority: paired WPR + guided V2 close-pinch capture (2026-10-17)

Two separate user-confirmed V2 trials provide **17/17 intentional M
annotations** with two physical fingers but **one OS pointer**. The next
decisive experiment is to capture the raw sensor bus and Windows
pointer output **in the same trial**, not to gather another OS-only
CSV. See [full capture protocol and validation gates](../../docs/WINDOWS-CORRELATED-PINCH-EXPERIMENT-20261017.md).

### One coordinated run (on the Surface in Windows)

**Open Windows PowerShell as Administrator**. Make sure no other
Windows Performance Recorder session is running. Copy/paste
this full block:

```powershell
$kit = Join-Path $env:USERPROFILE 'Desktop\SL4A-Correlated-Kit'
New-Item -ItemType Directory -Force -Path $kit | Out-Null

$base = 'https://raw.githubusercontent.com/avgbob/SL4A_TouchScreen/main/tools/windows_capture/'
foreach ($name in @('capture_pinch_correlated.ps1',
                    'capture_os_pointer_contacts_v2.ps1',
                    'touch_boot.wprp')) {
    Invoke-WebRequest ($base + $name) -OutFile (Join-Path $kit $name)
}

powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File (Join-Path $kit 'capture_pinch_correlated.ps1') -Mode Capture
```

It checks the WPR profile, starts the ETW trace, opens the V2
full-screen test, stops the trace when the test closes, and **retains
the original ETL even if tracerpt cannot export CSV**. It does not
call `wpr -cancel` and will not reset or modify the device.

**Perform one consistent physical sequence:**

1. Press **SPACE**; drag one finger and lift it.
2. Press **SPACE**; put two fingers far apart and hold for five
   seconds. **Keep them down** when you press SPACE to advance.
3. Move the **same two fingers** slowly together then apart,
   repeating three times; hold them close briefly without lifting.
   **If both physically touch but active IDs show 1, press M**
   with your other hand while the missing-contact condition persists.
   Do not press M when the screen correctly shows 2.
4. Press **SPACE**; lift only one finger, hold the remaining finger
   for three seconds, then lift it. Press **SPACE** to finish (ESC
   also saves a partial attempt).

Outputs go to the timestamped Desktop
`SL4A-Correlated-YYYYMMDD-HHMMSS` folder. Upload
`pointer/SUMMARY.txt`, `pointer/events.csv`,
`pointer/samples.csv`, `manifest.json`, and
`coordinator-markers.tsv` first; also upload
`pinch-runtime.csv` when feasible. **Preserve
`pinch-runtime.etl` locally** as the original source for further
UTC/QPC and TraceLogging reconstruction.

The CSV/ETL may contain device-wide event metadata and touch
positions; do not publish them on GitHub. The
[offline coverage verifier](analyze_correlated_pinch.py) will
confirm whether **complete V0 0x0C sensor frames** are actually
present. A WPR trace with only provider names is not sufficient
for a sensor/software root-cause diagnosis. This collector has
passed CI parsing and synthetic regression gates, but **live
WPR+Surface hardware execution is not yet validated**.

---


## Recommended test: guided one-hand pinch diagnostic V2 (2026-10-17)

**Use [`capture_os_pointer_contacts_v2.ps1`](capture_os_pointer_contacts_v2.ps1), not the old V1 script** when checking the operator's report that the on-screen active ID count sometimes fell to **one while two fingers were physically pinching**. The previous 8,947-event CSV proved that *some* two-ID intervals existed; it **did not** prove the device tracked both fingers through **every** pinch. The operator's firsthand observation must be tested and recorded as such.

### Launch on the Surface in Windows

Run in **Windows PowerShell** (ordinary user is sufficient; no driver installs):

```powershell
$script = "$env:USERPROFILE\Desktop\capture_os_pointer_contacts_v2.ps1"
Invoke-WebRequest "https://raw.githubusercontent.com/avgbob/SL4A_TouchScreen/main/tools/windows_capture/capture_os_pointer_contacts_v2.ps1" -OutFile $script
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $script
```

A dark full-screen screen opens. **Large number on the left = number of
currently tracked Windows pointer IDs**, drawn circles = positions of each
tracked ID, and **"Frame contact count" = count of in-contact pointers in
the most recently available native Win32 pointer frame**. The latter is an
additional view of the same Windows pointer pipeline, **not an independent
sensor measurement**. `NA` means frame data is unavailable/stale, **not
zero fingers**.

You control the four stages with your keyboard **SPACE**. Always keep your
finger(s) inside this test screen; avoid clicking taskbar/browser windows.

1. **SPACE** starts STEP 1 — one finger only. Move it and lift it.
2. **SPACE** starts STEP 2 — two fingers placed far apart, hold both for
   at least **five seconds**. You should see two labeled circles and
   **Active IDs: 2**.
3. **SPACE** starts STEP 3 — with both fingers physically touching the
   glass, slowly bring them toward one another and back apart **three
   times without lifting**. Watch whether the big number drops to 1
   during the actual pinch.
4. **SPACE** starts STEP 4 — place two fingers, lift just one, keep
   the other held for **three seconds**, then lift it.
5. **SPACE** again to finish (or **ESC** at any point to save and exit).

**The most important key is M:** Press **M immediately while TWO fingers
are genuinely still touching the glass** if the screen displays only one
active finger (or the count is otherwise suspicious). Press again if it
happens a second time. This logs the exact stage, UTC time, tracked IDs
and recent native frame count together with your **physical two-finger
observation**, eliminating the ambiguity of the original CSV.

The script creates a timestamped Desktop folder:

* `SUMMARY.txt` — concise stage-by-stage 2/1/0 counts, native-frame
  totals, ID changes, duplicate/orphan releases and every M marker.
* `samples.csv` — screen/window counts, frame counts and IDs sampled
  ten times per second for each stage.
* `events.csv` — detailed per-event timestamps, pointer flags,
  contact IDs, coordinates, raw coordinates, contact rectangles,
  pressure/orientation when available, and operator markers.

**Upload all three**, especially `SUMMARY.txt`. We will not declare
all pinches correct merely because one interval had two active IDs.
Do not post raw coordinate CSVs publicly without considering privacy.

### Validation

[GitHub Windows PowerShell 5.1 regression](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/windows-pointer-v2-check.yml)
parses the entire script, compiles its embedded Win32 interop C# and
checks a synthetic two-finger staggered release. It **cannot test actual
hardware messages**, so the Windows machine trial is still necessary.
The V1 original remains archived solely for comparisons.

## Purpose

The Surface multitouch pipeline now implements native Linux tracking
(see `docs/PIPELINE.md`). This kit is a historical research reference
for comparing Windows ACPI, power, PnP, and Surface/SAM activity against
the Linux driver. It does not establish that an external Windows component
is required for standard HID initialization. The existing SPI traces cover
SPB, GPIO-interrupt, and HIDCLASS, but not ACPI/SAM/power activity.

## What this kit captures (that the old traces did NOT)
- **ACPI** (power methods, _PS0/_INI/_RST, the 2 `AcpiEventMethod`s seen before touch init)
- **Kernel-Power** (the device's Dx transitions: who brings the touch to D0, and when)
- **Kernel-PnP** (device start order: what starts before the touch)
- **Kernel-Process** (maps an SPB request's submitter PID/TID to its image)
- **Surface/SAM** (Surface Aggregator requests: whether Windows sends a SAM command for the
  touch)

The touch initializes at COLD BOOT (a disable/enable in Device Manager isn't enough — that
only triggers a D2→D0 resume). So a **boot trace** is used.

## Windows OS-visible pointer ID/lift reference (new 2026-10-17 research probe)

The existing TraceLogging `touch_boot.wprp` and `capture_runtime.cmd`
capture sensor/processor metadata. **Those events do not themselves establish
what pointer contact Windows delivers to applications.**

A separate **read-only Windows Forms pointer message observer** is provided:
[`capture_os_pointer_contacts.ps1`](capture_os_pointer_contacts.ps1).
It logs `WM_POINTERDOWN`, `WM_POINTERUPDATE`, `WM_POINTERUP`,
`WM_POINTERENTER/LEAVE`, and `WM_POINTERCAPTURECHANGED` in a full-screen
touch target. CSV columns include UTC timestamp, Stopwatch ticks, OS pointer
ID, type, Windows-screen coordinates, and the untouched raw `WPARAM`.
It does not install anything, modify a touch driver, or issue HID commands.

**Not yet tested on the user's Windows installation; validate that DOWN and UP
rows actually appear before promoting this as a ground-truth collection.**
`WM_POINTER` IDs are **Windows application-facing pointer IDs**, not
proven to match USB/HID internal Contact ID values or HeatCore tracker IDs.
It provides a measurement of Windows-visible active contact and lift rather
than internal classification.

To use with sensor correlation, on Windows PowerShell in the downloaded repo's
`tools/windows_capture` folder, with `touch_boot.wprp` copied into
`%USERPROFILE%\Desktop\SL4A_capture`:

1. Start `capture_runtime.cmd` as Administrator in one console, following
   its existing steps. **Start the WPR trace first**.
2. In a **second** Windows PowerShell 5.1 console (STA), run:
   `powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File .\capture_os_pointer_contacts.ps1`.
3. In the full-screen target, do one-finger drag/lift, far-separated two-finger
   pinch/expand/lift, then close the logger using **ESC**.
4. Stop WPR in the original console, preserve both the
   `touch_runtime.etl` and `sl4a-os-pointer-*.csv`, and record their
   exact source hashes. Both sessions record wall-clock UTC for approximate
   alignment. **Frame-accurate sensor/contact synchronization still needs
   measured correlation**, not an assumed millisecond offset.
5. Validate one DOWN/UP pair per observed OS pointer before treating the CSV
   as an oracle. Beware that the observer receives events only when the finger
   targets its window; it is not a system-wide input logger.

The touched OS-pointer CSV may contain screen coordinates, so treat the original
recording as potentially sensitive; do not automatically upload or publish it.

## Steps (run on Windows, in an Administrator prompt)

### Runtime centroid capture for multi-touch mapping

The shared `touch_boot.wprp` profile also enables `Microsoft.Surface.TouchAndPen.Prod`
(`{3FA102E9-1A62-5490-7AF8-6088C2F9E6BE}`), the TraceLogging provider in
`TouchPenProcessor0C19.dll`. Its event schema contains the Windows-computed
`TouchBlobCoMX` and `TouchBlobCoMY` fields for each tracked finger.

For coordinate calibration, copy `touch_boot.wprp` and `capture_runtime.cmd` to the
Windows capture directory, run the latter as Administrator, and hold one finger at each
point of the indicated 3x3 screen grid. Repeat with two separated fingers. Stop the trace
and run `export_runtime.cmd`. Preserve the resulting ETL; it retains TraceLogging metadata and
is preferable to CSV. Use `tracerpt` or WPA on Windows to export the decoded fields, then copy
both the export and ETL back for correlation with physical grid coordinates. This is read-only and does not send
experimental HID commands to the controller.

### Capture the callback host

After using the touchscreen in Windows, run `collect_touch_host.cmd` as Administrator from
the same directory. It writes `touch_host/touch_host_modules.txt` with the process command
line and loaded modules for the process that contains `TouchPenProcessor0C19.dll`, and copies
its executable when Windows permits it. Copy the entire `touch_host/` directory back with the
ETL. This identifies the binary owning the indirect callback that supplies raw heatmap frames
to the processor DLL.

### 1. Find this machine's exact Surface/SAM providers
```
00_enumerate.cmd > providers.txt
```
Send me `providers.txt`. I'll look for the Surface/Aggregator/ACPI GUIDs and add them to the
profile if they're missing. (The profile already includes ACPI/Power/PnP by name.)

### 2. Start the boot trace, reboot, stop
```
wpr -boottrace -addboot touch_boot.wprp
shutdown /r /t 0
```
After rebooting and logging in, wait ~30 seconds (so the touch has finished initializing),
then:
```
wpr -boottrace -stopboot %SystemDrive%\touch_boot.etl
```

### 3. Export to text and send me the result
```
02_export.cmd
```
Produces `touch_boot.csv` (+ possibly `touch_boot.txt`). Send me that.

### Submitter attribution

The profile records process start/stop events in addition to the SPB request
events. Preserve the ETL and CSV from the same boot. The offline analyzer will
map the submitter of every observed SET_FEATURE to its PID, TID, and process
image. Do not send manual Feature reports during this capture: normal boot is
the target behavior.

## What I'll look for in the log
- A SAM/Surface Serial Hub event around the touch's power-up (a specific TC/command).
- Which ACPI method the 2 `AcpiEventMethod`s are, and whether a _PS0/M009/M010 precedes the
  first RESET_RSP.
- PnP ordering: whether a companion/SAM device starts and enables something before the touch.
- D0/Dx transitions of the touch and any related devices.
- The process that submits ID5 and ID56, if the normal boot emits them.

## In parallel (optional, Linux side)
If your kernel has the `ssam_*` ftrace events, we can log what SAM does on Linux and compare.
They weren't compiled in on this boot; happy to check if you're interested.

---

## UPDATE after providers.txt (07/2026)

`providers.txt` revealed the Windows touch stack. The `touch_boot.wprp` profile
now uses this machine's real GUIDs. The extension-package hypothesis below was
later falsified: it is a registry-only overlay, not a separate initializer.
What to look for in the log:

- **`ACPI\MSHW0231\A` = "Surface Digitizer HidSpi Extn Package"** — a
  registry-only cosmetic/power-management overlay, not a separate binary or
  proven initializer (see `docs/GROUND_TRUTH.md` section 15.13/15.14).
- The touch is a multi-collection HID device: **COL01 "Touch Communications"** (a CONTROL
  channel, distinct from touch data), COL06 "Touch Screen Device", + pen/digitizer/VHF enum.
- **Surface Serial Hub (MSHW0084)** + **SMF Core/Client** + **SMF Display Client**: the SAM
  stack that might power/enable the panel before the touch.
- **"ACPI Driver Trace Provider"** (GUID DAB01D4D...) traces ACPI method execution — i.e. it
  should finally tell us WHAT the 2 `AcpiEventMethod`s seen before touch init actually are.

The profile captures all of this plus SPB/GPIO/HIDCLASS on the same timeline, so I can
correlate "SAM request / ACPI method → the touch's first RESET_RSP".
