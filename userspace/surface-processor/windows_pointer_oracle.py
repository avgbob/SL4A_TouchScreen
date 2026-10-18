#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Build a frame-aligned OS-pointer oracle from a correlated guided V4 run.

The output contains private pointer coordinates and timing. It represents
OS-visible Windows pointer lifetimes, not HeatCore internal contact IDs,
classes, groups, rejected candidates, or pre-publication state.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


CONTACT_EVENTS = frozenset({'DOWN', 'UPDATE', 'UP'})
TRANSITION_EVENTS = frozenset({'DOWN', 'UP'})
CONFIRM_PREFIX = 'OPERATOR_CONFIRM_'
HOLD_COMPLETE = 'GUIDED_HOLD_COMPLETE'
GUARD_AFTER_TICKS = 3_500_000
GUARD_BEFORE_TICKS = 1_500_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError(f'{path}: expected a JSON object')
    return value


def parse_int(value: str | None, label: str, *, default: int | None = None) -> int:
    if value in (None, ''):
        if default is None:
            raise ValueError(f'missing integer field {label}')
        return default
    try:
        return int(value, 0)
    except ValueError as exc:
        raise ValueError(f'invalid integer field {label}: {value!r}') from exc


def optional_int(row: dict[str, str], key: str) -> int | None:
    value = row.get(key, '')
    return None if value == '' else parse_int(value, key)


def read_pointer_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError(f'{path}: no pointer rows')
    required = {
        'StopwatchTicks', 'Stage', 'Event', 'PointerId', 'X', 'Y', 'RawX',
        'RawY', 'ContactL', 'ContactT', 'ContactR', 'ContactB', 'Pressure',
        'Orientation', 'PointerFlags', 'FrameId', 'OperatorPhysical',
    }
    missing = required.difference(rows[0])
    if missing:
        raise ValueError(f'{path}: missing columns: {sorted(missing)}')
    ticks = [parse_int(row['StopwatchTicks'], 'StopwatchTicks') for row in rows]
    if any(current < previous for previous, current in zip(ticks, ticks[1:])):
        raise ValueError(f'{path}: pointer ticks are not monotonic')
    return rows


@dataclass(frozen=True)
class Hold:
    stage: int
    event: str
    physical: int
    start: int
    end: int

    def annotation(self, tick: int) -> dict | None:
        if not self.start <= tick < self.end:
            return None
        return {
            'stage': self.stage,
            'event': self.event,
            'physical_contacts': self.physical,
            'conservative': (
                self.start + GUARD_AFTER_TICKS <= tick
                < self.end - GUARD_BEFORE_TICKS
            ),
        }


def guided_holds(rows: Iterable[dict[str, str]]) -> list[Hold]:
    pending: dict[int, dict[str, str]] = {}
    holds: list[Hold] = []
    for row in rows:
        event = row['Event']
        stage = parse_int(row['Stage'], 'Stage')
        if event.startswith(CONFIRM_PREFIX):
            if stage in pending:
                raise ValueError(f'stage {stage}: repeated confirmation')
            pending[stage] = row
        elif event == HOLD_COMPLETE:
            if stage not in pending:
                raise ValueError(f'stage {stage}: hold completion without confirmation')
            start_row = pending.pop(stage)
            start = parse_int(start_row['StopwatchTicks'], 'StopwatchTicks')
            end = parse_int(row['StopwatchTicks'], 'StopwatchTicks')
            if end <= start:
                raise ValueError(f'stage {stage}: non-positive hold')
            holds.append(Hold(
                stage=stage,
                event=start_row['Event'],
                physical=parse_int(start_row['OperatorPhysical'],
                                   'OperatorPhysical'),
                start=start,
                end=end,
            ))
    if pending:
        raise ValueError(f'unfinished guided holds: {sorted(pending)}')
    if holds and [hold.stage for hold in holds] != sorted(hold.stage for hold in holds):
        raise ValueError('guided hold stages are not ordered')
    return holds


def contact_from_row(row: dict[str, str], tick: int) -> dict:
    return {
        'id': parse_int(row['PointerId'], 'PointerId'),
        'x': parse_int(row['X'], 'X'),
        'y': parse_int(row['Y'], 'Y'),
        'raw_x': parse_int(row['RawX'], 'RawX'),
        'raw_y': parse_int(row['RawY'], 'RawY'),
        'contact': {
            'left': optional_int(row, 'ContactL'),
            'top': optional_int(row, 'ContactT'),
            'right': optional_int(row, 'ContactR'),
            'bottom': optional_int(row, 'ContactB'),
        },
        'pressure': optional_int(row, 'Pressure'),
        'orientation': optional_int(row, 'Orientation'),
        'pointer_flags': row['PointerFlags'],
        'windows_frame_id': parse_int(row['FrameId'], 'FrameId'),
        '_last_tick': tick,
    }


