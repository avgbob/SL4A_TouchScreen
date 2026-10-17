# SL4A research source manifest and artifact locations

**CRITICAL HISTORY RECOVERY (same day):** [RESEARCH-HISTORICAL-RECOVERY.md](RESEARCH-HISTORICAL-RECOVERY.md) documents **468 Windows TouchPen Ghidra `.c` bodies** in commit `c94c399`, indexed in [RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json](RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json), and the restored strict corpus analyzer; previous text below saying those exports were only external is superseded.

**Audited:** 2026-10-17 against `avgbob/SL4A_TouchScreen:main` commit `c081075492feae4146510cf0d364b23fd0a394eb`, plus research draft PR #12 at `0782c6cfca09953f29ddb9475561900108d3713e`. Relative paths below resolve from the repository root. This is not a claim that externally referenced local directories exist in the current execution environment.

## 1. Original or near-original tracked Windows evidence

| Tracked path | Size / source identity | Role and limitation |
| --- | --- | --- |
| `traces/surface_touch.csv` | 19,514,888 bytes; git blob `9c4a2a90f4b44ca255cf2c74b5098ccbaba193a5` | July 2026 SPB raw touch, 537 complete 0x0c bodies. Has no confirmed Windows processed IDs. |
| `captures/wintrace/surface_touch.csv` | **exact same blob SHA** | Mirror, not another 537 frames |
| `traces/surface_init.csv` | 9,055,161 bytes; blob `5b2a049276506a5e1538fbef43953afc7faddfe` | July initialization/SPB data, 247 bodies |
| `captures/wintrace/surface_init.csv` | **exact same blob SHA** | Mirror, not another 247 frames |
| `traces/surface_boot_auto.csv` | 29,339,823 bytes; blob `a46277ba81b6f4e8a343f66d8587e4b0998ec735` | July Windows boot, 638 bodies |
| `captures/wintrace/touch_spb_transactions.txt` | 6,623,988 bytes | Derived transaction text; not a separate experimental data set or final HID capture |
| `captures/wintrace/surface_{touch,init,boot_auto}_summary.txt` | ~10–12 KB each | `tracerpt` event summaries, event counts and zero-loss claims for the corresponding captures |
| `captures/wintrace/mshw0231_report_descriptor.txt` | 10,607 bytes | Windows descriptor evidence; full descriptor 936 bytes per Gate2 |
| `captures/wintrace/providers.txt` | 8,531 bytes, identical to `tools/windows_capture/providers.txt` | Enumerated ETW provider reference |
| `captures/id5-20260718/frames/raw-slot-0.v0` ... `raw-slot-7.v0` | Eight **distinct** 4,304-byte bodies; Git SHA pinned in the JSON snapshot | Retained binary decoder/capability fixtures; not eight labelled gesture sessions |
| `captures/id5-20260718/raw_capture_status` | 513 bytes | Reports 484 valid bodies in a separate partial Linux field experiment; **the 484 complete bodies are not checked in as a corpus here** |
| `evidence/windows/gate2/windows-golden.jsonl` | 4,287 bytes | Verified normalized lifecycle/feature/report information extracted from September Gate2 ETL. Not the full ETL. |
| `evidence/windows/gate2/ATTEMPT-2026-09-22-{REJECTED,PROVIDER-COVERAGE-REJECTED}.md` | Both present | Failed/rejected evidence sessions: *do not* promote to a passing trace |
| `docs/acpi/dsdt.dsl`, `docs/acpi/ssdt*.dsl`, and matching `.dat` | 20+ ACPI files | Device/controller/DSDT reference. Use target model/revision scope, not universal Surface claims |
| `evidence/windows/{amdspi,hidspi_km,SurfaceDigitizerHidSpiExtnPackage,SurfaceTouchPenProcessorUpdate_13}.inf` | Four INF files | OEM/transport/HeatCore binding evidence and provider identity |
| `evidence/windows/SOURCE-HASHES.md` | Four source hashes | Exact original source-bundle hash provenance versus Git's normalized text bytes |

