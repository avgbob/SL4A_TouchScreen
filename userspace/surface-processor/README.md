# MSHW0231 Windows-derived contact processor (offline research)

> **Guided V4 result (2026-10-17):** [The 17,018-frame physical-truth replay](PHYSICAL-TRUTH-V4-RESULTS-20261017.md) directly aligns raw and pointer QPC clocks and falsifies the V3 two-field morphology release rule.  During a deliberate lift, the surviving one-finger region became stronger/larger rather than collapsing; the diagnostic shadow remained active through the entire hold and would have ghosted had it been emitted.  Conversely, Windows maintained or eventually created two pointers in several holds where the threshold proxy still had one region.  Shadow state remains internal-only, with no ID reuse or contact emission; no Gate5 or kernel change is authorized.

> **Frame-aligned pointer oracle:** `windows_pointer_oracle.py` now converts the
> private V4 run into one OS-visible Windows contact snapshot per raw frame. It
> verifies the original pointer CSV hash, monotonic clocks, 17,018 raw frames,
> balanced 14 DOWN / 14 UP lifetimes, and all 19 guided holds.
> `v4_oracle_contract.py` locks the close-contact, genuine-lift and returned-
> finger counterexamples. The generated JSONL remains private because it
> contains touch coordinates and timing; it is not internal HeatCore truth.

> **Newest research gate (2026-10-17):** [V3 physical-truth and post-coalescing replay](PHYSICAL-TRUTH-V3-RESULTS-20261017.md). The controlled V3 lift produces a sharp morphology collapse, but the same normalized rule falsely retires a shadow before one of the older corpus's three physical-two markers. Recovery hysteresis now rejects one-frame split flicker, yet morphology is still diagnostic-only: it emits no contact and reuses no identity by default. Use `python3 physical_truth_shadow_replay.py /path/to/correlated-run --output /tmp/shadow-physical-truth.json` for the private-run replay or `python3 shadow_replay.py /path/to/SL4A_heatmaps_privacy_hardened.zip --output /tmp/shadow-audit.json` for the published 8,232-frame sweep; no Gate5 or upstream driver change.


> **Latest empirical next gate:** [Pre-loss sensor-region collapse and independent-lift control audit](PINCH-TRANSITION-AUDIT-20261017.md). Four clear Windows contact transitions anchor only a **behavioral** estimate of sensor/event time offset. Across four close-pinch secondary `UP` events, distinct raw regions collapsed **0.43–1.45 seconds before** Windows released the corresponding pointer by that estimate. Three subsequent M markers independently confirm two physical fingers at later points. Even a peak threshold of 2 recovers no second 4-cell-separated lobe in the sampled failure windows. **No hold timer or synthetic second contact has been implemented**.

**Reproduce pre-loss audit (Python stdlib, public dataset only):**
```bash
python3 pinch_transition_audit.py /path/to/SL4A_heatmaps_privacy_hardened.zip --output /tmp/pinch-transition.json
python3 -m unittest discover -p 'test_*.py' -v
```


**Status: prototype, not a Windows-equivalent driver.** The default Linux driver,
Gate5 transport, and #87 remain unchanged. This directory cannot open `/dev/hidraw`,
issue GET6/SET5, emit `uinput` events, or modify a running machine.

## Why this exists

The earlier tracker merged proximity candidates before or after Hungarian matching
and accumulated unverified close-birth/occlusion heuristics. This prototype
separates **transport/decoder**, **signal+candidate detection**, **association
and persistent contact history**, **report grouping**, and **future Linux output**.
It is inspired by the architecture of `linux-surface/iptsd` and by Linux's input-MT
API, while using verified `TouchPenProcessor0C19.dll` facts wherever available.

## Run

Python 3.10+ and its standard library only:

```sh
cd userspace/surface-processor
python3 -m unittest discover -p 'test_*.py' -v
python3 replay.py /path/to/sl4a-heat/heat-captures > contacts.jsonl
python3 replay.py /path/to/real-frames.txt --association-scale 1 > contacts.jsonl
```

For a private guided V4 correlated run:

