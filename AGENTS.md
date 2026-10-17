# SL4A Surface touchscreen research handoff

**Before any driver, tracker, Windows-reverse-engineering, or hardware-test work**, read:

1. [`docs/WINDOWS-STACK-COMPLETENESS-20261017.md`](docs/WINDOWS-STACK-COMPLETENESS-20261017.md) — **2026-10-17 complete Windows stack gap audit; original 0C19/0C18 DLL binaries and 262 MSI payload files were RECOVERED IN GIT HISTORY (not absent)**.
2. [`docs/RESEARCH-HISTORICAL-RECOVERY.md`](docs/RESEARCH-HISTORICAL-RECOVERY.md) — **IMPORTANT: recovered 468 Windows Ghidra function bodies plus restored strict corpus analyzer from older Git commits**.
2. [`docs/RESEARCH-INDEX.md`](docs/RESEARCH-INDEX.md) — authoritative orientation, verified facts, scope and next steps.
3. [`docs/RESEARCH-CONTRADICTIONS.md`](docs/RESEARCH-CONTRADICTIONS.md) — superseded claims, known false statements, and unresolved evidence gaps.
4. [`docs/RESEARCH-SOURCE-MANIFEST.md`](docs/RESEARCH-SOURCE-MANIFEST.md) — exact original evidence locations, derived outputs, checkable numbers, hashes and missing external artifacts.
5. [`docs/EVIDENCE.md`](docs/EVIDENCE.md) and [`docs/GATE5-QUALIFICATION.md`](docs/GATE5-QUALIFICATION.md) for formal release-evidence and physical hardware scope.

These sources supersede unqualified claims in old experimental `docs/PIPELINE.md`, `docs/ETW_CSV_FORMAT.md`, `docs/CONTACT_ABI.md`, and `docs/CONFIG_TABLE.md`. **Do not confuse recovered Windows implementation details with Linux tracker heuristics.**

Non-negotiable:
- **Search deleted-file Git history before claiming an artifact is missing.** Historical commit `c94c399618b23588c95711ab4449d9400036ffd0` holds 468 complete TouchPen function exports and the original 181 KB GROUND_TRUTH.md; current branch tips do not. Original `tools/analyze_raw_corpus.py` has been restored and the strict Windows corpus check passed CI on 2026-10-17.
- Inspect sources and the latest GitHub branch/PR status before claiming a fact; this snapshot is dated **2026-10-17**.
- Do not ask for a new raw Windows CapImg capture until the tracked three-CSV **1,422-frame corpus** and eight binary fixtures have been used; the GitHub Actions replay already succeeded.
- No processed Windows touch IDs or final contact reports are established by these sensor captures. Sensor-region proxies are not Windows contact truth.
- Do not change Gate5, the stable #87 transport, or fork `main` driver on the strength of draft PR #12 offline results; no installation or live-touch validation of PR #12 is claimed.
- Windows track states 0–4, Linux blob-slot states 0–4, merge groups, and Linux tracking IDs are separate namespaces.
- Before porting or inventing a DLL classifier, check the **August MSI correction**: `+0xD40..+0xD78` is not a 10×11 Mahalanobis float matrix; `+0xED0` contains static fixed-point lookup data; `+0x8C4=0.7553579807`.
- Record each new finding with source path, branch, commit/hash, exact function/offset, whether *observed / derived / hypothesized*, reproducibility, and test. Update the canonical documents, not only a chat.

Current working paths: source fork `avgbob/SL4A_TouchScreen`; upstream `Syax89/SL4A_TouchScreen`; Windows research draft `research/windows-contact-processor-v1` / fork PR #12; experimental in-tree kernel draft PR #11; upstream PR #88 is experimental and still separate. These are **historical statuses**, not a guarantee of present state.
