# Surface Laptop 4 AMD touchscreen — canonical research index

**Audit date:** 2026-10-17. **Scope:** `avgbob/SL4A_TouchScreen` tracked `main` tree (352 file blobs / 389 tree entries at `c081075492feae4146510cf0d364b23fd0a394eb`), current research PR #12 (draft), upstream PRs, the indexed prior-source reports, and archived Windows ETW inputs. This is a *source-and-claim audit*, not a new Windows DLL disassembly or new live hardware qualification. The research PR had 403 tree entries when inspected; the two trees have different content.

**Read this first in future conversations.** The original source locations and checksums are in [RESEARCH-SOURCE-MANIFEST.md](RESEARCH-SOURCE-MANIFEST.md); competing assertions are adjudicated in [RESEARCH-CONTRADICTIONS.md](RESEARCH-CONTRADICTIONS.md). [docs/EVIDENCE.md](EVIDENCE.md) retains the project's E0/E1/E2/E3/E4 release-evidence definitions. A finding must say both *what is known* and *which layer produced it*.

## A. No need to rediscover these facts

| Question | Current evidence-grounded answer | Primary source |
| --- | --- | --- |
| Which hardware? | SL4 AMD: `AMDI0060` controller, ACPI `MSHW0231`, HID VID:PID `045e:0c19`, HID-over-SPI **V0**, 936-byte report descriptor; do not generalize to MSHW0162/0230. | `docs/acpi/dsdt.dsl`; `docs/GOLDEN-SM.md`; `docs/GATE5-QUALIFICATION.md` |
| Where is Windows touch processing? | `hidspi.sys` delivers Col02 CapImg; `HeatCore.dll` loads `TouchPenProcessor0C19.dll`; Windows synthesizes contact output above the SPI bus. The extension INF binds the processor; it is not itself a standalone chip driver. | `docs/decomp/MULTITOUCH_STATIC_DECOMP.md`; `evidence/windows/SurfaceTouchPenProcessorUpdate_13.inf`; `docs/SL4_MSI_Mining_Report.md` |
| What is the real raw data? | ID `0x0c` V0 body **4304 bytes** on retained fixtures; CapImg heat raster **72 x 48 x 8 bits = 3456 bytes** in container, with additional sections, not a generic 6912-byte 16-bit raster. Numbered HID report has a different envelope length. | `tools/decode_v0_capimg.py`; `driver/spi-hid-capimg.c`; `captures/id5-20260718/frames`; `tests/raw_corpus_test.py` |
| Have Windows raw frames been collected? | **Yes: 1,422 complete** raw frames in three July Windows ETW CSVs: **638** boot, **247** init, **537** touch. Reconstructed and CapImg-validated in Oct 17 PR #12 GitHub Actions. Eight additional 4304-byte V0 snapshots exist. | `traces/*.csv`; `tests/raw_corpus_test.py`; [Actions 39049953280](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39049953280) |
| Are the two CSV directories independent evidence? | **No:** `captures/wintrace/surface_touch.csv` and `traces/surface_touch.csv` have exactly the same Git blob SHA, likewise both `surface_init.csv` files. Avoid doubling counts. | pre-audit `main` git tree; manifest |
| What Windows startup is observed? | Gate2 after descriptor: report `0x56` SET, GET6/reply, then SET5=1; `_PS0 -> _RST` on activation; `_PS3` on stop. The `0x56` report belongs to a distinct HID collection. Do not hard-code an observed boot's arbitrary 0x56 payload or assume those actions all share one owner. | `docs/GOLDEN-SM.md`; `docs/GATE3-ARCH-A.md`; `docs/FRAME-MATRIX.md` |
| What was physically qualified on Linux? | One SL4 AMD Gate5 standard-transport profile, after `GET6` write-only -> approximately 4.5-5.5 ms -> `SET5`, with DATA draining and safe startup; one unit's cold/warm/s2idle/installer results. This **does not** establish classifier fidelity or E1 broad compatibility. | `docs/GATE5-QUALIFICATION.md`; `docs/UPSTREAM-RECONCILIATION.md`; `docs/EVIDENCE.md` |
| Is current tracker Windows equivalent? | **No.** Linux uses CCL, Hungarian matching, close-contact suppression/occlusion heuristics, EMA and slot-state adaptations. Microsoft classifier, gains, quality-gated hold/lift, and final report visibility/IDs are not faithfully implemented. | `docs/WINDOWS-ALIGNMENT.md`; `docs/PIPELINE.md` (historical Linux approximation); `userspace/surface-processor/AUDIT.md` on PR #12 |
| What did DLL decomp prove? | Pipeline order: prep `FUN_180600820`, candidate extraction `180600c40`, classifier `180601690`, global association `180606040/180607a20`, track update `180608000/180607c60`, state `1806067d0`, emission `180601c10/180601dd0/180602a90`, grouping `1806025c0`. Internal tracks up to **48**, stride `0x254`, 10 history entries; frame gap >5 triggers release. | `docs/decomp/SURFACE_TRACKER_DECOMP.md` |
| Does Windows coalescing delete a close candidate? | Decompiled `FUN_1806025c0` rewrites group labels and may change class 1 -> 7; *it retains the two local records*. Final Windows OS-visible emission rules remain unproven. Group labels are not IDs. | `docs/decomp/SURFACE_TRACKER_DECOMP.md`; `tools/surface_tracker_oracle.py` |
| Are Windows candidate classes known? | Control-flow class values `1,3,4,5,7` are seen but their human semantics are not established; the former `1=palm`/`3=coalesced` mapping was conjecture. | `docs/CONTACT_ABI.md` **corrected on PR #12 and this audit**; MSI analysis |
| Did we recover Windows classifier matrix? | **No.** The prior 10x11 Mahalanobis float array assigned to `+0xD40..+0xD78` is disproven by the August MSI static binary: it is nonzero structured byte/index data, with `0xff` sentinels. | `docs/SL4_MSI_Mining_Report.md`; corrected `docs/CONFIG_TABLE.md` |
| What was wrong in config table? | `+0x8C4` is **0.7553579807**, not `0.754732`; `+0xED0` onward has static floats/20-entry quadratic fixed-point table, not a purely runtime-zero regional map. Runtime-zero ranges exist at E20/E60/EA0, but their producers are not proven. | `docs/SL4_MSI_Mining_Report.md` |
| Is Windows **processed contact output** captured? | **Not in checked-in July CSVs.** Oct 17 CI event probe found **zero TouchAndPen matching event types** across boot/init/touch exports. Gate2 normalized JSONL is transport/lifecycle, not contact IDs. The original runtime TraceLogging ETL, if retained elsewhere, was **not located** in tracked tree. | PR #12 `WINDOWS-EVIDENCE-INVENTORY.md`; [Actions 39049953280](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39049953280) |

