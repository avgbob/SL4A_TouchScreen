#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Validate the sanitized behavioral contract of the clean guided V4 run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPECTED = {
    'OPERATOR_CONFIRM_EMPTY_START': (0, {}),
    'OPERATOR_CONFIRM_HORIZONTAL_TWO_APART': (2, {'2': 155}),
    'OPERATOR_CONFIRM_HORIZONTAL_CLOSE_BOTH_DOWN': (2, {'1': 160}),
    'OPERATOR_CONFIRM_HORIZONTAL_LEFT_LIFTED': (1, {'1': 158}),
    'OPERATOR_CONFIRM_HORIZONTAL_RIGHT_ONLY': (1, {'1': 161}),
    'OPERATOR_CONFIRM_HORIZONTAL_LEFT_RETURNED': (2, {'2': 152}),
    'OPERATOR_CONFIRM_HORIZONTAL_RIGHT_LIFTED': (1, {'1': 151}),
    'OPERATOR_CONFIRM_HORIZONTAL_LEFT_ONLY': (1, {'1': 158}),
    'OPERATOR_CONFIRM_HORIZONTAL_RIGHT_RETURNED': (2, {'2': 150}),
    'OPERATOR_CONFIRM_HORIZONTAL_TWO_APART_AGAIN': (2, {'2': 158}),
    'OPERATOR_CONFIRM_EMPTY_BETWEEN_TRIALS': (0, {}),
    'OPERATOR_CONFIRM_VERTICAL_TWO_APART': (2, {'2': 156}),
    'OPERATOR_CONFIRM_VERTICAL_CLOSE_LIGHT': (2, {'2': 150}),
    'OPERATOR_CONFIRM_VERTICAL_CLOSE_FIRM': (2, {'2': 153}),
    'OPERATOR_CONFIRM_VERTICAL_TOP_LIFTED': (1, {'1': 157}),
    'OPERATOR_CONFIRM_VERTICAL_BOTTOM_ONLY': (1, {'1': 153}),
    'OPERATOR_CONFIRM_VERTICAL_TOP_RETURNED': (2, {'1': 86, '2': 67}),
    'OPERATOR_CONFIRM_VERTICAL_TWO_APART_AGAIN': (2, {'2': 159}),
    'OPERATOR_CONFIRM_EMPTY_FINISH': (0, {}),
}


def validate(summary: dict) -> dict:
    errors = []
    if summary.get('schema') != 'sl4a-windows-pointer-oracle-v1':
        errors.append('unexpected oracle schema')
    if summary.get('frame_count') != 17018:
        errors.append('expected exactly 17018 raw frames')
    if summary.get('pointer_lifetimes') != {'DOWN': 14, 'UP': 14}:
        errors.append('expected balanced 14 DOWN / 14 UP')
    if summary.get('active_at_end') != []:
        errors.append('pointers remained active at exit')
    holds = summary.get('guided_holds', [])
    if len(holds) != len(EXPECTED):
        errors.append(f'expected {len(EXPECTED)} guided holds, got {len(holds)}')
    by_event = {item.get('event'): item for item in holds}
    if len(by_event) != len(holds):
        errors.append('guided hold events are not unique')
    for event, (physical, histogram) in EXPECTED.items():
        item = by_event.get(event)
        if item is None:
            errors.append(f'missing hold {event}')
            continue
        if item.get('physical_contacts') != physical:
            errors.append(f'{event}: wrong physical-contact label')
        if item.get('windows_contact_histogram') != histogram:
            errors.append(f'{event}: Windows count histogram changed')
    if errors:
        raise ValueError('; '.join(errors))
    return {
        'status': 'V4_ORACLE_CONTRACT_PASS',
        'frames': 17018,
        'guided_holds': len(EXPECTED),
        'pointer_lifetimes': {'DOWN': 14, 'UP': 14},
        'counterexamples': {
            'horizontal_close_physical_two_windows_one_frames': 160,
            'vertical_return_physical_two_windows_one_then_two_frames': {
                'one': 86,
                'two': 67,
            },
            'deliberate_lift_physical_one_windows_one_frames': 157,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path)
    args = parser.parse_args(argv)
    result = validate(json.loads(args.summary.read_text(encoding='utf-8')))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
