# Windows MSHW0231 evidence inventory — October 17, 2026

This index was made by checking the tracked GitHub tree and the preserved
reverse-engineering reports. It does **not** certify that every historical
binary, ETL, decompiler output, or processed-contact record is accessible here.
The distinction between SPB sensor data and Windows *processed contacts* is
critical. Nothing in this index qualifies the experimental tracker for use.

## Tracked source evidence

| Source | Role | What it can prove | What it cannot prove |
|---|---|---|---|
| `traces/surface_touch.csv` / `captures/wintrace/surface_touch.csv` | Historical ETW/SPB export | Raw report bodies, SPI ordering, timestamps, controller transaction shapes | The contact IDs emitted by HeatCore/VHF |
| `traces/surface_init.csv` / `captures/wintrace/surface_init.csv` | ETW initialization export | Initial handshake and additional raw heatmap frames | Classifier decisions |
| `traces/surface_boot_auto.csv` | ETW boot export | Additional heatmap frames and boot timing | Processed touchscreen reports |
| `captures/wintrace/touch_spb_transactions.txt` | Derived SPB transaction text | Transport chronology | Windows touch classifications |
| `captures/id5-20260718/frames/raw-slot-{0..7}.v0` | Eight retained binary V0 bodies | Decoder frame-layout checks | A labelled complete finger-sequence oracle |
| `evidence/windows/gate2/windows-golden.jsonl` | Gate2 windows: cold boot, enable, one/two finger, sleep/resume | Lifecycle and `0x56 -> GET6 -> SET5` sequence | Generated `0x40` contact report above SPI |
| `docs/decomp/{MULTITOUCH_STATIC_DECOMP,SURFACE_TRACKER_DECOMP,HEATCORE_REPORT_TABLE}.md` | Recovered DLL control-flow and data structures | Processing *order*, fields and some constants | Unrecovered runtime matrix semantics or final HID IDs |
| `docs/SL4_MSI_Mining_Report.md` | August binary static-table audit | `0x0C19` DLL identity and corrected table contents | Code xrefs and runtime use of every static value |
| `tools/ghidra/*.java` | Headless decompilation utilities | Repeatability *if binary and Ghidra project exist* | The previously exported decompiled `.c` functions themselves |
| `tools/windows_capture/touch_boot.wprp` | TouchAndPen ETW provider capture configuration | Possibility of `TouchBlobCoMX/Y` telemetry in a fresh/preserved ETL | Presence of processed events in the tracked July CSV files |

The repository's historical corpus test `tests/raw_corpus_test.py` records
**1422** valid `0x0c` sensor frames across three Windows CSVs: **537** touch,
**247** initialization, **638** boot. It also records per-trace stream hashes,
segment structure and cadence checks. That old test references a missing
`tools/analyze_raw_corpus.py`; its expected counts are a provenance assertion,
**not an independent run of PR #12**.

The original Gate2 ETL `C:\gate2\gate2.etl` (398,721,024 bytes; SHA-256
`4583C62F0A7AC1B2099AA904FF8F61BF1DE065A2A2EF1AB58397950E57906552`)
is described in `docs/GOLDEN-SM.md` with 3,254,430 ETW events and no event loss.
Its full binary is not tracked in the inspected GitHub tree; the compact
`windows-golden.jsonl` is. The Gate2 summaries explicitly do not observe final
software-synthesized multitouch reporting.

## Contradictions resolved by the August MSI report

The MSI report verified the actual `TouchPenProcessor0C19.dll` hash as
`f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`,
version `5.127.137.0`, and `0x0C19` configuration at VA `0x1808E0460`.

1. `config + 0x8C4` is **0.7553579807**, *not* the old `0.754732`.
2. `+0xD40..+0xD78` contains **nonzero structured byte/index data with 0xFF
   sentinels**, *not* a zero-filled `10x11` float Mahalanobis matrix. Its
   exact meaning still needs code-xref recovery.
3. `+0xED0` onward includes three static floats (`0.12`, `0.06`, `0.055`),
   an integer count of **20**, and a 20-pair quadratic lookup where the integer
   is approximately `round(65536*x*x)`. It is *not* an entirely runtime-zero
   regional-sensitivity map.
4. `+0xE20..+0xE48`, `+0xE60..+0xE98`, `+0xEA0..+0xEC0` are statically zero in
   the examined image; the precise runtime producers are **not** proven.