## B. Keep the evidence layers separate

1. **Device/controller/protocol:** ACPI DSDT, Windows ETW SPB/GPIO, descriptor, V0 frames, Gate2/5 lifecycle. The 2026-09 Gate2 ETL has a documented hash and 3,254,430 events, 0 lost; only compact normalized output is tracked.
2. **CapImg sensor signal:** raw 72x48 bytes, c590 lookup, 30-frame calibration baseline, 0.02 rise/0.04 noise thresholds, `byte < 135` (=0.1) reference region gate. Different filters operate at different stages; do not declare them interchangeable.
3. **Candidate/track:** Windows peak detection, classification, global assignment, history, conditional hold/lift and grouping. Some stage order and structs recovered; runtime dynamic values and exact full behavior incomplete.
4. **Published input:** Windows HeatCore VHF/HID and pointer injection, Linux MT slots/IDs. Windows source record `0x34`, pointer record `0x3a`, and injected contact record `0x21` are **different formats**. No exact Windows output-ID equivalence established.
5. **Linux tests:** synthetic gestures, panel emulator, tracked replay fixtures, 537 real-frame offline replay. These establish properties of **our** code, not Windows equivalence or physical touch quality.

## C. What has already been measured (not a Windows contact oracle)

- Oct 17 PR #12 `offline-tests` GitHub Actions: **31 Python tests** passed; parser found **638 + 247 + 537** complete Windows CapImg frames; the 537-frame touch sequence split into **30 calibration + 507 tracking** frames. See [run 39049953280](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39049953280).
- Against a *separate sensor-only CCL proxy* with a byte-135 threshold and two-pixel/weight filter, prototype candidate counts equaled proxy counts in **501/507** tracking frames, exceeded them in **6**, and were lower in **0**. Totals: **518** prototype candidates, **452** published *prototype* contacts; raw regions 590, qualified proxy regions 541. **Not** measured Windows misses, Windows palm rejection, Windows tracking continuity, or two-finger separation after signals merge.
- Sept Gate5 physical testing: cold/warm/s2idle and Secure Boot installation were scoped to a *single unit*. Historical later two-finger tests reported an original finger lingering under certain runs; do not infer the root cause from replay counts alone.
- Frozen support contract: release authority remains `docs/EVIDENCE.md` and precise dated hardware qualification; do not promote host (E3) or partial hardware tests into an E1 release claim.

