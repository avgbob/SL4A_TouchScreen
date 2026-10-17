#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Build a small upload ZIP from a completed Windows V2 + WPR experiment.

Runs entirely on the Windows machine; does NOT upload to any service.
Excludes 200+ MB source ETL and 600+ MB tracerpt CSV from the ZIP.
Includes decoded heatmap frames ONLY if V0 0x0C decoder validates them.
Preserve originals, and never publish the resulting ZIP to public GitHub.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from analyze_correlated_pinch import verify_wpr_csv, verify_pointer_events


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(4 << 20), b""):
            digest.update(b)
    return digest.hexdigest()


def collect(folder: Path, *, skip_wpr: bool = False) -> dict:
    folder = folder.resolve()
    manifest = folder / "manifest.json"
    pointer = folder / "pointer" / "events.csv"
    samples = folder / "pointer" / "samples.csv"
    summary = folder / "pointer" / "SUMMARY.txt"
    wpr_csv = folder / "pinch-runtime.csv"
    if not manifest.is_file() or not pointer.is_file():
        raise FileNotFoundError("Need completed capture folder containing manifest.json and pointer/events.csv")
    meta = json.loads(manifest.read_text(encoding="utf-8-sig"))
    expected = {item["file"].replace("\\", "/"): item for item in meta["files"]}
    if "pointer/events.csv" not in expected:
        raise ValueError("Original manifest is missing pointer/events.csv")
    result_dir = folder / "offline-analysis"
    result_dir.mkdir(exist_ok=True)
    print("Inspecting pointer IDs and M key annotations ...", flush=True)
    pointer_report = verify_pointer_events(pointer)
    report = {"pointer": pointer_report,
              "manifest_created_utc": meta.get("generated_utc"),
              "tool": "SL4A correlated trace offline bundle extractor",
              "clock_warning": "Do not convert tracerpt Clock-Time QPC to UTC without an explicit verified mapping"}
    if pointer_report["sha256"].lower() != expected["pointer/events.csv"]["sha256"].lower():
        raise ValueError("Pointer events differ from original manifest; refusing untraceable evidence")
    if not skip_wpr and wpr_csv.is_file():
        print("Streaming large tracerpt CSV to reconstruct and strictly decode V0 0x0C frames ...", flush=True)
        wpr_report = verify_wpr_csv(wpr_csv, result_dir)
        report["wpr"] = wpr_report
        original = expected.get("pinch-runtime.csv")
        if original and wpr_report["source_sha256"].lower() != original["sha256"].lower():
            raise ValueError("WPR CSV differs from original manifest; refusing untraceable evidence")
        report["status"] = ("RAW_FRAMES_VERIFIED_UNALIGNED"
                            if wpr_report["raw_heatmaps_verified"]
                            else "RAW_FRAMES_NOT_RECOVERED")
    elif skip_wpr:
        report["status"] = "WPR_INTENTIONALLY_SKIPPED"
    else:
        report["status"] = "WPR_CSV_NOT_SUPPLIED"
    report["input_integrity"] = {"pointer_csv": "sha256 matches original manifest",
                                 "wpr_csv": ("sha256 matches original manifest"
                                             if "wpr" in report and "pinch-runtime.csv" in expected
                                             else "not_checked")}
    for name, file in (("pointer/samples.csv", samples), ("pointer/SUMMARY.txt", summary)):
        if file.is_file() and name in expected and sha256_file(file).lower() != expected[name]["sha256"].lower():
            raise ValueError(f"{name}: hash differs from original manifest")
    result_path = result_dir / "coverage-report.json"
    result_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    archive = result_dir / "SL4A-correlated-evidence.zip"
    include = [
        manifest, folder/"coordinator-markers.tsv",
        folder/"capture-profile.wprp",
        folder/"pointer-process.log", folder/"wpr-start.log",
        folder/"wpr-stop.log", folder/"tracerpt.log",
        pointer, samples, summary, result_path,
    ]
    if (result_dir/"capimg-frames.hex").exists():
        include.append(result_dir/"capimg-frames.hex")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as z:
        for file in include:
            if file.is_file():
                z.write(file, str(file.relative_to(folder)).replace("\\", "/"))
    return {
        "status": report["status"],
        "bundle": str(archive),
        "bundle_bytes": archive.stat().st_size,
        "raw_heatmaps_verified": report.get("wpr", {}).get("raw_heatmaps_verified", False),
        "decoded_0c_frames": report.get("wpr", {}).get("decoded_complete_0c_frames", 0),
        "pointer_events": sum(pointer_report["event_counts"].values()),
        "physical_two_keypresses": len(pointer_report["raw_m_presses"]),
        "physical_two_with_one_os_pointer": len(pointer_report["raw_one_pointer_m_presses"]),
        "warnings": [
            "Raw M presses may include mistakes; user should identify any accidental M.",
            "Even verified raw 0x0C frames require a proper WPR-to-UTC timestamp mapping.",
            "Never publish raw touch events/heatmaps to a public repository.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--skip-wpr", action="store_true",
                   help="Build pointer-only ZIP; only when full WPR export unavailable")
    a = p.parse_args(argv)
    result = collect(a.run_dir, skip_wpr=a.skip_wpr)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