These 1,422 bodies are **three distinct captures** and include 537 + 247 + 638. The 2 duplicated CSV paths are **aliases**. Do not sum files by directory. Historical `tests/raw_corpus_test.py` preserves expected counts, per-stream payload SHA-256 values, cadence runs and static sections. The original `tools/analyze_raw_corpus.py` was recovered from Git commit `c94c399` and **restored**. The previously skipping `tests/raw_corpus_test.py` has now executed successfully with **all strict stream-hash, cadence, and static segment assertions** in [CI 39052198562](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39052198562); do not continue calling this gate absent.

### Known archived corpus expected outputs

- Touch 0x0c count `537`; payload-stream SHA-256 `3d2122e71d0855771897dbb35fb00fc3dfc4183be8521b5dae76825109851aa2`.
- Init 0x0c count `247`; payload-stream SHA-256 `ebe1eed7fb69c5c3a580190febe1678952de189c07601abcd5eb7e889b5accc0`.
- Boot 0x0c count `638`; payload-stream SHA-256 `aef0f6da2a60ea872dd2cfa0d07253bc7a581970ce4277463b1a765eeb2acd6d`.
- The older strict stream SHA and cadence `expected_falsification` are tracked in `tests/raw_corpus_test.py`; **PR #12's extractor checks structure/counts/replay; separately, the recovered original analyzer is now checked by mainline documentation-audit CI against all historical byte-for-byte SHA/cadence/segment assertions.**

### October 17 GitHub Actions verification

- [Run 39049773971](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39049773971): 31 unit tests, 1,422 corpus frames, 30 baseline / 507 tracking on touch session, 501/507 proxy candidate-count agreements, 518 candidates / 452 research contacts. See its `offline-tests` job logs.
- [Run 39049953280](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39049953280): same corpus/proxy pass; TouchAndPen event probes found **0 matching event types in each checked-in July CSV**. A negative *event-export search*, not a claim Windows did not synthesize contacts.
- Research code (not on main before PR merge): `userspace/surface-processor/{processor.py,replay.py,windows_evidence.py,analyze_windows_proxy.py,compare.py,test_*.py,README.md,AUDIT.md,WINDOWS-EVIDENCE-INVENTORY.md}` on `research/windows-contact-processor-v1`, and `.github/workflows/surface-processor.yml`.
- Reproduce via GH checkout of the **research branch** (no `/dev/hidraw` or live device required):

```sh
python3 -m unittest discover -s userspace/surface-processor -p 'test_*.py' -v
python3 userspace/surface-processor/windows_evidence.py \
  traces/surface_boot_auto.csv traces/surface_init.csv traces/surface_touch.csv \
  --output-dir /tmp/sl4a-windows-corpus --check-known-counts
python3 userspace/surface-processor/replay.py \
  /tmp/sl4a-windows-corpus/surface_touch/frames.txt > /tmp/contacts.jsonl
python3 userspace/surface-processor/analyze_windows_proxy.py \
  /tmp/sl4a-windows-corpus/surface_touch/frames.txt /tmp/contacts.jsonl
```

## 2. Decompiled/reverse-engineered *derived reports* that ARE tracked

