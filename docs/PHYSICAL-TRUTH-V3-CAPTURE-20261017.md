# Surface Laptop 4 AMD: controlled finger-presence/lift capture (V3)

**Status:** Implemented as an **opt-in** operator-annotated mode of
[`capture_os_pointer_contacts_v2.ps1`](../tools/windows_capture/capture_os_pointer_contacts_v2.ps1)
and its
[paired WPR/SPB coordinator](../tools/windows_capture/capture_pinch_correlated.ps1).
Windows PowerShell 5.1 compatibility and synthetic reports are tested in
[Windows correlated collector CI](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/windows-pinch-correlated.yml).
**Actual V3 human-lift session has NOT yet been recorded.**
The previous V2 recordings and existing WPR capture remain intact.

## Objective

Separate these two physically different situations that may look
identical to a capacitive tracker:

1. **True occlusion:** TWO fingers physically remain on the glass
   while the app or sensor produces one contact/region.
2. **True release:** the experimenter deliberately LIFTS the second
   finger while maintaining the first finger.

Include a return of the second finger **at the same nearby position**,
which is intentionally adversarial to trackers that reuse an old
finger ID too readily.

The operator declares physical states explicitly with a spare hand.
These are **human annotations**, not independent video/hardware
measurements. Their reaction time is not known. The offline
analyzer excludes the first 350ms after and final 150ms before each
state-change marker, and retains the raw logs for later review.
This addresses sustained physical states; it **does not certify exact
finger-lift microsecond timing** or Windows HeatCore algorithms.

## Start on the actual Surface running Windows

Run **Windows PowerShell as Administrator**.
Do not use this while another WPR recording is active.
Ensure several gigabytes of free disk (earlier same-session WPR
captured 222MB ETL and exported a 657MB CSV).

```powershell
$desktop = [Environment]::GetFolderPath('Desktop')
$kit = Join-Path $desktop 'SL4A-PhysicalTruth-Kit'
New-Item -ItemType Directory -Force -Path $kit | Out-Null

$base = 'https://raw.githubusercontent.com/avgbob/SL4A_TouchScreen/main/tools/windows_capture/'
foreach ($name in @('capture_pinch_correlated.ps1',
                    'capture_os_pointer_contacts_v2.ps1',
                    'touch_boot.wprp')) {
    Invoke-WebRequest ($base + $name) -OutFile (Join-Path $kit $name)
}

$script = Join-Path $kit 'capture_pinch_correlated.ps1'
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $script -Mode SelfTest -PhysicalTruthMode
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File $script -Mode Capture -PhysicalTruthMode
```

The coordinator saves a unique timestamped
`Desktop\SL4A-PhysicalTruth-YYYYMMDD-HHMMSS` folder.
It starts WPR and OS pointer tracing in the same run, stops WPR
and preserves original ETL, then attempts `tracerpt` CSV export.
No driver, kernel or device configuration is modified.
There is **no** `wpr -cancel` command.

## Keys and eight test stages

**SPACE** advances only the stage and does NOT claim how many
fingers physically touch. With the spare hand use these marker keys:

| Key | Meaning (press *after* confirming the physical state) |
| --- | --- |
| **B** | Two fingers **B**oth physically DOWN |
| **T** | Both **T**wo STILL down, even if Windows reports one |
| **L** | Second finger **L**ifted deliberately; first remains down |
| **R** | Second finger **R**eturned physically down |
| **N** | **N**o fingers on glass |
| **X** | Previous annotation/interval invalid; physical state now UNKNOWN |
| **SPACE** | Next stage, without inferring a physical state |
| **ESC** | Save partial session and stop |

1. **Baseline/no touch:** SPACE begins. With no fingers on glass,
   press **N** and hold this zero state about 2 seconds.
2. **Two far apart:** SPACE advances. Place two fingers far apart
   and press **B** *after both are physically touching*.
   Hold 3 seconds with both on glass.