```sh
python3 windows_pointer_oracle.py /path/to/V4-run \
  --output /tmp/windows-pointer-oracle.jsonl \
  --summary /tmp/windows-pointer-oracle-summary.json
python3 v4_oracle_contract.py /tmp/windows-pointer-oracle-summary.json
python3 calibrate_pointer_oracle.py /path/to/V4-run \
  /tmp/windows-pointer-oracle.jsonl \
  --output /tmp/pointer-sensor-calibration.json
python3 replay.py /path/to/V4-run/offline-analysis/capimg-frames.hex \
  > /tmp/prototype.jsonl
python3 compare.py /tmp/windows-pointer-oracle.jsonl /tmp/prototype.jsonl \
  --reference-affine-json /tmp/pointer-sensor-calibration.json \
  > /tmp/prototype-vs-windows.json
python3 guided_hold_compare.py /tmp/windows-pointer-oracle.jsonl \
  /tmp/prototype.jsonl --output /tmp/guided-counts.json
```

The oracle keeps coordinates in Windows screen pixels. A later comparison may
apply the measured proxy transform; the oracle generator itself does not guess
one. The calibration target is explicitly a threshold-region centroid proxy,
not a recovered Windows classifier coordinate.

Inputs: a directory of numbered `heat-*.bin` HID reports, a single binary V0
report, a one-hex-frame-per-line SPB capture (optional leading 5 `ff` bytes),
or an isolated 3456-byte raster. `.v0` and `.raw` are also accepted as binary.  Each frame is validated using the same V0
section constraints as `driver/spi-hid-capimg.c`. Outputs are JSON Lines with
contact records, candidate coordinates, age, and mutable coalescing groups.

The first 30 frames establish a baseline; captures beginning mid-touch may not
provide a usable baseline. The `--absolute-gate` and `--association-scale`
arguments support controlled A/B comparisons, not claims of Windows parity.
Newly detected contacts have **unknown Windows class and merge group** (`null`),
not assumed status 1. The recovered coalescer is only applied if verified class
and group labels are explicitly provided. `--hold-frames` retains internal
tracks but does not emulate Windows' HID hold/lift emissions.

## Provenance/uncertainty inventory

| Stage | Source | Fidelity claim |
|---|---|---|
| `0x0c` V0 section parser | `driver/spi-hid-capimg.c` | Structural validation of known frames |
| 72x48 grid, `c590`, 30-frame baseline | Decomp/config and Windows alignment docs | LUT/geometry verified; runtime baseline update partly Linux heuristic |
| 0.1 cell threshold | `docs/WINDOWS-ALIGNMENT.md` | Value recovered; use in candidate mask is provisional |
| 4-connected candidate extraction | Fork raw pipeline | Linux approximation, NOT Windows detector/classifier |
| Hungarian solver and radius tables | `docs/decomp/SURFACE_TRACKER_DECOMP.md`; `docs/CONFIG_TABLE.md` | Solver strategy and DLL constants; unknown Windows cost details |
| Ten-history samples, gap >5 reset | Surface tracker decomp | Recovered structure and release behavior |
| 3-frame birth / internal retention | Current Linux defaults | *Experimental* semantics; Windows hold quality gate not implemented |
| Merge-group/status-7 annotations | `FUN_1806025c0` and `tools/surface_tracker_oracle.py` | Recovered local behavior only; no final HID contact semantics |
| Windows candidate score and transition gates | `FUN_180601690`, `FUN_180607050`, `FUN_1806071c0` plus initializer/xrefs | Ten-field/four-block arithmetic, corrected config pointer, numeric argmax and current/history gates implemented and unit-tested; overrides, outer policy and class meanings remain unavailable |
| Windows class semantics and gain adaptation | DLL decomp + August MSI correction | NOT implemented |
| Windows virtual HID tracking-ID mapping | Windows HeatCore | Unknown; local IDs must not be treated as Windows IDs |

**Important:** A Windows group annotation does **not** decide whether a finger is
published to the OS. This offline tool deliberately retains both grouped records
instead of guessing which should be emitted. It does not solve close-finger
behavior yet; it creates a reproducible platform for that work.

