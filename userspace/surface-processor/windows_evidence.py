#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Extract Windows V0 CapImg SPB bodies from the existing ETW CSV evidence.

Read-only source inspection, no Windows/device access. Do not treat these raw
frames as ground-truth Windows processed contacts. This intentionally depends on
the research processor's strict decoder rather than a magic substring alone.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from processor import decode_frame

BODYSIZE = 4304
PAD = b'\xff' * 5
PATTERN = re.compile(r'0[xX]([0-9a-fA-F]+)')
KNOWN_COUNTS = {'surface_touch.csv': 537, 'surface_init.csv': 247,
                'surface_boot_auto.csv': 638}


@dataclass
class Transfer:
    direction: str
    payloads: list[bytes] = field(default_factory=list)


@dataclass
class Transaction:
    activity: str
    clock: str
    transfers: list[Transfer] = field(default_factory=list)
    malformed: int = 0


def _payload(row: list[str]) -> bytes | None:
    """Keep all bytes in the ETW TdBuffer hex field, never infer direction."""
    if len(row) <= 21:
        return None
    m = PATTERN.search(row[21].strip())
    if not m or len(m.group(1)) % 2:
        return None
    try:
        return bytes.fromhex(m.group(1))
    except ValueError:
        return None


def _v0_body(rx: bytes) -> bytes | None:
    if len(rx) == BODYSIZE and rx[:3] == b'\xce\x10\x0c':
        return rx
    if len(rx) == BODYSIZE + 5 and rx.startswith(PAD) and rx[5:8] == b'\xce\x10\x0c':
        return rx[5:]
    return None


def extract(path: Path) -> tuple[list[dict], dict]:
    """Rebuild complete SPB transaction boundaries, retain file-order frames."""
    rows = Counter()
    txns: dict[str, Transaction] = {}
    entries: list[dict] = []
    errors = Counter()
    processed_probe = Counter()
    tx_index = 0
    with path.open('r', encoding='latin-1', newline='') as f:
        for line_no, row in enumerate(csv.reader(f), 1):
            if len(row) < 19:
                continue
            provider, event = row[0].strip(), row[1].strip()
            if not provider or provider == 'Event Name':
                continue
            rows[provider] += 1
            # TraceLogging provider fields would be required to reconstruct
            # processed contacts. This probes their presence, not just SPB.
            if 'TouchAndPen' in provider or 'TouchBlobCoM' in ','.join(row):
                processed_probe[provider + ':' + event] += 1
            if 'SPB-ClassExtension' not in provider:
                continue
            activity = row[14].strip() or '<no activity>'
            if event == 'IoSpbPayloadStart':
                if activity in txns:
                    errors['overlapped_or_incomplete_transaction'] += 1
                txns[activity] = Transaction(activity, row[16].strip())
            elif event == 'IoSpbPayloadTdStart' and activity in txns:
                direction = row[20].strip().strip('"').strip() if len(row) > 20 else ''
                txns[activity].transfers.append(Transfer(direction))
            elif event == 'IoSpbPayloadTdBuffer' and activity in txns:
                t = txns[activity]
                if not t.transfers:
                    t.malformed += 1
                    continue
                data = _payload(row)
                if data is None:
                    t.malformed += 1
                    continue
                t.transfers[-1].payloads.append(data)
            elif event == 'IoSpbPayloadStop' and activity in txns:
                t = txns.pop(activity)
                tx_index += 1
                if t.malformed:
                    errors['malformed_transfer'] += 1
                    continue
                rx = b''.join(b''.join(z.payloads) for z in t.transfers
                              if z.direction.startswith('FromDevice'))
                body = _v0_body(rx)
                if body is None:
                    continue
                try:
                    raster = decode_frame(body)
                except (ValueError, IndexError):
                    errors['invalid_capimg_body'] += 1
                    continue
                entries.append({'index': len(entries), 'spb_transaction': tx_index,
                                'source_line': line_no, 'activity': t.activity,
                                'clock_100ns': t.clock,
                                'body_sha256': hashlib.sha256(body).hexdigest(),
                                'raster_sha256': hashlib.sha256(raster).hexdigest(),
                                '_body': body})
    if txns:
        errors['unfinished_transactions'] += len(txns)
    report = {
        'source': path.name,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'format': 'Windows ETW/tracerpt CSV SPB IoSpbPayloadTdBuffer',
        'decoded_capimg_frames': len(entries),
        'known_historical_frame_count': KNOWN_COUNTS.get(path.name),
        'matches_historical_count': (len(entries) == KNOWN_COUNTS[path.name]
                                     if path.name in KNOWN_COUNTS else None),
        'transactions_completed': tx_index,
        'provider_events': dict(rows),
        'processed_touch_provider_probe': dict(processed_probe),
        'errors': dict(errors),
        'warning': ('CapImg heatmaps are sensor inputs, not Windows processed '
                    'contact records or Microsoft contact IDs.'),
    }
    return entries, report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv', nargs='+', type=Path, help='Windows ETW CSV traces')
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--check-known-counts', action='store_true',
                   help='fail if known 638/247/537 Windows trace frame totals differ')
    args = p.parse_args(argv)
    if len({x.name for x in args.csv}) != len(args.csv):
        p.error('duplicate source basenames: output directories would collide')
    output = []
    mismatch = False
    for path in args.csv:
        records, report = extract(path)
        if report['matches_historical_count'] is False:
            mismatch = True
        folder = args.output_dir / path.stem
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'frames.txt').write_text(''.join(x['_body'].hex() + '\n' for x in records),
                                           encoding='ascii')
        manifest = dict(report)
        manifest['frames'] = [{k: v for k, v in x.items() if k != '_body'} for x in records]
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n',
                                              encoding='utf-8')
        output.append({k: v for k, v in report.items() if k != 'provider_events'})
    print(json.dumps({'traces': output}, indent=2, sort_keys=True))
    return 1 if args.check_known_counts and mismatch else 0


if __name__ == '__main__':
    raise SystemExit(main())