5. Class/status numbers `1`, `3`, `5`, `7` have observed code-path roles;
   the prior table that mapped `0=finger`, `1=palm`, `2=noise`, `3=coalesced`
   was **not substantiated**. Do not use it to decide which candidate is a palm.

See `docs/SL4_MSI_Mining_Report.md`, `docs/decomp/SURFACE_TRACKER_DECOMP.md`,
and the corrected `docs/{CONFIG_TABLE,CONTACT_ABI}.md` on this branch.

## What PR #12 can now do without a new capture

The new **read-only** `userspace/surface-processor/windows_evidence.py` extracts
complete `0x0c` frames directly from the tracked ETW CSVs using
`IoSpbPayloadStart` -> `IoSpbPayloadTdStart/Buffer` -> `IoSpbPayloadStop`.
It only accepts complete 4304-byte V0 bodies with a valid CapImg section tree,
retains per-frame source line, transaction, ETW clock, SHA-256, and a provider
probe, and writes a `frames.txt` that existing `replay.py` can consume. The
optional `--check-known-counts` asserts historical frame totals.

```sh
cd userspace/surface-processor
python3 windows_evidence.py \
  ../../traces/surface_touch.csv \
  ../../traces/surface_init.csv \
  ../../traces/surface_boot_auto.csv \
  --output-dir /tmp/sl4a-windows-corpus --check-known-counts
python3 replay.py /tmp/sl4a-windows-corpus/surface_touch/frames.txt > /tmp/sl4a-windows-touch.jsonl
```

Do **not** add the reconstructed raw frames to GitHub: the original CSV sources
and manifests already establish provenance. Run this against a complete clone
with the CSV files locally available. The large CSVs could not be opened by the chat's GitHub content reader, but
**the repository's GitHub Actions runner checked them out and replayed them
successfully** on October 17, 2026. The extractor's historical count checks
passed: 638+247+537 = **1422** validated frames. The 537-frame touch session
ran 30 baseline and 507 tracking frames. This is still not a processed-contact
oracle. See workflow run 39049773971 for the extraction and replay logs.

## Processed-contact evidence: known search target, not verified present

`tools/windows_capture/README.md` names the
`Microsoft.Surface.TouchAndPen.Prod` TraceLogging provider (GUID
`{3FA102E9-1A62-5490-7AF8-6088C2F9E6BE}`) and fields `TouchBlobCoMX`,
`TouchBlobCoMY`. The profile requests that provider, but a `.wprp` declaration
**is not proof the preserved ETL or CSV contains its events**. The extractor
reports matching provider events if decoded CSV rows carry them; it does not
pretend coordinates are stable Windows HID IDs. A processed-contact benchmark
still requires actual relevant provider events or matching HID/pointer output.

## External historical paths to recover if available

- `~/sl4a-analysis/ghidra-findings/FINDINGS*.md`
- `touchpen0c19_fullheat_20260716/functions/*.c` (including
  `180601690_FUN_180601690.c`, `180606370_FUN_180606370.c`)
- `heatcore_20260716/functions/*.c`
- Original Gate2 `gate2.etl`, `markers.tsv`, and a labelled processed-contact
  capture, if any was made

These full decompilation files are **referenced in GitHub docs but absent from
its tracked tree**. Request them only if they are not accessible in the
working machine's local analysis directories; do not assume they were never
collected.

## October 17 real-corpus raw-region comparison

The dedicated offline test run [39049773971](https://github.com/avgbob/SL4A_TouchScreen/actions/runs/39049773971)
reported 31/31 tests passing; the full CSV corpus extractor and V0 replay also
passed. Across **507 tracking frames**, the sensor-region proxy matched the
prototype's candidate count in **501 frames**, with **6** frames containing
more prototype candidates and **0** containing fewer. The raw-proxy rule is
four-connected CCL of raster byte <135, minimum two pixels and weight >=1000.
The prototype recorded **518 candidates** and **452 emitted research contacts**.
The difference includes birth/lift policy; it cannot be labeled a measured
Windows miss/false-touch rate. Neither independent classifier labels nor final
Windows HID IDs exist in this corpus.

This agreement is *not* evidence that the current detector correctly separates
two physical fingers when their heatmaps form one region; the Windows candidate
classifier and split behavior still need code-level reconstruction.