3. **Continuous pinch:** SPACE advances **without lifting either finger**.
   Bring them together slowly, separate, repeat. Press **T**
   at close separation and again if the OS pointer count drops
   to one. This is a physical-contact confirmation independent
   of whether Windows currently reports 1 or 2. Hold the
   close physical state about 3 seconds.
4. **Close two-finger hold:** SPACE advances, keep the same two
   fingertips near one another without lifting. Press **T**,
   hold another 3 seconds.
5. **Intentional close-finger lift:** SPACE advances; deliberately
   lift just the second fingertip, leaving the first finger down.
   Immediately after physically lifting, press **L** with the
   spare hand. Hold 3 seconds.
6. **One-finger control:** SPACE advances, keep only the original
   first finger down for 3 seconds. Do **not** press T here.
7. **Close re-touch:** SPACE advances; touch the second finger
   again near its old position. Press **R** only once it is
   physically on the glass. Hold 3 seconds.
8. **Complete release:** SPACE advances; lift BOTH fingers,
   press **N** after they're both off, hold 3 seconds, then
   press SPACE to finish.

Avoid accidentally changing physical contact while pressing the
keys. If you do, press **X** immediately and repeat the state
marker (B/L/R/N) only when you are certain. Corrections are
**appended, never silently deleted**, for evidence integrity.

Run the sequence once first. Further trials should cover
**different actual fingertip distances** and lift orders, but
a successful full sensor+pointer V3 trace is more useful than
uncontrolled repeated V2 sessions.

## Offline analysis / compact sharing

On the Surface, after completing V3, open regular PowerShell.
Update four **Python standard-library only** tools in the kit:

```powershell
$desktop = [Environment]::GetFolderPath('Desktop')
$kit = Join-Path $desktop 'SL4A-PhysicalTruth-Kit'
$base = 'https://raw.githubusercontent.com/avgbob/SL4A_TouchScreen/main/tools/'
foreach ($name in @('analyze_correlated_pinch.py',
                    'analyze_physical_truth.py',
                    'build_pinch_evidence_bundle.py')) {
    Invoke-WebRequest ($base + 'windows_capture/' + $name) -OutFile (Join-Path $kit $name)
}
Invoke-WebRequest ($base + 'decode_v0_capimg.py') -OutFile (Join-Path $kit 'decode_v0_capimg.py')

$run = Get-ChildItem -Path $desktop -Directory -Filter 'SL4A-PhysicalTruth-*' |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $run) { throw 'No V3 capture folder found' }

$python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
& $python (Join-Path $kit 'build_pinch_evidence_bundle.py') --run-dir $run.FullName
```

This produces `offline-analysis\SL4A-correlated-evidence.zip`.
**Upload the ZIP privately here, not the original 657MB CSV or ETL.**
For V3, the ZIP includes
`offline-analysis/physical-truth-report.json`, with counts for:
- **2 physically down / Windows 1**: candidate missing-contact intervals.
- **1 physically down / Windows 2**: candidate ghost-after-second-lift.
- **0 physically down / Windows nonzero**: candidate ghost-after-all-lift.
- 1 physically down / Windows zero: candidate false negative.
- Corrections/excluded intervals, sample coverage and run durations.

Metrics apply conservative post-annotation windows; brief transitions
close to a marker are not assumed correct or incorrect.
Frame-by-frame comparison of heatmap/Windows pointers must **still
validate a shared clock mapping** before claiming physical release
timing or Windows-equivalent track identities.

## Qualification gates

- New markers: explicit physical states, including at least one
  deliberate **L** and subsequent **R**; manual correction possible.
- Balanced Windows pointer lifetimes and no API/capture losses.
- Complete raw CapImg `0x0C` sensor frames actually decoded and
  sensor timestamps conserved (not just provider names).
- Confirm two-close and independent-lift windows remain distinguishable
  after excluding uncertain human transition boundaries.
- Separate **identity continuity** from **contact count**:
  even a correct count does not prove the old finger physically
  persisted through disappearance.
- Keep PR #12 shadow identity reuse disabled, and do not alter
  production Gate5 or Syax upstream #87 until these evidence gates
  are met.