def public_contact(contact: dict, tick: int) -> dict:
    result = {key: value for key, value in contact.items()
              if not key.startswith('_')}
    result['age_since_update_100ns'] = tick - contact['_last_tick']
    return result


def transition_from_row(row: dict[str, str], origin: int) -> dict:
    return {
        'event': row['Event'],
        'id': parse_int(row['PointerId'], 'PointerId'),
        'time_100ns': parse_int(row['StopwatchTicks'], 'StopwatchTicks') - origin,
        'x': parse_int(row['X'], 'X'),
        'y': parse_int(row['Y'], 'Y'),
    }


def validate_manifest_hash(run_dir: Path, relative: str, actual_path: Path) -> None:
    manifest = read_json(run_dir / 'manifest.json')
    expected = None
    normalized = relative.replace('/', '\\').lower()
    for item in manifest.get('files', []):
        if str(item.get('file', '')).replace('/', '\\').lower() == normalized:
            expected = item.get('sha256')
            break
    if not expected:
        raise ValueError(f'manifest has no SHA-256 for {relative}')
    actual = sha256_file(actual_path)
    if actual.lower() != str(expected).lower():
        raise ValueError(f'{relative}: SHA-256 differs from original manifest')


def load_frame_ticks(run_dir: Path) -> tuple[list[int], dict]:
    coverage = read_json(run_dir / 'offline-analysis' / 'coverage-report.json')
    if coverage.get('physical_truth_protocol') != 'V4_GUIDED_PHYSICAL_TRUTH':
        raise ValueError('capture is not the guided V4 protocol')
    frames = coverage.get('wpr', {}).get('frames', [])
    ticks = [parse_int(item.get('clock_100ns_raw'), 'clock_100ns_raw')
             for item in frames]
    if not ticks:
        raise ValueError('coverage report contains no raw frames')
    if any(current <= previous for previous, current in zip(ticks, ticks[1:])):
        raise ValueError('raw frame ticks are not strictly monotonic')
    declared = coverage.get('wpr', {}).get('decoded_complete_0c_frames')
    if declared != len(ticks):
        raise ValueError(f'coverage declares {declared} frames but lists {len(ticks)}')
    return ticks, coverage


