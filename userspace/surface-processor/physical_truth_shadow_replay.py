#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Replay the diagnostic shadow gate against a private correlated run.

The script emits aggregate diagnostics only.  It does not copy heatmaps,
pointer coordinates, UTC timestamps, or boot-relative clock values into its
JSON output, and it never creates a visible contact from shadow state.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
import json
from math import hypot, sqrt
from pathlib import Path

from processor import CELLS, COLS, ROWS, Candidate, Config, Tracker, decode_frame
from shadow_tracker import RegionMorphology, ShadowConfig, ShadowOverlay


GUIDED_CONFIRM_PREFIX = 'OPERATOR_CONFIRM_'
GUIDED_HOLD_COMPLETE = 'GUIDED_HOLD_COMPLETE'
GUIDED_GUARD_AFTER_TICKS = 3_500_000
GUIDED_GUARD_BEFORE_TICKS = 1_500_000
MAX_MARKER_FRAME_DELTA_TICKS = 1_000_000


@dataclass(frozen=True)
class RawRegion:
    candidate: Candidate
    cells: tuple[int, ...]
    weights: tuple[int, ...]


def regions(raster: bytes, threshold: int = 150) -> list[RawRegion]:
    """Return bounded four-connected dark regions at the V3 audit threshold."""
    if len(raster) != CELLS or not 1 <= threshold <= 255:
        raise ValueError('invalid raster or threshold')
    seen = bytearray(CELLS)
    result = []
    for start, value in enumerate(raster):
        if seen[start] or value >= threshold:
            continue
        seen[start] = 1
        queue = [start]
        cells = []
        for cell in queue:
            cells.append(cell)
            x, y = cell % COLS, cell // COLS
            for nxt in (cell - 1 if x else -1,
                        cell + 1 if x + 1 < COLS else -1,
                        cell - COLS if y else -1,
                        cell + COLS if y + 1 < ROWS else -1):
                if nxt >= 0 and not seen[nxt] and raster[nxt] < threshold:
                    seen[nxt] = 1
                    queue.append(nxt)
        if len(cells) < 2:
            continue
        weights = [threshold - raster[cell] for cell in cells]
        mass = sum(weights)
        x = sum((cell % COLS) * weight for cell, weight in zip(cells, weights)) / mass
        y = sum((cell // COLS) * weight for cell, weight in zip(cells, weights)) / mass
        result.append(RawRegion(Candidate(x, y, mass, len(cells), max(weights)),
                                tuple(cells), tuple(weights)))
    return sorted(result, key=lambda region: -region.candidate.weight)


def combine(parts: list[RawRegion]) -> tuple[Candidate, RegionMorphology]:
    cells = tuple(cell for part in parts for cell in part.cells)
    weights = tuple(weight for part in parts for weight in part.weights)
    mass = sum(weights)
    x = sum((cell % COLS) * weight for cell, weight in zip(cells, weights)) / mass
    y = sum((cell // COLS) * weight for cell, weight in zip(cells, weights)) / mass
    xx = sum(weight * ((cell % COLS) - x) ** 2
             for cell, weight in zip(cells, weights)) / mass
    yy = sum(weight * ((cell // COLS) - y) ** 2
             for cell, weight in zip(cells, weights)) / mass
    xy = sum(weight * ((cell % COLS) - x) * ((cell // COLS) - y)
             for cell, weight in zip(cells, weights)) / mass
    major = (xx + yy + sqrt((xx - yy) ** 2 + 4 * xy * xy)) / 2
    return (Candidate(x, y, mass, len(cells), max(weights)),
            RegionMorphology(mass, major))


def load_run(run_dir: Path):
    offline = run_dir / 'offline-analysis'
    coverage = json.loads((offline / 'coverage-report.json').read_text(encoding='utf-8'))
    frame_meta = coverage['wpr']['frames']
    frames = [bytes.fromhex(line.strip()) for line in
              (offline / 'capimg-frames.hex').read_text(encoding='ascii').splitlines()
              if line.strip()]
    ticks = [int(item['clock_100ns_raw']) for item in frame_meta]
    if len(frames) != len(ticks) or not frames:
        raise ValueError('frame/clock coverage mismatch')
    with (run_dir / 'pointer' / 'events.csv').open(encoding='utf-8-sig', newline='') as stream:
        pointer = list(csv.DictReader(stream))
    return frames, ticks, pointer


def marker_summary(pointer: list[dict], ticks: list[int],
                   frame_results: list[tuple[int, int]]) -> list[dict]:
    legacy = {'PHYSICAL_TWO_MARK', 'OPERATOR_SECOND_INTENTIONALLY_LIFTED',
              'OPERATOR_SECOND_RETURNED'}
    markers = []
    for row in pointer:
        event = row.get('Event', '')
        if event not in legacy and not event.startswith(GUIDED_CONFIRM_PREFIX):
            continue
        target = int(row['StopwatchTicks'])
        index = min(range(len(ticks)), key=lambda i: abs(ticks[i] - target))
        delta = ticks[index] - target
        item = {'event': event, 'stage': int(row['Stage']),
                'operator_physical': int(row.get('OperatorPhysical', '-1')),
                'windows_at_marker': int(row.get('MessageActive', '-1'))}
        if abs(delta) <= MAX_MARKER_FRAME_DELTA_TICKS:
            visible_count, shadow_count = frame_results[index]
            item.update({'nearest_raw_frame': index,
                         'nearest_delta_ms': round(delta / 1e4, 3),
                         'visible_count': visible_count,
                         'shadow_active': bool(shadow_count)})
        else:
            item.update({'nearest_raw_frame': None, 'nearest_delta_ms': None,
                         'visible_count': None, 'shadow_active': False})
        markers.append(item)
    return markers


def guided_hold_summary(pointer: list[dict], ticks: list[int],
                        frame_results: list[tuple[int, int]]) -> list[dict]:
    pending: dict[int, dict] = {}
    holds = []
    for row in pointer:
        event = row.get('Event', '')
        stage = int(row.get('Stage', '-1'))
        if event.startswith(GUIDED_CONFIRM_PREFIX):
            pending[stage] = row
        elif event == GUIDED_HOLD_COMPLETE and stage in pending:
            start = int(pending[stage]['StopwatchTicks']) + GUIDED_GUARD_AFTER_TICKS
            end = int(row['StopwatchTicks']) - GUIDED_GUARD_BEFORE_TICKS
            indices = [i for i, tick in enumerate(ticks) if start <= tick < end]
            visible = Counter(frame_results[i][0] for i in indices)
            shadow = Counter(frame_results[i][1] for i in indices)
            confirm = pending.pop(stage)
            holds.append({
                'stage': stage,
                'event': confirm['Event'],
                'operator_physical': int(confirm.get('OperatorPhysical', '-1')),
                'raw_frames': len(indices),
                'prototype_visible_histogram': dict(sorted(visible.items())),
                'internal_shadow_histogram': dict(sorted(shadow.items())),
            })
    return holds


def replay(run_dir: Path, coalesce_distance: float = 6.0) -> dict:
    frames, ticks, pointer = load_run(run_dir)
    tracker = Tracker(Config(birth_frames=1, association_scale=10, hold_frames=0))
    overlay = ShadowOverlay(ShadowConfig(ttl_seconds=30, max_merge_distance=12,
                                         gap_reset_seconds=.2, recovery_frames=3))
    visible_histogram = Counter()
    shadow_histogram = Counter()
    frame_results = []
    events = []
    for index, (raw, tick) in enumerate(zip(frames, ticks)):
        if index and (tick - ticks[index - 1]) / 1e7 > .2:
            tracker.reset()
        raw_regions = regions(decode_frame(raw))
        candidates = [part.candidate for part in raw_regions]
        morphology = None
        if len(raw_regions) == 2 and hypot(candidates[0].x - candidates[1].x,
                                           candidates[0].y - candidates[1].y) < coalesce_distance:
            merged, morphology = combine(raw_regions)
            candidates = [merged]
        elif len(raw_regions) == 1:
            _, morphology = combine(raw_regions)
        contacts, _ = tracker.update(index, candidates)
        visible = [vars(contact) for contact in contacts]
        result = overlay.observe(index, tick / 1e7, visible, morphology)
        if len(result['observed_contacts']) != len(visible):
            raise AssertionError('shadow gate emitted a phantom contact')
        visible_histogram[len(visible)] += 1
        shadow_histogram[result['internal_shadow_count']] += 1
        frame_results.append((len(visible), result['internal_shadow_count']))
        for event in result['events']:
            if event['action'] in ('occluded', 'morphology_release', 'expired'):
                events.append({'frame': index,
                               'seconds_from_first_raw': round((tick - ticks[0]) / 1e7, 6),
                               **event})
    markers = marker_summary(pointer, ticks, frame_results)
    holds = guided_hold_summary(pointer, ticks, frame_results)
    return {
        'status': 'DIAGNOSTIC_ONLY_NO_CONTACT_EMISSION',
        'frames': len(frames),
        'coalesce_distance_cells': coalesce_distance,
        'visible_contact_histogram': dict(sorted(visible_histogram.items())),
        'internal_shadow_histogram': dict(sorted(shadow_histogram.items())),
        'counters': overlay.totals,
        'operator_markers': markers,
        'guided_holds': holds,
        'diagnostic_events': events,
        'limits': [
            'Threshold/coalescing and morphology ratios are experimental.',
            'A shadow is identity memory only and never an emitted contact.',
            'One-track return cannot create a second contact.',
            'This replay does not establish Windows classifier equivalence.'
        ]
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    text = json.dumps(replay(args.run_dir), indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
