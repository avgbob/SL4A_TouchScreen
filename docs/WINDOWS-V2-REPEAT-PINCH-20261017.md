# Repeated Windows V2 one-handed pinch: contact-loss observations

> **Next evidence step prepared:** [Windows correlated pinch capture protocol](WINDOWS-CORRELATED-PINCH-EXPERIMENT-20261017.md) with same-session V2 M markers and WPR SPI/TouchAndPen. Offline decoder insists on complete 0x0C CapImg frames; it will flag a trace with only provider metadata as insufficient. Windows CI passed, but the collector has not yet been run on this Surface.


Date: 2026-10-17. **Second guided V2 trial** (separate from first).
The user additionally confirmed that the **only erroneous M keypress in
the first V2 trial** was at **2026-10-17T19:48:15.5399695Z**, the
one reporting TWO contacts. Thus first trial has **12/12 intentional
M annotations reporting one contact**, not an uncertain 11–12.

## Inputs, privacy and exact hashes

All raw traces were analyzed privately and **not committed**.
These identifiers uniquely select the latest inputs:
- `events(1).csv`: 1,577,692 bytes,
  SHA-256 `c2e51798228605b822aee2a5c738c6aef25aef36b1671ec76392f494dd165c9c`
- `samples(1).csv`: 37,498 bytes,
  SHA-256 `d135e4394a395d99033d0f171f0f225f1b6ecc18c2b862c94f0af5d1735b4a5d`
- `SUMMARY(2).txt`: 3,036 bytes,
  SHA-256 `37f1122ecf774d70352bc97539e15c42b6fbac82dce764bc36f36079319e825e`

Session UTC **19:57:34.160 to 19:59:06.457** (~92.30s).
CSV: 11,660 actual WM_POINTER messages, plus 4 STAGE_START and
5 PHYSICAL_TWO_MARK records, **11 DOWN/11 UP**, zero
duplicate DOWN/orphan UP/capture losses/native pointer API errors.
Maximum two active OS pointer IDs and native-frame contacts, none active
on exit.

## Stage results

| Stage | ~10Hz samples two/one/none | Events in stage | Observation |
| --- | --- | --- | --- |
| 1: one finger | 0/66/26 | 1 DOWN / 1 UP | Single ID 1665 |
| 2: two apart | 119/0/22 | 2 DOWN / 0 UP | IDs 1666 and 1667; 968.5–1023.4 screen px when both present |
| **3: one-handed pinch** | **349/75/0** | **8 DOWN / 8 UP** | 42.4s, **5/5** deliberate M annotations had one OS pointer and one native-frame contact |
| 4: staggered release | 29/37/50 | 0 DOWN / 2 UP | Both remaining IDs eventually release |

The pinch stage was at one reported pointer for **75/424 samples
(17.7%)**. This is NOT a measured physical hardware failure rate: it
also includes some unspecified physical-touch transitions.
Longest *sampled* one-ID streak was ~1.9s; an exact event-level
one-ID interval runs ~2.1069s (UP 1670 to DOWN 1671).

**Persistent anchor:** ID `1666` was reported continuously for
**63.462 seconds**, spanning stages 2–4. Secondary IDs
`1667` through `1675` were repeatedly released/replaced.
All five new intentional M annotations recorded **only 1666** active.

### Five explicit physical-contact mismatches

Each M annotates the user confirming that TWO fingers were physically
touching, while Windows provided ONE pointer. Each falls between
a real secondary UP and later replacement DOWN.

| M time UTC | Seconds since secondary UP | Seconds until next DOWN | Active pointer |
| --- | ---: | ---: | --- |
| 19:58:17.5885995 | 1.015 | 1.019 | 1666 |
| 19:58:26.3585235 | 0.701 | 0.637 | 1666 |
| 19:58:36.0538033 | 0.796 | 1.311 | 1666 |
| 19:58:40.0979884 | 0.656 | 0.344 | 1666 |
| 19:58:49.8792491 | 0.407 | 0.528 | 1666 |

## Correlation with reported inter-finger proximity

For each pinch-stage secondary `UP`, the released contact's X/Y
was compared to the most recent reported X/Y of anchor `1666`
(the latter was only 0–13ms old). Distances in **OS screen pixels**
were approximately **82.8, 91.0, 35.6, 40.0, 83.0, 87.2,
73.2 and 81.3**. Thus **all 8/8** pinch-stage releases occurred
at or below **91 screen pixels**. The earlier guided V2 trial yielded
**15/19** secondary releases at or below 100 pixels, so **23/27
combined** are at or below 100.

**Do not turn this into a 100px classifier parameter:** OS pixel
distance is not CapImg cell separation; there is no matched sensor
heatmap, and a spatial correlation is not a causal demonstration.
Also, the user has not supplied synchronized physical video.

## Updated evidence status

- **First V2:** 13 raw M events; **one accidental at 19:48:15.5399695Z
  when 2 IDs were correctly present**; therefore **12/12 intentional
  M events showed only one ID**.
- **Second V2:** **5/5 intentional M events showed only one ID**.
- **Pooled:** **17 of 17 deliberate, user-confirmed physical
  two-finger observations** coincide with ONE Windows OS pointer,
  despite other correctly tracked two-pointer intervals.
  These 17 observations are clustered in two recording sessions,
  not 17 statistically independent randomized trials.
- Both `MessageActive` and latest native pointer-frame counts
  read 1 at these annotations; those are views from the same OS
  pointer stack, NOT independent hardware sensor measurements.
- Windows balance of DOWN/UP only shows clean end-of-contact signaling,
  **not** that the OS maintained each real finger's contact lifetime.
- The exact faulty processing stage is still **unidentified**. Possible
  sensor peak merger, threshold/classifier behavior, touch firmware
  logic, Windows software processor, HeatCore, or application capture
  semantics require additional data to distinguish.

### Next decisive work

On the same one-hand close pinch, record raw `0x0C` CapImg frames
and available Windows TouchAndPen/HeatCore ETW *simultaneously* with
the already-working OS pointer tester. Align UTC timestamps and
`M` markers to sensor frames. Determine whether two physical peaks
remain in raw data when Windows publishes only one contact. Compare
candidate classifier and hold/lift internals before any Linux Gate5
or PR #87 changes.

Raw screen coordinates and event timelines remain private; this is
a reproducible aggregate research note, not a firmware-level diagnosis.