def build_oracle(run_dir: Path) -> tuple[list[dict], dict]:
    pointer_path = run_dir / 'pointer' / 'events.csv'
    validate_manifest_hash(run_dir, 'pointer/events.csv', pointer_path)
    rows = read_pointer_rows(pointer_path)
    ticks, coverage = load_frame_ticks(run_dir)
    holds = guided_holds(rows)
    origin = ticks[0]

    active: dict[int, dict] = {}
    frames: list[dict] = []
    row_index = 0
    previous_raw_tick = origin
    lifetime_counts = {'DOWN': 0, 'UP': 0}

    for frame_index, tick in enumerate(ticks):
        transitions = []
        while row_index < len(rows):
            row = rows[row_index]
            event_tick = parse_int(row['StopwatchTicks'], 'StopwatchTicks')
            if event_tick > tick:
                break
            event = row['Event']
            if event in CONTACT_EVENTS:
                pointer_id = parse_int(row['PointerId'], 'PointerId')
                if event == 'DOWN':
                    if pointer_id in active:
                        raise ValueError(f'duplicate DOWN for pointer {pointer_id}')
                    active[pointer_id] = contact_from_row(row, event_tick)
                    lifetime_counts['DOWN'] += 1
                elif event == 'UPDATE':
                    if pointer_id not in active:
                        raise ValueError(f'orphan UPDATE for pointer {pointer_id}')
                    active[pointer_id] = contact_from_row(row, event_tick)
                else:
                    if pointer_id not in active:
                        raise ValueError(f'orphan UP for pointer {pointer_id}')
                    del active[pointer_id]
                    lifetime_counts['UP'] += 1
                if event in TRANSITION_EVENTS:
                    transitions.append(transition_from_row(row, origin))
            row_index += 1

        hold = next((item.annotation(tick) for item in holds
                     if item.start <= tick < item.end), None)
        frames.append({
            'frame': frame_index,
            'time_100ns': tick - origin,
            'gap_from_previous_100ns': (
                0 if frame_index == 0 else tick - previous_raw_tick
            ),
            'contacts': [public_contact(active[pointer_id], tick)
                         for pointer_id in sorted(active)],
            'transitions': transitions,
            'guided_hold': hold,
        })
        previous_raw_tick = tick

    tail_transitions = []
    while row_index < len(rows):
        row = rows[row_index]
        event = row['Event']
        if event in CONTACT_EVENTS:
            pointer_id = parse_int(row['PointerId'], 'PointerId')
            event_tick = parse_int(row['StopwatchTicks'], 'StopwatchTicks')
            if event == 'DOWN':
                if pointer_id in active:
                    raise ValueError(f'duplicate tail DOWN for pointer {pointer_id}')
                active[pointer_id] = contact_from_row(row, event_tick)
                lifetime_counts['DOWN'] += 1
            elif event == 'UPDATE':
                if pointer_id not in active:
                    raise ValueError(f'orphan tail UPDATE for pointer {pointer_id}')
                active[pointer_id] = contact_from_row(row, event_tick)
            else:
                if pointer_id not in active:
                    raise ValueError(f'orphan tail UP for pointer {pointer_id}')
                del active[pointer_id]
                lifetime_counts['UP'] += 1
            if event in TRANSITION_EVENTS:
                tail_transitions.append(transition_from_row(row, origin))
        row_index += 1

    expected_lifetimes = coverage.get('physical_truth_v4', {}).get(
        'os_event_lifetimes', {})
    if lifetime_counts != expected_lifetimes:
        raise ValueError(
            f'lifetime counts differ: {lifetime_counts} != {expected_lifetimes}'
        )
    if active:
        raise ValueError(f'active pointers remain at end: {sorted(active)}')

    hold_summary = []
    for hold in holds:
        indices = [index for index, tick in enumerate(ticks)
                   if hold.start <= tick < hold.end]
        conservative = [
            index for index in indices
            if hold.start + GUARD_AFTER_TICKS <= ticks[index]
            < hold.end - GUARD_BEFORE_TICKS
        ]
        histogram: dict[str, int] = {}
        for index in conservative:
            key = str(len(frames[index]['contacts']))
            histogram[key] = histogram.get(key, 0) + 1
        hold_summary.append({
            'stage': hold.stage,
            'event': hold.event,
            'physical_contacts': hold.physical,
            'duration_100ns': hold.end - hold.start,
            'raw_frames': len(indices),
            'conservative_raw_frames': len(conservative),
            'windows_contact_histogram': histogram,
        })

    summary = {
        'schema': 'sl4a-windows-pointer-oracle-v1',
        'status': 'OS_VISIBLE_POINTER_ORACLE_NOT_HEATCORE_INTERNAL_TRUTH',
        'privacy': 'PRIVATE: contains touch coordinates and timing; do not publish',
        'frame_count': len(frames),
        'pointer_lifetimes': lifetime_counts,
        'active_at_end': [],
        'tail_transitions': tail_transitions,
        'guided_holds': hold_summary,
        'source': {
            'pointer_events_sha256': sha256_file(pointer_path),
            'wpr_csv_sha256': coverage.get('wpr', {}).get('source_sha256'),
            'manifest_generated_utc': coverage.get('manifest_created_utc'),
        },
        'limits': [
            'Pointer IDs and coordinates are OS-visible Win32 observations.',
            'They are not HeatCore internal IDs, classifier labels or groups.',
            'Coordinates remain in Windows screen pixels; no sensor-grid mapping is guessed.',
            'Human physical labels apply only inside guided holds; transitions are unknown.',
            'Raw-frame times are relative to the first frame, not converted to UTC.',
        ],
    }
    return frames, summary


def write_oracle(frames: Iterable[dict], output: Path) -> str:
    digest = hashlib.sha256()
    with output.open('wb') as stream:
        for frame in frames:
            line = (json.dumps(frame, sort_keys=True, separators=(',', ':'),
                               allow_nan=False) + '\n').encode('utf-8')
            stream.write(line)
            digest.update(line)
    return digest.hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args(argv)
    frames, summary = build_oracle(args.run_dir)
    summary['oracle_sha256'] = write_oracle(frames, args.output)
    summary_path = args.summary or output_summary_path(args.output)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True,
                                       allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': summary['status'],
        'frames': summary['frame_count'],
        'pointer_lifetimes': summary['pointer_lifetimes'],
        'oracle': str(args.output),
        'summary': str(summary_path),
        'oracle_sha256': summary['oracle_sha256'],
    }, indent=2, sort_keys=True))
    return 0


def output_summary_path(output: Path) -> Path:
    return output.with_suffix(output.suffix + '.summary.json')


if __name__ == '__main__':
    raise SystemExit(main())
