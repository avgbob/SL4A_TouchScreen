# Critical recovery — original Ghidra source preserved in Git history

**Recovered by commit-history search: 2026-10-17.** This **corrects** the earlier index conclusion that the function bodies and historical `GROUND_TRUTH.md` were available only on an external machine. They are *absent from current branch tips*, but their original contents **survive in Git history**.

## How to access the material without collecting it again

Historical commit: [`c94c399618b23588c95711ab4449d9400036ffd0`](https://github.com/avgbob/SL4A_TouchScreen/tree/c94c399618b23588c95711ab4449d9400036ffd0)

- **468 complete exported Windows `TouchPenProcessor0C19.dll` decompiler `.c` files** plus one `index.tsv` (469 directory entries): [`docs/decomp/touchpen0c19_fullheat_20260716/functions/`](https://github.com/avgbob/SL4A_TouchScreen/tree/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions)
- Source report [`FINDINGS.md`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/FINDINGS.md); complete graph/report directory also contains `callgraph.tsv` (1,090 direct call edges), `static_data_references.tsv` (6,027 references), `exports.tsv`, `strings.tsv`, `vtables.tsv`, `scope_report.md` and logs.
- Original 182,732-byte [`docs/GROUND_TRUTH.md`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/GROUND_TRUTH.md). **HISTORICAL ONLY**: its claim that the entire Windows pipeline was ported is *disproved by the classifier/output gaps*; read as evidence history, not present validation.
- [`docs/decomp/touchpen0c19_tables_20260716/`](https://github.com/avgbob/SL4A_TouchScreen/tree/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_tables_20260716) includes table manifest, `ccl_consumers.c`, and `keyword_xrefs.c` (~1.7 MB of static xrefs); `docs/decomp/clean/` holds 42 decompiled controller/HID extracts; `docs/decomp/heat_resources_20260716/` contains resource analysis.
- Original [`tools/analyze_raw_corpus.py`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/tools/analyze_raw_corpus.py) SHA `3a6f6e1523e519ff435caea717a6d22a5aa80215`, removed at cleanup commit [`82807826`](https://github.com/avgbob/SL4A_TouchScreen/commit/82807826c36509621a0717640858b17c30a82b7b), **restored in the docs audit branch** to execute the original strict corpus checks.

Machine-readable index: [`RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json`](RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json) lists all 469 original exported function-directory entries and their historical Git blob SHAs/sizes. Paths refer to the **c94c399** historical commit, *not* to the current main working tree. If source is needed for legitimate analysis, fetch only the specific required old file; do not confuse decompiled C with independently licensed driver source or automatically republish 468 files on the active public branch.

GitHub historical search method, to reuse for ANY future 'missing' file:

```text
GET /repos/avgbob/SL4A_TouchScreen/commits?path=<previously-referenced-path>
GET /repos/avgbob/SL4A_TouchScreen/contents/<path>?ref=<historical-commit>
GET /repos/avgbob/SL4A_TouchScreen/git/trees/<historical-tree-sha>
```

**Search history BEFORE requesting uploads or new captures.** This recovery was missed by repeated checks of only `main`, PR #12, and the other current branch tips.

## Key recovered functions — real source, not guessed summaries

| Function | Historical source and blob hash | Directly visible finding and caution |
|---|---|---|
| Candidate classification `FUN_180601690` | [`180601690.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/180601690_FUN_180601690.c), `76723e8825d06f2b25c2a4e3f1b853024ee93036` | Builds a **ten-feature vector**, an active-feature mask from configuration bytes at `config+0x10c..0x125`, and evaluates a quadratic score against **four per-class config blocks**, including threshold words at `config+0x870` and matrices/means indexed near `config+0x134..`. It **does not** treat `+0xD40..+0xD78` as a 10x11 float matrix. Code branches at 108–173, final decisions at 184–214. Exact feature meanings and class semantics need typed xrefs; DO NOT invent labels. |
| Conditional hold `FUN_180606370` | [`180606370.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/180606370_FUN_180606370.c), `b45f9db30f6ec3f282713e9231d8b8c174408532` | Selects different thresholds based on hold enabled, active track count, sample flags; checks pixel/age/quality, **up to 10 history entries**, movement/size, signal. Calls `FUN_180608430(...,4)` and clears current history class only if gates pass (lines 37–82, 113–170, 213–224). **Not** a blanket three-frame Linux grace period. |
| Frame setup `FUN_180600820` | [`180600820.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/180600820_FUN_180600820.c), `017e9c6644d8f9fc806e972910e9b9e5b184f5d0` | Selects per-cycle config floats, resets candidate areas, invokes `FUN_180604ab0` and `FUN_180604bd0`; the prior generic 'gain adaptation' label is not a complete interpretation. |
| Candidate processing `FUN_180600c40` | [`180600c40.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/180600c40_FUN_180600c40.c), `982fd637201fa7751f50d303e3c0d74ed05022fc` | Candidate field conversions, event/class conditions, bound/geometry and signal-based filters; **not** simply Linux's 4-connected CCL. |
| Post-report grouping `FUN_1806025c0` | [`1806025c0.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/1806025c0_FUN_1806025c0.c), `b4c5135b1ef153f70a00938a156a395def1fc71f` | Groups/marks close eligible local records; does not simply destructively merge inputs. |
| Association `FUN_180607a20` | [`180607a20.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/180607a20_FUN_180607a20.c), `3113a8e4419b757d1241022c19250edd0d90f7a3` | Association radii and special continuity; verify coordinate units and cost matrix orientation. |
| State accounting `FUN_180608430` | [`180608430.c`](https://github.com/avgbob/SL4A_TouchScreen/blob/c94c399618b23588c95711ab4449d9400036ffd0/docs/decomp/touchpen0c19_fullheat_20260716/functions/180608430_FUN_180608430.c), `e1e2bc895690637dac8d0cd71444b5f82151cf5d` | Windows state counters, 0 free, 1/2 active, 3 transitional, 4 inactive/hold. Not Linux's enum. |

The recovered classifier is **more concrete than earlier docs admitted**: the core score-building path is available, and its use of 10-dimensional configurable quadratic terms can be investigated without collecting a new binary. **It does not automatically establish the meanings of all ten features, all score outputs, the runtime config producer, or the final class/OS contact mapping.** Any implementation should preserve this boundary.

## Recovery ramifications

1. `docs/RESEARCH-INDEX.md` and the source/contradiction manifests must treat these 468 functions as **RECOVERED_IN_GIT_HISTORY**, not 'not committed' or 'external-only'. Keep original `c94c399` hash pinned.
2. Prior claims that DLL body recovery is the *primary prerequisite* can be retired. **The next work is function analysis/type recovery and behavioral implementation**, followed by actual processed Windows touch-output validation.
3. The old analyzer may restore the historical strict checks, including raw per-trace SHA, cadence, and segment falsification that PR #12's newer extractor did not reproduce. Run `python3 tests/raw_corpus_test.py` in CI (and fail on skip), not just the new frame-count gate.
4. `heatcore_20260716/functions/*` may not be present under that literal path; inspect this commit's `docs/decomp/heat_resources_20260716/` and code history before claiming those specific HeatCore function bodies are likewise recovered. **Only the listed TouchPen files have been directly verified.**
5. Do **not** restore older source implementation blobs or `GROUND_TRUTH.md` indiscriminately into today's main branch: their unqualified Windows parity statements and legacy transport behaviors can regress the working driver. Historical permalinks are safer.

## Direct Surface Laptop 4 local verification — 2026-10-17

The operator ran the following on the **Ubuntu Surface Laptop 4** at
`/home/jo/SL4A_TouchScreen-host56` (provided terminal output):

```text
$ git cat-file -t c94c399618b23588c95711ab4449d9400036ffd0
commit
$ git cat-file -s c94c399:docs/decomp/touchpen0c19_fullheat_20260716/functions/180601690_FUN_180601690.c
7426
$ git cat-file -s c94c399:docs/decomp/touchpen0c19_fullheat_20260716/functions/180606370_FUN_180606370.c
5949
$ git ls-tree -r --name-only c94c399 docs/decomp/touchpen0c19_fullheat_20260716/functions/ | grep -c '\\.c$'
468
$ git cat-file -s c94c399:docs/GROUND_TRUTH.md
182732
```

The operator then successfully invoked `git archive c94c399` piped to
`tar -x` into **`/home/jo/sl4a-evidence-recovered/`**, extracting
`touchpen0c19_fullheat_20260716/`,
`touchpen0c19_tables_20260716/`, historical `GROUND_TRUTH.md`, and
`analyze_raw_corpus.py`. **Filesystem extraction command returned to the
prompt without reported errors**; directory contents have not yet been
independently enumerated after extraction. This is a verified *local
historical Git-object* recovery, not evidence of the original Windows DLL.

The operator separately ran `ls -lah` for
`~/sl4a-analysis/`, `~/sl4a-analysis/ghidra-findings/`, and
`~/sl4a-analysis/raw-corpus/`: all produced no output with stderr suppressed.
A limited search for `TouchPenProcessor0C19.dll`, `HeatCore.dll`,
`FINDINGS3.md`, or `*.etl` in `~/sl4a-analysis`,
`~/Downloads` and `~/Documents` yielded no matches. This **does not**
prove those files are absent from the Windows NTFS partition, other home
folders or mounted devices. Do not request the 468 functions again.

**Byte-size correction:** older audit text said 181,159 *bytes* for
`GROUND_TRUTH.md`; that was the decoded Unicode text's character count
in a tool response. The Git object size is **182,732 bytes**. The difference
is not a corruption indicator.
