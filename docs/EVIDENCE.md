# Evidence Ledger

This ledger is the authority for release behavior. A document or code comment
that disagrees with it is a discrepancy to resolve, not a reason to change the
wire protocol.

## Levels

| Level | Meaning |
| --- | --- |
| E1 | Reproducible Linux hardware result with machine, firmware, kernel, distribution, date, and procedure recorded. |
| E2 | Versioned ACPI table, Windows trace, or captured descriptor. |
| E3 | Tracked host test or replay fixture. |
| E4 | Static proof of memory safety, ownership, or locking. |
| E0 | Hypothesis or partial observation. It cannot set a release default. |

## Accepted Facts

| Claim | Level | Source |
| --- | --- | --- |
| The controller is `AMDI0060` at `0xFEC10000` with a `0x100` resource. | E2 | `docs/acpi/dsdt.dsl:1523-1538` |
| The child SPI resource uses logical CS 0, mode 0, 33.33 MHz, and GPIO 0x55. | E2 | `docs/acpi/dsdt.dsl:1541-1573` |
| The HID DSM GUID is `6e2ac436-0fcf-41af-a265-b32a220dcfab`, revision 1, function 1. | E2 | `docs/acpi/dsdt.dsl:1576-1601`, `driver/spi-hid-core.c` |
| The captured MSHW0231 device is identified as VID/PID `045e:0c19`. | E2 | `captures/wintrace/analisi_MSHW0231.md:3-7` |
| The host protocol and CapImg decoder have executable bounds coverage. | E3 | `tests/protocol_test.c`, `tests/capimg_decoder_host_test.c` |
| Eight retained V0 raw-slot bodies have checksum-validated decoder replay coverage, including deterministic malformed-input rejection. | E3 | `tests/fixtures/replay/v1/manifest.json`, `tests/replay_fixture_test.py` |
| The merged post-association tracker tree passes the complete local host/sanitizer validation, deterministic 469-assertion panel emulator, and kernel-module build; GitHub Actions run `35678885908` also passed whitespace, host tests, Ubuntu kernel build, and current-kernel build. | E3 | `tools/validate-tracker-pr4.sh`, `.github/workflows/ci.yml`, GitHub Actions run `35678885908` |

## Observations Not Yet Release Evidence

| Observation | Status | Source |
| --- | --- | --- |
| 484 valid 4304-byte raw captures were recorded. | Partial Linux observation; machine and kernel provenance are absent. | `captures/id5-20260718/raw_capture_status` |
| An isolated GET/SET Feature experiment wrote successfully but timed out. | Does not prove activation sufficiency. | `captures/id5-20260718/isolated_set_status` |
| The raw pipeline creates beta multitouch contacts. | Requires replay comparison and hardware gesture matrix. | `driver/spi-hid-core.c` |
| 2026-09-21 targeted SL4 AMD pinch regression preserved two tracking IDs through far -> pinch -> close hold -> expand -> far; the trace exercised weak-component rescue and one armed occlusion episode with a 20-frame detector blackout, then released normally on intentional lift. | Targeted non-E1 hardware regression evidence only; full blinded matrix and release qualification remain incomplete. | `docs/HARDWARE_VALIDATION.md` |
| The current controller driver forces physical ALT_CS 1. | Implementation behavior; board mapping needs target-machine verification. | `driver/spi-amd.c` |
| Guided V4 decoded 17,018 strict CapImg frames and aligned them directly to balanced 14 DOWN / 14 UP OS-visible Windows pointer lifetimes over 19 guided holds. | Strong E2/E3 research evidence for this capture, but not Linux hardware release qualification or HeatCore internal state. | `userspace/surface-processor/PHYSICAL-TRUTH-V4-RESULTS-20261017.md`, `windows_pointer_oracle.py`, `v4_oracle_contract.py` |
| In V4, horizontal close physical-two remained one Windows pointer for all 160 conservative raw frames; a genuine vertical lift remained one for 157; a returned close finger transitioned from one for 86 frames to two for 67 while the region proxy remained one. | Falsifies connected-component count and morphology-only release as parity rules. It does not reveal Microsoft's internal classifier. | `userspace/surface-processor/PHYSICAL-TRUTH-V4-RESULTS-20261017.md` |
| A V4 affine fit from 1,123 one-pointer/one-region samples scored p95 0.695 cells on 2,000 independently assigned two-pointer contacts. The default research processor matched Windows contact count in 1,611/2,484 conservative guided frames. | Establishes a measured proxy coordinate transform and discrepancy baseline, not Windows classifier geometry or a parity percentage. | `calibrate_pointer_oracle.py`, `guided_hold_compare.py`, V4 results report |

## Open Discrepancies

| Topic | Conflicting material | Required resolution |
| --- | --- | --- |
| Raw frame layout | `HIDSPI_PROTOCOL.md` and `ACTIVATION.md` describe 16-bit/6912-byte cells; the replay corpus covers eight 4304-byte CapImg bodies only. | Capture labelled reset, descriptor, and gap traffic before changing either implementation or release claim. |
| Raw activation | Documents imply ID5 alone activates raw mode; isolated capture times out after GET/SET. The replay metadata records this as unqualified and has no activation response bytes. | Record a full cold-boot activation trace and resulting stream. |
| Clock description | Older register docs mention 12 MHz; tracked ACPI requests 33.33 MHz. | Treat ACPI 33.33 MHz as the current target default; verify with an E1 controller trace before changing speed logic. |
| Physical chip select | Driver forces ALT_CS 1 while ACPI exposes logical CS 0. | Record an E1 target trace before treating this mapping as portable board evidence. |
| Raw profile | Historical v1.2.0 installer enabled raw although the module default was standard. | Current installer uses standard mode; `--raw` is explicit opt-in. |
| `raw_enabled` interface | Older activation documentation refers to it; no such module parameter exists. | Removed from release instructions. Use `ready`, `protocol_stats`, and `baseline_status` sysfs attributes instead. |

No E4 entry is currently release-qualified: the branch contains lifecycle and
buffer hardening, but its review record is not a versioned static-analysis
artifact. Add an auditable analysis result before assigning E4 to that work.

## Recording New Evidence

Add a dated row to `COMPATIBILITY.md` and a source entry here for every E1
result. Preserve raw captures only when they contain no personal data and record
their checksum, firmware, kernel, profile, procedure, and expected result.
