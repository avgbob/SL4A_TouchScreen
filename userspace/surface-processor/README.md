# MSHW0231 Windows-derived contact processor (offline research)

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
python3 -m unittest -v test_processor
python3 replay.py /path/to/sl4a-heat/heat-captures > contacts.jsonl
python3 replay.py /path/to/real-frames.txt --association-scale 1 > contacts.jsonl
```

Inputs: a directory of numbered `heat-*.bin` HID reports, a single binary V0
report, a one-hex-frame-per-line SPB capture (optional leading 5 `ff` bytes),
or an isolated 3456-byte raster.  Each frame is validated using the same V0
section constraints as `driver/spi-hid-capimg.c`. Outputs are JSON Lines with
contact records, candidate coordinates, age, and mutable coalescing groups.

The first 30 frames establish a baseline; captures beginning mid-touch may not
provide a usable baseline. The `--absolute-gate` and `--association-scale`
arguments support controlled A/B comparisons, not claims of Windows parity.

## Provenance/uncertainty inventory

| Stage | Source | Fidelity claim |
|---|---|---|
| `0x0c` V0 section parser | `driver/spi-hid-capimg.c` | Structural validation of known frames |
| 72x48 grid, `c590`, 30-frame baseline | Decomp/config and Windows alignment docs | LUT/geometry verified; runtime baseline update partly Linux heuristic |
| 0.1 cell threshold | `docs/WINDOWS-ALIGNMENT.md` | Value recovered; use in candidate mask is provisional |
| 4-connected candidate extraction | Fork raw pipeline | Linux approximation, NOT Windows detector/classifier |
| Hungarian solver and radius tables | `docs/decomp/SURFACE_TRACKER_DECOMP.md`; `docs/CONFIG_TABLE.md` | Solver strategy and DLL constants; unknown Windows cost details |
| Ten-history samples, gap >5 reset | Surface tracker decomp | Recovered structure and release behavior |
| 3-frame birth / optional hold | Current Linux defaults | *Experimental* semantics; Windows hold quality gate not implemented |
| Merge-group/status-7 annotations | `FUN_1806025c0` and `tools/surface_tracker_oracle.py` | Recovered local behavior only; no final HID contact semantics |
| Finger validity, Mahalanobis classifier, gain adaptation | Windows DLL/runtime calibration | NOT implemented |
| Windows virtual HID tracking-ID mapping | Windows HeatCore | Unknown; local IDs must not be treated as Windows IDs |

**Important:** A Windows group annotation does **not** decide whether a finger is
published to the OS. This offline tool deliberately retains both grouped records
instead of guessing which should be emitted. It does not solve close-finger
behavior yet; it creates a reproducible platform for that work.

## Tests and next gates

- Python unit tests cover V0/numbered/SPB formats, invalid sections, baseline,
  two contacts, optimal assignment, strict merge threshold, stable IDs,
  discontinuity, lift/debounce, and malformed input.
- Next: run the retained **537 raw frames**, compare against the existing Linux
  tracker, and collect aligned **Windows processed contact output** for ground
  truth. Raw capacitive cells alone are insufficient to prove equivalent IDs.
- Next: recover/implement `FUN_180601690` classification and
  `FUN_180606370` hold/lift using evidence; add frame-aligned golden tests.
- Next: choose a bounded opt-in CapImg export path under #87; only after offline
  qualification, consider uinput adapter vs in-kernel processor.

See `linux-surface/iptsd`'s `src/contacts/finder.hpp`, `src/contacts/tracking/tracker.hpp`
and mainline `drivers/input/input-mt.c` for architectural comparisons.

## Windows contact reference comparison

When Windows *processed* contacts are captured and converted to JSONL using the
same frame sequence and coordinate system, compare them with:

```sh
python3 compare.py windows-contacts.jsonl contacts.jsonl > discrepancy.json
```

Each line in both inputs must have `{"frame": N, "contacts": [{"id": 1,
"x": 10.2, "y": 20.4}]}`. Coordinates default to 72×48 sensor grid units.
Use `--reference-scale-x` and `--reference-scale-y` for known coordinate
conversions; do not guess. The comparator reports misses, false contacts,
coordinate error, and consecutive-frame ID switches. **This is a measurement
interface; it does not itself capture or infer Windows touch output.**