## Tests and next gates

- Python unit tests cover V0/numbered/SPB formats, invalid sections, baseline,
  two contacts, optimal assignment, strict merge threshold, stable IDs,
  discontinuity, lift/debounce, and malformed input.
- The retained **537 raw frames** have been replayed. V4 now supplies
  frame-aligned OS-visible Windows pointer output, but not HeatCore internal
  classes, groups, or pre-publication IDs. Use it for count, lifetime,
  birth/lift and eventual coordinate comparisons; do not relabel it as
  internal Microsoft state.
- Next: type the candidate score overrides, finish the outer
  `FUN_1806067d0` class-selection policy and later correction path, then
  reconstruct hold/lift and add frame-aligned golden tests. The parameterized
  score and transition gates are in `windows_classifier.py` and
  `windows_class_transition.py`; neither is wired to emission or supplied with
  bundled proprietary defaults.
- Next: choose a bounded opt-in CapImg export path under #87; only after offline
  qualification, consider uinput adapter vs in-kernel processor.

See `linux-surface/iptsd`'s `src/contacts/finder.hpp`, `src/contacts/tracking/tracker.hpp`
and mainline `drivers/input/input-mt.c` for architectural comparisons.

## Windows contact reference comparison

When Windows *processed* contacts are captured and converted to JSONL using the
same frame sequence and coordinate system, compare them with:

```sh
python3 compare.py windows-contacts.jsonl contacts.jsonl > discrepancy.json
# If capture windows intentionally differ:
python3 compare.py --allow-partial windows-contacts.jsonl contacts.jsonl > partial.json
```

Each line in both inputs must have `{"frame": N, "contacts": [{"id": 1,
"x": 10.2, "y": 20.4}]}`. Coordinates default to 72×48 sensor grid units.
Use `--reference-scale-x` and `--reference-scale-y` for known coordinate
conversions; do not guess. The comparator reports misses, false contacts,
coordinate error, and consecutive-frame ID switches. **This is a measurement
interface; it does not itself capture or infer Windows touch output.**

## Audit

See [AUDIT.md](AUDIT.md) for corrected bugs and unresolved release gates.
The new comparator **requires complete frame coverage** by default; incomplete
windows need explicit `--allow-partial`. A synthetic pass alone does not prove
correct close-finger operation or Windows output equivalence.

## Reusing the preserved Windows ETW data

The tracked repository already includes three sizeable Windows SPB CSV exports.
Rather than request new raw captures, use the offline extractor to rebuild
replay input **from these preserved sources**:

```sh
python3 windows_evidence.py ../../traces/surface_touch.csv \
  ../../traces/surface_init.csv ../../traces/surface_boot_auto.csv \
  --output-dir /tmp/sl4a-windows-corpus --check-known-counts
python3 replay.py /tmp/sl4a-windows-corpus/surface_touch/frames.txt > /tmp/sl4a-processed.jsonl
```

See [WINDOWS-EVIDENCE-INVENTORY.md](WINDOWS-EVIDENCE-INVENTORY.md). The
July CSVs represent a historical 537+247+638 = **1422 raw frame corpus**;
these numbers come from the existing source test ledger and still need to
be reverified by executing extraction against the full CSV sources. They
are **not processed Windows contacts**. The August MSI report corrects an
important old assumption: `+0xD40..+0xD78` is structured nonfloat byte
data, *not* the hypothesized zero 10x11 Mahalanobis matrix.

### First real-corpus CI result (October 17, 2026)

GitHub Actions passed exact counts **638 boot + 247 initialization + 537 touch = 1422 complete V0 frames**. The 537-frame touch replay produced 30 calibration frames and 507 tracking frames. The independent byte<135 *raw-region proxy* agreed with the prototype's candidate count on 501/507 tracking frames; six had more prototype candidates, none fewer. Aggregate: 518 prototype candidates, 452 emitted prototype contact records. This is **not** Windows HID ID/coordinate equivalence; one connected sensor region can contain two fingers. See the research workflow and WINDOWS-EVIDENCE-INVENTORY.md.
