#!/usr/bin/env python3
"""Offline audit for immutable SL4A Windows source evidence.

Usage: python3 tools/research_evidence_guard.py [--root DIR]
Does not open hardware, write firmware, load modules or require third-party packages.
Original captured data is checked; it does NOT validate Windows contact IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

RAW_BODY_BYTES = 4304

SOURCES = {
    'traces/surface_touch.csv': 19514888,
    'traces/surface_init.csv': 9055161,
    'traces/surface_boot_auto.csv': 29339823,
    'captures/wintrace/touch_spb_transactions.txt': 6623988,
    'captures/wintrace/mshw0231_report_descriptor.txt': 10607,
    'evidence/windows/gate2/windows-golden.jsonl': 4287,
    'docs/SL4_MSI_Mining_Report.md': 7604,
}

MIRRORS = [
    ('traces/surface_touch.csv', 'captures/wintrace/surface_touch.csv'),
    ('traces/surface_init.csv', 'captures/wintrace/surface_init.csv'),
]

REQUIRED_DOCS = [
    'AGENTS.md',
    'docs/RESEARCH-INDEX.md',
    'docs/RESEARCH-CONTRADICTIONS.md',
    'docs/RESEARCH-SOURCE-MANIFEST.md',
    'docs/RESEARCH-SNAPSHOT-20261017.json',
    'docs/RESEARCH-HISTORICAL-RECOVERY.md',
    'docs/RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json',
    'docs/EVIDENCE.md',
    'docs/CONFIG_TABLE.md',
    'docs/CONTACT_ABI.md',
    'docs/GATE5-QUALIFICATION.md',
    'docs/decomp/SURFACE_TRACKER_DECOMP.md',
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while data := handle.read(1 << 20):
            digest.update(data)
    return digest.hexdigest()


def audit(root: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    notes: list[str] = []
    for name in REQUIRED_DOCS:
        if not (root / name).is_file():
            errors.append(f'MISSING_REQUIRED_DOC: {name}')
    for name, length in SOURCES.items():
        path = root / name
        if not path.is_file():
            errors.append(f'MISSING_SOURCE: {name}')
        elif path.stat().st_size != length:
            errors.append(f'CHANGED_SOURCE_SIZE: {name}: {path.stat().st_size} != {length}')
    duplicate_ok: dict[str, bool] = {}
    for first, second in MIRRORS:
        if not (root / first).exists() or not (root / second).exists():
            duplicate_ok[first] = False
            errors.append(f'MISSING_MIRROR: {first} or {second}')
        else:
            identical = sha256(root / first) == sha256(root / second)
            duplicate_ok[first] = identical
            if not identical:
                errors.append(f'MIRROR_MISMATCH: {first}, {second}')
    snapshots = []
    for i in range(8):
        p = root / f'captures/id5-20260718/frames/raw-slot-{i}.v0'
        if not p.is_file() or p.stat().st_size != RAW_BODY_BYTES:
            errors.append(f'MISSING_OR_INVALID_V0_FIXTURE: {p.relative_to(root)}')
        else:
            snapshots.append(p.name)
    p = root / 'evidence/windows/gate2/windows-golden.jsonl'
    gate2 = []
    if p.is_file():
        try:
            gate2 = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
            if not gate2 or not all(isinstance(x, dict) and x.get('src') == 'etl_compact' for x in gate2):
                errors.append('GATE2_COMPACT_JSONL_NOT_EXPECTED_SCHEMA')
        except (ValueError, UnicodeError):
            errors.append('GATE2_COMPACT_JSONL_PARSE_FAILED')
    if (root / 'tools/analyze_raw_corpus.py').is_file():
        legacy = 'RESTORED_CI_STRICT_HASH_CADENCE_TEST_REQUIRED'
    else:
        legacy = 'MISSING_OLD_CORPUS_ANALYZER_OLD_TEST_SILENTLY_SKIPS'
        errors.append('RESTORED_ANALYZER_MISSING: old corpus test would silently SKIP; failure is mandatory')
        notes.append('D13 regression: tools/analyze_raw_corpus.py was recovered from Git history, do not allow it to disappear again')
    manifest = root / 'docs/RESEARCH-SNAPSHOT-20261017.json'
    entries = 0
    if manifest.is_file():
        try:
            snap = json.loads(manifest.read_text())
            entries = len(snap['tracked_blobs'])
            if entries != 352 or snap['source_head'] != 'c081075492feae4146510cf0d364b23fd0a394eb':
                errors.append('SNAPSHOT_BASELINE_NOT_EXPECTED')
        except (ValueError, KeyError, TypeError):
            errors.append('SNAPSHOT_JSON_INVALID')
    historic_index = root / 'docs/RESEARCH-HISTORICAL-DECOMP-INDEX-20260716.json'
    recovered_functions = 0
    if historic_index.is_file():
        try:
            history = json.loads(historic_index.read_text())
            recovered_functions = history['historical_counts']['source_files']
            if recovered_functions != 468 or history['source_historical_commit'] != 'c94c399618b23588c95711ab4449d9400036ffd0':
                errors.append('HISTORICAL_468_FUNCTION_INDEX_INVALID')
        except (ValueError, KeyError, TypeError):
            errors.append('HISTORICAL_INDEX_JSON_PARSE_FAILED')
    result = {
        'scope': 'original git tracked evidence only; not processed Windows HID truth',
        'ok': not errors,
        'source_sizes_checked': len(SOURCES),
        'exact_csv_mirrors': duplicate_ok,
        'v0_fixture_count': len(snapshots),
        'gate2_compact_rows': len(gate2),
        'original_tracked_blob_manifest_rows': entries,
        'historical_decompiled_function_count': recovered_functions,
        'legacy_corpus_contract': legacy,
        'notes': notes,
        'errors': errors,
    }
    return result, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    report, errors = audit(args.root)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