| Source | Use |
| --- | --- |
| `docs/decomp/MULTITOUCH_STATIC_DECOMP.md` | Actual Windows ownership and function addresses, `HeatCore` plugin->contact report mapping; 0x3a pointer vs 0x21 HID record path; flags unknown |
| `docs/decomp/SURFACE_TRACKER_DECOMP.md` | Exact stage ordering; 0xB0 candidate, 0x254 track, 0x34 emitted, 10-sample history, state setter, Hungarian, group rewrite, gap >5 |
| `docs/decomp/HEATCORE_REPORT_TABLE.md` | Descriptor/report table dispatch and Usage 0x62/0x56; not final content type labels |
| `docs/SL4_MSI_Mining_Report.md` | August audited 0x0C19 DLL SHA/version and static tables; corrects unproven Mahalanobis label, `+0x8c4`, `+0xed0` |
| `docs/CONFIG_TABLE.md` | Historical/revised constant table; use corrected version + warning about unknown behavior |
| `docs/WINDOWS-ALIGNMENT.md` | Windows signal approximations and *explicitly invented* Linux heuristics; read alongside later August MSI findings |
| `docs/FRAME-MATRIX.md` | Historically tested wire frames and actual register/sequence distinction; `0x56` payload differs across captures |
| `docs/GOLDEN-SM.md`, `docs/GATE2-CAPTURE.md` | Gate2 Windows power, reset, descriptor, feature chronology with precise capture scope |
| `docs/GATE5-QUALIFICATION.md` | Narrow hardware qualification for chosen Linux default |
| `tools/ghidra/{DecompileAll.java,DecompileByAddress.java,...}` | Scripts to **recreate** missing function exports if DLL/binary and Ghidra project found |
| `tools/windows_capture/{touch_boot.wprp,capture_runtime.cmd,collect_touch_host.ps1,...}` | Previously prepared TraceLogging capture; provider `Microsoft.Surface.TouchAndPen.Prod` GUID `{3FA102E9-1A62-5490-7AF8-6088C2F9E6BE}`. Script existence is NOT proof runtime ETL was collected |
| `tools/surface_tracker.py` | Partial Python Windows-*inspired* oracle; module doc states missing classification and hold/lift, and enlarges practical radius; **not an independent full Windows truth source** |
| `tools/surface_tracker_oracle.py` | Focused Windows report-group coalescing model; this specific behavior has decompilation basis |

## 3. Known reference-only external artifacts (not in audited git tree)

These **historical names and locations are valuable retrieval clues, not invented files**. Check the original Surface analysis system, archived drives and user-provided bundles before asking for new collection.

| Referenced artifact/location | Evidence of reference | Current audit status |
| --- | --- | --- |
| `~/sl4a-analysis/ghidra-findings/{FINDINGS.md,FINDINGS2.md,FINDINGS3.md}` | `docs/WINDOWS-ALIGNMENT.md` | Not present in audited repo; actual local path needs filesystem check |
| `touchpen0c19_fullheat_20260716/functions/180601690_FUN_180601690.c`, `180606370_FUN_180606370.c`, `180600820_FUN_180600820.c`, `180600c40_FUN_180600c40.c` | `docs/decomp/SURFACE_TRACKER_DECOMP.md` | **Recovered in historical Git commit c94c399**: 468 complete `.c` files; exact directory and per-file hashes in RESEARCH-HISTORICAL-RECOVERY.md |
| `heatcore_20260716/functions/{180015ff0_FUN_180015ff0.c,1800351a0_FUN_1800351a0.c,...}` | `docs/decomp/MULTITOUCH_STATIC_DECOMP.md` | This specific HeatCore function-export directory was not found with the recovered TouchPen closure; inspect other historical sources, full contact egress remains unresolved |
| `~/windrivers/` original `.sys/.dll/.pdb` | `tools/ghidra/README.md`; MSI report SHA | Files not committed by design; Windows binaries not recoverable from secondary reports alone |
| `SL4-SPI.zip`, `SL4-MSI-MINE.zip` | `evidence/windows/SOURCE-HASHES.md` | Previously analyzed August archives; original ZIPs not located in audited repo/current accessible Library search |
| `C:\gate2\gate2.etl`, `markers.tsv` | `docs/GOLDEN-SM.md` | ETL SHA-256 `4583C62F0A7AC1B2099AA904FF8F61BF1DE065A2A2EF1AB58397950E57906552`, size **398,721,024 bytes**, **3,254,430 events**, **0 lost**. Compact JSONL available; original binary not checked in |
| Windows **runtime** ETL exported with TouchAndPen TraceLogging provider and fields `TouchBlobCoMX/CoMY` | `tools/windows_capture/README.md` | **Capture method exists; completed capture not established by repo.** July CSV event probes negative; locate ETL before planning new run |
| `docs/GROUND_TRUTH.md`, `docs/decomp/heatcore_20260716/` | Referenced in historical roadmap/notes | `docs/GROUND_TRUTH.md` **recovered at c94c399** (181 KB, explicitly outdated claims). `docs/decomp/heatcore_20260716/` under that literal name not yet recovered. |
| `tools/analyze_raw_corpus.py` | Required by `tests/raw_corpus_test.py` | **RESTORED** from Git history at c94c399; strict test PASSED in CI 39052198562 |

