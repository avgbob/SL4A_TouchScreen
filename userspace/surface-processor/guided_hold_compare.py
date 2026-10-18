#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Compare reference/experimental contact counts inside conservative holds.

The aggregate output contains no coordinates, pointer IDs, raw clocks or
heatmaps and is suitable for a sanitized research report.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path


def read_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
    if not rows:
        raise ValueError(f'{path}: no JSONL rows')
    frames = [row.get('frame') for row in rows]
    if frames != list(range(len(rows))):
        raise ValueError(f'{path}: frames must be contiguous from zero')
    if any(not isinstance(row.get('contacts'), list) for row in rows):
        raise ValueError(f'{path}: contacts must be arrays')
    return rows


def compare_holds(reference: list[dict], experiment: list[dict]) -> dict:
    if len(reference) != len(experiment):
        raise ValueError('reference/experiment frame coverage mismatch')
    counts: dict[tuple[int, str, int], Counter] = {}
    for expected_frame, (ref, got) in enumerate(zip(reference, experiment)):
        if ref.get('frame') != expected_frame or got.get('frame') != expected_frame:
            raise ValueError('reference/experiment frame sequence mismatch')
        hold = ref.get('guided_hold')
        if not hold or not hold.get('conservative'):
            continue
        key = (int(hold['stage']), str(hold['event']),
               int(hold['physical_contacts']))
        counts.setdefault(key, Counter())[
            (len(ref['contacts']), len(got['contacts']))] += 1
    holds = []
    total = matching = 0
    for (stage, event, physical), histogram in sorted(counts.items()):
        frames = sum(histogram.values())
        exact = sum(value for (ref_count, got_count), value in histogram.items()
                    if ref_count == got_count)
        total += frames
        matching += exact
        holds.append({
            'stage': stage,
            'event': event,
            'physical_contacts': physical,
            'frames': frames,
            'exact_count_frames': exact,
            'count_pairs': {
                f'windows_{ref_count}_prototype_{got_count}': value
                for (ref_count, got_count), value in sorted(histogram.items())
            },
        })
    if not holds:
        raise ValueError('reference contains no conservative guided-hold frames')
    return {
        'status': 'SANITIZED_GUIDED_HOLD_COUNT_COMPARISON',
        'conservative_frames': total,
        'exact_count_frames': matching,
        'exact_count_fraction': round(matching / total, 6),
        'holds': holds,
        'limits': [
            'Count agreement is not coordinate, identity or classifier parity.',
            'Transitions and non-conservative hold edges are excluded.',
            'The reference is OS-visible Windows pointer output.',
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('experiment', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = compare_holds(read_rows(args.reference), read_rows(args.experiment))
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
