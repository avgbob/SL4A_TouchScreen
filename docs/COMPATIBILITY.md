# Compatibility Matrix

This file distinguishes **broad/E1 compatibility rows** from narrower
single-unit field qualifications. Gate5 and the Secure Boot reuse lifecycle are
qualified on one physical MSHW0231 unit, but they do not constitute a broad
hardware/firmware/kernel compatibility claim.

## E1 / Broad Compatibility Rows

| Date | Device | BIOS/firmware | Kernel | Distribution | Profile | Secure Boot | Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| No E1-qualified compatibility row recorded | - | - | - | - | - | - | - | - |

## Qualified Single-Unit Results (not E1 compatibility rows)

| Date | Device | Kernel | Profile / lifecycle | Secure Boot | Result | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-09-26 | Surface Laptop 4 AMD, MSHW0231 + AMDI0060 | `7.0.0-31-generic` | Gate5: write-only GET6 -> 4.5-5.5 ms -> SET5; cold boot + touch, 3/3 warm reload + touch, 2/2 s2idle resume + touch | Not the scope of this transport checkpoint | PASS on one unit; zero observed frame drops and no unexpected post-DONE reset | `docs/GATE5-QUALIFICATION.md`, checkpoint `58f0231` |
| 2026-09-26 | Same tested MSHW0231 unit | `7.0.0-31-generic` | DKMS install -> signer verification -> reboot -> automatic Gate5 activation | Enabled; existing enrolled Ubuntu DKMS MOK reused | PASS on one unit | `docs/GATE5-QUALIFICATION.md`, lifecycle checkpoint `e2be025` |

## Required Fields

Each new row must include:

- Surface model and ACPI identifiers found at runtime.
- BIOS/UEFI and touchscreen firmware versions when available.
- Exact kernel release and distribution version.
- Standard or raw profile, including non-default module parameters.
- Secure Boot state and module-signing result.
- Test procedure from `TESTING.md`, date, outcome, and capture/log location.

## Non-Qualified Observations

These observations are not release-qualified. They record single-session standard
HID results with temporary local artifacts; permanent E1 qualification requires
archived evidence with verified checksums and a completed matrix.

| Date | Session | Cases | Artifact | Outcome |
| --- | --- | --- | --- | --- |
| 2026-07-23 | Cold boot | No auto-binding; post-login activation ok; descriptor 936 B; ready; 0 drops | evidence/cold-boot-state | pass |
| 2026-07-23 | Post-activation | Controller+transport bound; ready; data=267; 0 drops | evidence/post-activation-state | pass |
| 2026-07-23 | Suspend/resume | Touch returned ready; descriptor re-read (reset 2→4, re-read desc); 0 drops. Platform warnings from surface_aggregator/charger, not SL4A stack | evidence/pre-suspend, evidence/post-resume | functional, platform deviation |
| 2026-07-23 | Stylus | HID 045E:0C19 Stylus discovered (pen, pressure, tilt); no pen hardware available for input test | device discovery only | not applicable |
| 2026-09-09 | Community report, SL4 AMD (upstream issue #4), standard HID on v1.5.0 | Cold boot reaches probe, RESET_RSP, descriptor (936 B) and HID creation, then no input frames at all; the same instance streams immediately after a suspend/resume (idle IRQ ~150, 755 while touching). Reported by the reporter, not reproduced locally | upstream issue #4 comment | fail (recovered only by suspend/resume) |
| 2026-09-19 | Local field unit, SL4 AMD (MSHW0231 + AMDI0060), standard HID on fixed HEAD (doubled DESCREQ + hdr9, `e9c071b`) | Handshake DONE in 2–4 resets (`device_desc`/`rpt_desc` parse, `ready`, DATA flowing, input nodes `045E:0C19` present); storm (~9 RESET_RSP/s, `device_desc=0`) eliminated. Touch gestures (tap/drag/edge/palm), suspend/resume and cold-boot NOT yet performed — operator absent | live sysfs + dmesg, no archived bundle | handshake pass, gestures pending |

`captures/id5-20260718/raw_capture_status` records valid raw captures, but has
no associated firmware, kernel, distribution, or gesture-output result. It is
kept as an investigation artifact and is not a compatibility result.

## Known Constraints

- The MSHW0231 standard installer profile is now the Gate5 mode-1
  standard-transport CapImg bridge with the in-kernel multitouch tracker; this is a single-unit field qualification,
  not a broad E1 compatibility row.
- MSHW0162 retains the conservative standard-HID installer profile; Gate5 mode 1
  is not claimed there.
- Raw mode remains explicit opt-in through `sl4a-touch.sh install --raw`.
- Pen, palm rejection, the full one-through-five-finger matrix, long stress and
  broad platform compatibility still require E1 evidence.
- Secure Boot reuse/sign/reboot/auto-activation is qualified on the tested unit;
  fresh MOK generation/import + firmware enrollment remains separately unqualified.