## D. Branch map (snapshot, do not assume future status)

| Ref | Purpose / decision |
| --- | --- |
| `avgbob:main` at `c081075...` (before this docs-only audit) | Existing production/Gate5 and historical tracker; avoid algorithm/transport changes without physical qualification |
| `avgbob:research/windows-contact-processor-v1` / [PR #12](https://github.com/avgbob/SL4A_TouchScreen/pull/12), head `0782c6c...` | Research-only CapImg parser, offline contact processor, ETW extractor, comparator and real-corpus CI. Draft, not deployable/Windows-equivalent |
| `avgbob:experiment/in-tree-kernel` / [PR #11](https://github.com/avgbob/SL4A_TouchScreen/pull/11) | In-tree kernel staging; driver blob shares existing fork tracker, **not** independently recovered Windows algorithm and not hardware-tested as a new kernel |
| [upstream PR #87](https://github.com/Syax89/SL4A_TouchScreen/pull/87) | Opt-in standard transport CapImg MT, historically older `raw_ghost_merge` tracker; transport and algorithm review separable |
| [upstream PR #88](https://github.com/Syax89/SL4A_TouchScreen/pull/88) | Post-association coalescing experiment; **not** reliable Windows fidelity. Open draft in audit. Closing does not remove related tracker code in `avgbob:main` |
| [upstream PRs #89–91](https://github.com/Syax89/SL4A_TouchScreen/pulls) | Independent Secure Boot, testing and bounds work; do not tie to #88 retirement |

## E. Work ordering / gates

- **First:** retrieve and inspect original decompiler *function bodies* from historical local paths `touchpen0c19_fullheat_20260716` (particularly `FUN_180601690`, `FUN_180606370`, `FUN_180600820`, `FUN_180600c40`), `heatcore_20260716`, and `~/sl4a-analysis/ghidra-findings`. They are referenced in docs but **not tracked in the source tree**; avoid falsely declaring the original binary or ETL never existed.
- **Second:** check for the specifically configured `Microsoft.Surface.TouchAndPen.Prod` **runtime ETL** with `TouchBlobCoMX/CoMY` fields. Capture scripts exist; the checked-in July CSV trio does not include processed-contact observations. Do not request a new **raw-only** capture.
- **Third:** reconstruct classifier, gain, peak/centroid split, state/lift and final HeatCore reporting separately with source-derived tests; do not seed guessed classifier types or synthetic status codes as Windows truth.
- **Fourth:** compare archived real heatmaps and stage outputs, add aligned processed Windows oracle if found; qualify legitimate ID continuity, finger lift and group visibility with labelled physical gestures.
- **Finally:** evaluate userspace processing (IPTSD-style) vs in-kernel port; retain rollback and Gate5; no defaults switched until physical test matrix and E1 acceptance.

## F. Rules for updating this index

Each new observation **must** add a dated row to [RESEARCH-CONTRADICTIONS.md](RESEARCH-CONTRADICTIONS.md) if it resolves/conflicts with an existing assertion, and to [RESEARCH-SOURCE-MANIFEST.md](RESEARCH-SOURCE-MANIFEST.md) if it introduces source material. Record: file+branch+SHA, original machine/context or GitHub Actions URL, relevant line/function/offset, extraction command, comparison expected/actual, evidence level and known uncertainty. When closing an issue mark `RESOLVED` with proof; don't erase history. A future conversation should start with the canonical docs and missing-artifact list rather than independently rediscovering the trace layout and already disproven config claims.
