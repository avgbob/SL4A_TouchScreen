#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Fit Windows screen pixels to the threshold-region sensor proxy.

The fit uses only conservative guided V4 frames. One-pointer/one-region frames
train a general 2D affine transform; two-pointer/two-region frames independently
score the transform with the lower-cost one-to-one assignment. The resulting
matrix is a measured comparison transform, not Windows classifier geometry.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from physical_truth_shadow_replay import load_run, regions
from processor import decode_frame


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def solve3(matrix: list[list[float]], vector: list[float]) -> list[float]:
    work = [list(matrix[row]) + [vector[row]] for row in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(work[row][column]))
        work[column], work[pivot] = work[pivot], work[column]
        divisor = work[column][column]
        if abs(divisor) < 1e-12:
            raise ValueError('singular calibration sample')
        work[column] = [value / divisor for value in work[column]]
        for row in range(3):
            if row == column:
                continue
            factor = work[row][column]
            work[row] = [work[row][item] - factor * work[column][item]
                         for item in range(4)]
    return [work[row][3] for row in range(3)]


def fit_affine(pairs: list[tuple[float, float, float, float]]
               ) -> tuple[list[float], list[float]]:
    if len(pairs) < 3:
        raise ValueError('at least three calibration pairs are required')
    normal = [[0.0] * 3 for _ in range(3)]
    target_x = [0.0] * 3
    target_y = [0.0] * 3
    for pointer_x, pointer_y, sensor_x, sensor_y in pairs:
        terms = (pointer_x, pointer_y, 1.0)
        for row in range(3):
            target_x[row] += terms[row] * sensor_x
            target_y[row] += terms[row] * sensor_y
            for column in range(3):
                normal[row][column] += terms[row] * terms[column]
    return solve3(normal, target_x), solve3(normal, target_y)


def transform(matrix: tuple[list[float], list[float]], x: float, y: float
              ) -> tuple[float, float]:
    row_x, row_y = matrix
    return (row_x[0] * x + row_x[1] * y + row_x[2],
            row_y[0] * x + row_y[1] * y + row_y[2])


def statistics(errors: list[float]) -> dict:
    if not errors:
        return {'samples': 0}
    ordered = sorted(errors)
    percentile_95 = ordered[min(len(ordered) - 1, int(.95 * len(ordered)))]
    return {
        'samples': len(ordered),
        'rmse_cells': round(math.sqrt(sum(value * value for value in ordered) /
                                      len(ordered)), 6),
        'median_cells': round(ordered[len(ordered) // 2], 6),
        'p95_cells': round(percentile_95, 6),
        'max_cells': round(ordered[-1], 6),
    }


def lower_cost_pairing(predicted: list[tuple[float, float]],
                       observed: list[tuple[float, float]]) -> list[float]:
    if len(predicted) != 2 or len(observed) != 2:
        raise ValueError('two-by-two assignment required')
    assignments = (((0, 0), (1, 1)), ((0, 1), (1, 0)))
    choice = min(assignments, key=lambda assignment: sum(
        (predicted[left][0] - observed[right][0]) ** 2 +
        (predicted[left][1] - observed[right][1]) ** 2
        for left, right in assignment))
    return [math.hypot(predicted[left][0] - observed[right][0],
                       predicted[left][1] - observed[right][1])
            for left, right in choice]


def calibrate(run_dir: Path, oracle_path: Path, threshold: int = 150) -> dict:
    frames, _, _ = load_run(run_dir)
    with oracle_path.open(encoding='utf-8') as stream:
        oracle = [json.loads(line) for line in stream if line.strip()]
    if len(frames) != len(oracle) or not frames:
        raise ValueError('raw frame/oracle coverage mismatch')
    if [item.get('frame') for item in oracle] != list(range(len(oracle))):
        raise ValueError('oracle frame sequence is not contiguous')

    training = []
    decoded_regions = []
    for raw, item in zip(frames, oracle):
        hold = item.get('guided_hold')
        found = regions(decode_frame(raw), threshold)
        decoded_regions.append(found)
        if not hold or not hold.get('conservative'):
            continue
        contacts = item.get('contacts', [])
        if len(contacts) == 1 and len(found) == 1:
            contact = contacts[0]
            candidate = found[0].candidate
            training.append((float(contact['x']), float(contact['y']),
                             candidate.x, candidate.y))
    matrix = fit_affine(training)

    training_errors = []
    for pointer_x, pointer_y, sensor_x, sensor_y in training:
        predicted_x, predicted_y = transform(matrix, pointer_x, pointer_y)
        training_errors.append(math.hypot(predicted_x - sensor_x,
                                          predicted_y - sensor_y))

    validation_errors = []
    by_hold: dict[str, list[float]] = defaultdict(list)
    validation_frames = 0
    for found, item in zip(decoded_regions, oracle):
        hold = item.get('guided_hold')
        contacts = item.get('contacts', [])
        if (not hold or not hold.get('conservative') or
                len(contacts) != 2 or len(found) != 2):
            continue
        predicted = [transform(matrix, float(contact['x']), float(contact['y']))
                     for contact in contacts]
        observed = [(part.candidate.x, part.candidate.y) for part in found]
        errors = lower_cost_pairing(predicted, observed)
        validation_errors.extend(errors)
        by_hold[hold['event']].extend(errors)
        validation_frames += 1

    return {
        'schema': 'sl4a-pointer-sensor-proxy-affine-v1',
        'status': 'MEASURED_PROXY_TRANSFORM_NOT_WINDOWS_CLASSIFIER_GEOMETRY',
        'threshold': threshold,
        'source_oracle_sha256': sha256_file(oracle_path),
        'matrix_screen_pixels_to_sensor_proxy': [
            [round(value, 12) for value in matrix[0]],
            [round(value, 12) for value in matrix[1]],
        ],
        'training_one_pointer_one_region': statistics(training_errors),
        'validation_two_pointer_two_region': {
            'frames': validation_frames,
            **statistics(validation_errors),
        },
        'validation_by_hold': {
            hold: statistics(errors) for hold, errors in sorted(by_hold.items())
        },
        'limits': [
            'Fit target is a threshold-150 connected-region centroid proxy.',
            'It is not a recovered Windows candidate or classifier coordinate.',
            'Training uses only conservative one-pointer/one-region guided frames.',
            'Two-pointer/two-region frames are validation only.',
            'Coordinate-bearing source oracle and raw frames remain private.',
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir', type=Path)
    parser.add_argument('oracle', type=Path)
    parser.add_argument('--threshold', type=int, default=150)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = calibrate(args.run_dir, args.oracle, args.threshold)
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