## 4. Numeric/scope traps (do not collapse these)

- **4309 SPB read** with 5-byte preamble -> **4304 V0 body** -> **3456 8-bit raster**, versus **4300-byte numbered HID report** in `userspace/sl4a-heat`. These are different envelopes of the same sensor frame, not competing sensor layouts. Decoder must honor section offsets, not hard-coded raster offsets.
- **48 Windows internal tracks** vs historical **47 Linux MT slots** vs actual Windows visible finger limit **not established**.
- 0x34 local emitted plugin struct vs 0x3a HeatCore pointer struct vs 0x21 HID injection struct; no assumed equal IDs or state enums.
- Static threshold `+0xC98` **36.0 squared** selects grouping criterion *only after appropriate classes and groups exist*; it does not authorize proximity-based pre/post candidate deletion.
- `+0x8DC = 0.545009`, `+0x8E0 = 1.218098` are per-device floats in association decomp, but older `ASSOC_RADIUS_*` Linux tuning and scaling guesses are **not recovered Windows radius policy**.
- Touch raw stream has **537 frames**, only **507 tracking frames** after **30 baseline** in PR #12, not 537 windows-HID frames. The 501 agreement is with **raw connected regions**, not final Windows contacts.
- The **2026-09 Gate2 trace** and the **July 2026 three CSV traces** are separate capture campaigns. Do not combine event totals or assume provider coverage is the same.

## 5. Maintenance instructions

- Treat [RESEARCH-INDEX.md](RESEARCH-INDEX.md) as canonical summary; [RESEARCH-CONTRADICTIONS.md](RESEARCH-CONTRADICTIONS.md) as the supersession and unresolved-blocker register.
- For each new external file, record canonical file path, original host/date, captured raw hash, normalized Git/blob hash if checked in, size, source derivation command, and whether personal data requires restricted storage. Do not add proprietary Microsoft DLLs/ETLs to a public repo without a licensing/privacy review.
- For an artifact marked **not in this tracked tree**, search external stores/other Git refs before concluding it never existed. Never substitute a code comment or derived CSV for its original bytes.
- When a gap is resolved, commit the new evidence and update all three canonical docs plus the evidence gate. Distinguish `FOUND`, `READ`, `VALIDATED`, and `WINDOWS-OUTPUT-COMPARED` statuses.

## Git history retrieval is now a required discovery step

Historical commit [`c94c399`](https://github.com/avgbob/SL4A_TouchScreen/tree/c94c399618b23588c95711ab4449d9400036ffd0) holds the formerly deleted **468 complete TouchPen processor `.c` decompilation functions**, `FINDINGS.md`, `callgraph.tsv`, `static_data_references.tsv`, `docs/GROUND_TRUTH.md` (181 KB), `touchpen0c19_tables_20260716/` and AMD/HIDSPI `docs/decomp/clean/` artifacts. Original `tools/analyze_raw_corpus.py` was also present and has been reinstated. See [RESEARCH-HISTORICAL-RECOVERY.md](RESEARCH-HISTORICAL-RECOVERY.md) for fully qualified links and verified hashes; see [RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json](RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json) for all 469 function-dir entries. The earlier 'external-only' descriptions of these specific files are **superseded**, but independent runtime processed TouchAndPen ETL and original Microsoft DLL bytes are still not located.


## Local Surface laptop recovery attested in operator transcript (2026-10-17)

The Surface laptop's repository at `/home/jo/SL4A_TouchScreen-host56`
contains historical commit `c94c399` and all **468** decompiler `.c` paths
in that commit. Actual Git object sizes confirmed: classifier `7426`,
quality hold `5949`, `GROUND_TRUTH.md` **`182732` bytes**. A previous
character count `181159` must not be mislabelled a byte size. The user
executed `git archive` / `tar -x` to
`/home/jo/sl4a-evidence-recovered/` without displayed errors. Original
DLL/ETL files were **not found by a limited `find`** over three Linux-home
paths; other volumes were not searched. Details:
[RESEARCH-HISTORICAL-RECOVERY.md](RESEARCH-HISTORICAL-RECOVERY.md).
