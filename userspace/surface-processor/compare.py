#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Frame-align offline contact JSONL against processed-contact reference JSONL.

Both files must use grid-cell coordinates unless --reference-scale is set.
This does not manufacture Windows ground truth from raw capacitance frames.
"""
import argparse
import json
import math
from pathlib import Path
from statistics import mean
from processor import assignment


def _validate_frame_contacts(contacts, label):
    if not isinstance(contacts, list):
        raise ValueError(f'{label}: contacts must be an array')
    seen = set()
    for i, contact in enumerate(contacts):
        if not isinstance(contact, dict) or not all(k in contact for k in ('id', 'x', 'y')):
            raise ValueError(f'{label}: contact {i} needs id, x, y')
        cid = contact['id']
        if isinstance(cid, bool) or not isinstance(cid, (str, int)) or cid == '':
            raise ValueError(f'{label}: invalid contact ID')
        if cid in seen:
            raise ValueError(f'{label}: duplicate contact ID {cid!r}')
        seen.add(cid)
        for key in ('x', 'y'):
            try:
                value = float(contact[key])
            except (TypeError, ValueError, OverflowError) as e:
                raise ValueError(f'{label}: invalid {key}') from e
            if not math.isfinite(value):
                raise ValueError(f'{label}: nonfinite {key}')


def read_jsonl(path):
    result = {}
    for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        label = f'{path}:{lineno}'
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError('expected JSON object')
            frame = row['frame']
            if (type(frame) is not int or frame < 0 or frame in result):
                raise ValueError('duplicate/invalid frame')
            _validate_frame_contacts(row['contacts'], label)
            result[frame] = row['contacts']
        except (KeyError, ValueError, TypeError) as e:
            raise ValueError(f'{label}: invalid contact JSONL: {e}') from e
    if not result:
        raise ValueError(f'{path}: no contact frames')
    return result


def _reference_xy(contact, scale_x, scale_y, affine):
    x, y = float(contact['x']), float(contact['y'])
    if affine is None:
        return x * scale_x, y * scale_y
    return (affine[0][0] * x + affine[0][1] * y + affine[0][2],
            affine[1][0] * x + affine[1][1] * y + affine[1][2])


def _validate_affine(affine):
    if affine is None:
        return
    if (not isinstance(affine, list) or len(affine) != 2 or
            any(not isinstance(row, list) or len(row) != 3 for row in affine)):
        raise ValueError('reference affine must be a 2x3 array')
    try:
        values = [float(value) for row in affine for value in row]
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('reference affine contains an invalid value') from exc
    if not all(math.isfinite(value) for value in values):
        raise ValueError('reference affine contains a nonfinite value')


def compare(reference, experimental, *, max_distance=2.5, scale_x=1,
            scale_y=1, affine=None, allow_partial=False):
    if not math.isfinite(max_distance) or not 0 < max_distance < 1e6:
        raise ValueError('max_distance must be positive finite (< 1e6)')
    if not all(math.isfinite(x) and x > 0 for x in (scale_x, scale_y)):
        raise ValueError('reference scales must be positive finite')
    _validate_affine(affine)
    if affine is not None and (scale_x != 1 or scale_y != 1):
        raise ValueError('reference scale and affine are mutually exclusive')
    for label, frames in [('reference', reference), ('experiment', experimental)]:
        for frame, contacts in frames.items():
            if type(frame) is not int or frame < 0:
                raise ValueError(f'{label}: invalid frame number')
            _validate_frame_contacts(contacts, f'{label} frame {frame}')
    missing = sorted(set(reference) - set(experimental))
    unexpected = sorted(set(experimental) - set(reference))
    if not allow_partial and (missing or unexpected):
        raise ValueError(f'frame coverage mismatch: {len(missing)} missing, '
                         f'{len(unexpected)} additional frames; use --allow-partial explicitly')
    shared = sorted(set(reference) & set(experimental))
    if not shared:
        raise ValueError('reference and experimental frames do not overlap')
    missed = extra = switches = matched = 0
    errors = []
    last_match = {}
    details = []
    for f in shared:
        ref, got = reference[f], experimental[f]
        distances = []
        for a in ref:
            ax, ay = _reference_xy(a, scale_x, scale_y, affine)
            distances.append([math.hypot(ax - float(b['x']), ay - float(b['y']))
                              for b in got])
        nr, ng = len(ref), len(got)
        used = set()
        # Dummy unmatched columns allow a reference contact to remain unmatched.
        edge = [[d if d <= max_distance else 1e6 for d in row] +
                [max_distance + 1 if j == i else 1e6 for j in range(nr)]
                for i, row in enumerate(distances)]
        pairing = assignment(edge)
        frame_matched = 0
        for i, k in enumerate(pairing):
            if k >= ng or edge[i][k] >= 1e6:
                continue
            used.add(k)
            matched += 1
            frame_matched += 1
            error = distances[i][k]
            errors.append(error)
            # Count ID reassociation only when same reference ID is matched
            # in consecutive common frames, avoiding false switches after gaps.
            rid, gid = ref[i]['id'], got[k]['id']
            if rid in last_match and last_match[rid][0] == f-1 and last_match[rid][1] != gid:
                switches += 1
            last_match[rid] = (f, gid)
        missed += nr - frame_matched
        extra += ng - len(used)
        details.append({'frame': f, 'reference': nr, 'experiment': ng,
                        'matched': frame_matched, 'missed': nr-frame_matched,
                        'extra': ng-len(used)})
    return {'frames_compared': len(shared), 'reference_only_frames': len(missing),
            'experiment_only_frames': len(unexpected),
            'coverage_complete': not (missing or unexpected),
            'reference_frames': len(reference), 'experiment_frames': len(experimental),
            'matched_contacts': matched, 'missed_contacts': missed,
            'extra_contacts': extra, 'tracking_id_switches': switches,
            'mean_grid_error': round(mean(errors), 5) if errors else None,
            'max_grid_error': round(max(errors), 5) if errors else None,
            'details': details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('experiment', type=Path)
    parser.add_argument('--max-distance', type=float, default=2.5)
    parser.add_argument('--reference-scale-x', type=float, default=1.0)
    parser.add_argument('--reference-scale-y', type=float, default=1.0)
    parser.add_argument('--reference-affine-json', type=Path,
                        help='JSON calibration report containing matrix_screen_pixels_to_sensor_proxy')
    parser.add_argument('--allow-partial', action='store_true', help='compare only shared frames (reports coverage gaps)')
    a = parser.parse_args(argv)
    affine = None
    if a.reference_affine_json:
        calibration = json.loads(a.reference_affine_json.read_text(encoding='utf-8'))
        try:
            affine = calibration['matrix_screen_pixels_to_sensor_proxy']
        except (TypeError, KeyError) as exc:
            raise ValueError('calibration JSON lacks matrix_screen_pixels_to_sensor_proxy') from exc
    report = compare(read_jsonl(a.reference), read_jsonl(a.experiment),
                     max_distance=a.max_distance,
                     scale_x=a.reference_scale_x, scale_y=a.reference_scale_y,
                     affine=affine,
                     allow_partial=a.allow_partial)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
