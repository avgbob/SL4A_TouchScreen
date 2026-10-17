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


def read_jsonl(path):
    result = {}
    for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        try:
            row = json.loads(line)
            frame = row['frame']
            if not isinstance(frame, int) or frame < 0 or frame in result:
                raise ValueError('duplicate/invalid frame')
            assert isinstance(row['contacts'], list)
            for contact in row['contacts']:
                if not all(k in contact for k in ('id', 'x', 'y')):
                    raise ValueError('contact requires id, x, y')
            result[frame] = row['contacts']
        except (KeyError, ValueError, AssertionError, TypeError) as e:
            raise ValueError(f'{path}:{lineno}: invalid contact JSONL: {e}') from e
    if not result:
        raise ValueError(f'{path}: no contact frames')
    return result


def compare(reference, experimental, *, max_distance=2.5, scale_x=1, scale_y=1):
    if not math.isfinite(max_distance) or max_distance <= 0:
        raise ValueError('max_distance must be positive finite')
    if not all(math.isfinite(x) and x > 0 for x in (scale_x, scale_y)):
        raise ValueError('reference scales must be positive finite')
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
            ax, ay = float(a['x']) * scale_x, float(a['y']) * scale_y
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
    return {'frames_compared': len(shared), 'reference_only_frames': len(set(reference)-set(shared)),
            'experiment_only_frames': len(set(experimental)-set(shared)),
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
    a = parser.parse_args(argv)
    report = compare(read_jsonl(a.reference), read_jsonl(a.experiment),
                     max_distance=a.max_distance,
                     scale_x=a.reference_scale_x, scale_y=a.reference_scale_y)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
