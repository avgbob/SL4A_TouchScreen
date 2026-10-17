#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Reproducible offline PR #12 replay of the published SL4A pinch sensor dataset.

No drivers, windows APIs, controller commands or dependencies outside stdlib.
The recorded OS event clock and raw WPR clock are NOT calibrated: M-event
windows are illustrative time-neighborhoods, not synchronized ground truth.
Connected-region and peak heuristics are experiments, NOT the Windows classifier.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from statistics import median
from zipfile import ZipFile

from processor import COLS, ROWS, CELLS, Config, Processor

TICKS_PER_SECOND_PROVISIONAL = 10_000_000


def load_dataset(path: Path):
    with ZipFile(path) as z:
        expected = {'heatmaps_u8.bin', 'metadata.json', 'frame_relative_ticks.csv',
                    'os_contact_transitions_relative.csv'}
        if not expected.issubset(set(z.namelist())):
            raise ValueError('dataset archive missing required files')
        metadata = json.loads(z.read('metadata.json'))
        if (metadata.get('frame_width'), metadata.get('frame_height'),
                metadata.get('raster_bytes_per_frame'), metadata.get('dtype')) != (COLS, ROWS, CELLS, 'uint8'):
            raise ValueError('unexpected grid geometry or dtype')
        data = z.read('heatmaps_u8.bin')
        count = metadata['frame_count']
        if len(data) != count * CELLS:
            raise ValueError('raster byte length / declared frame count mismatch')
        fingerprint = hashlib.sha256(data).hexdigest()
        if fingerprint != metadata['raster_concatenated_sha256']:
            raise ValueError('raster SHA-256 differs from metadata')
        rows = list(csv.DictReader(io.StringIO(z.read('frame_relative_ticks.csv').decode('utf-8-sig'))))
        if len(rows) != count or not rows:
            raise ValueError('timestamp count mismatch')
        times = []
        for i, row in enumerate(rows):
            if int(row['frame_index']) != i:
                raise ValueError('invalid timestamp index')
            tick = int(row['relative_wpr_ticks_at_10mhz'])
            if tick < 0 or (times and tick <= times[-1]):
                raise ValueError('non-monotonic timestamp')
            times.append(tick)
        if times[0] != 0:
            raise ValueError('timestamps must be relative to zero')
        events = list(csv.DictReader(io.StringIO(z.read('os_contact_transitions_relative.csv').decode('utf-8-sig'))))
        for event in events:
            t = float(event['relative_seconds_from_first_pointer_down'])
            if not math.isfinite(t) or t < 0:
                raise ValueError('invalid OS event-relative time')
        return metadata, data, times, events


def components(raster: bytes, threshold: int = 150, minimum_pixels: int = 3):
    """8-neighbor below-threshold raster regions, independent of PR #12 detector."""
    seen = bytearray(CELLS)
    regions = []
    for start in range(CELLS):
        if seen[start] or raster[start] >= threshold:
            continue
        seen[start] = 1
        queue = [start]
        size = 0
        sx = sy = signal = 0
        for p in queue:
            size += 1
            x, y = p % COLS, p // COLS
            strength = threshold - raster[p]
            signal += strength
            sx += strength * x
            sy += strength * y
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= ROWS:
                    continue
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if nx < 0 or nx >= COLS:
                        continue
                    j = ny * COLS + nx
                    if not seen[j] and raster[j] < threshold:
                        seen[j] = 1
                        queue.append(j)
        if size >= minimum_pixels:
            regions.append({'pixels': size,
                            'x': round(sx / signal, 3) if signal else None,
                            'y': round(sy / signal, 3) if signal else None,
                            'mass': signal})
    return sorted(regions, key=lambda v: -v['mass'])


def lobe_peaks(raster: bytes, minimum_smoothed_depth: float = 10.0,
               minimum_separation: float = 4.0, maximum_peaks: int = 8):
    """Independent exploratory 3x3-depth smoothing + local maxima + NMS.

    Local maxima are NOT independent touch contacts; this is a falsifiable
    alternative to connected components on merged peaks. No hidden state.
    """
    smooth = [0.0] * CELLS
    for y in range(1, ROWS-1):
        for x in range(1, COLS-1):
            i = y * COLS + x
            smooth[i] = sum(180 - raster[(y+dy)*COLS + x+dx]
                            for dy in (-1,0,1) for dx in (-1,0,1)) / 9.0
    raw_peaks = []
    for y in range(2, ROWS-2):
        for x in range(2, COLS-2):
            p = y*COLS+x
            value = smooth[p]
            if value < minimum_smoothed_depth:
                continue
            # Strict deterministic plateau tie-break: lowest grid index wins.
            neighbors = [((y+dy)*COLS+x+dx) for dy in (-1,0,1)
                         for dx in (-1,0,1) if dx or dy]
            if any(smooth[q] > value or (smooth[q] == value and q < p) for q in neighbors):
                continue
            raw_peaks.append((value,x,y))
    selected = []
    for value, x, y in sorted(raw_peaks, key=lambda t:(-t[0],t[2],t[1])):
        if all((x-px)**2+(y-py)**2 >= minimum_separation**2
               for _,px,py in selected):
            selected.append((value,x,y))
            if len(selected)>=maximum_peaks:
                break
    return [{'strength':round(float(v),2),'x':x,'y':y} for v,x,y in selected]


def nearest(times, target):
    """Binary search by monotone time; provisional event-to-raw comparison."""
    import bisect
    i = bisect.bisect_left(times, target)
    if i == len(times): return len(times)-1
    if i == 0: return 0
    return i if abs(times[i]-target) < abs(times[i-1]-target) else i-1


def window_report(raw, ticks, target_sec, window_sec=0.25):
    """Sensor-only descriptive stats around an approximately placed OS marker."""
    center = nearest(ticks, round(target_sec*TICKS_PER_SECOND_PROVISIONAL))
    idx = [j for j in range(len(ticks)) if abs(ticks[j]-ticks[center]) <= round(window_sec*TICKS_PER_SECOND_PROVISIONAL)]
    result = {'os_relative_seconds': target_sec,
              'nearest_raw_frame_provisional': center,
              'raw_relative_seconds': round(ticks[center]/TICKS_PER_SECOND_PROVISIONAL, 6),
              'raw_vs_os_relative_seconds_unverified': round(ticks[center]/TICKS_PER_SECOND_PROVISIONAL-target_sec,6),
              'frames_in_window':len(idx),
              'threshold_150_region_histogram':{}, 'threshold_165_region_histogram':{},
              'smoothed_peak_histogram':{}, 'examples':[]}
    h150,h165,peaks = Counter(),Counter(),Counter()
    for j in idx:
        r=raw[j*CELLS:(j+1)*CELLS]
        n150=len(components(r,150))
        n165=len(components(r,165))
        pk=lobe_peaks(r)
        h150[n150]+=1; h165[n165]+=1;peaks[len(pk)]+=1
        if j==center:
            result['examples']=[{'frame':j,'components_150':components(r,150),
                                  'components_165':components(r,165),
                                  'peak_candidates':pk}]
    result['threshold_150_region_histogram']={str(k):v for k,v in sorted(h150.items())}
    result['threshold_165_region_histogram']={str(k):v for k,v in sorted(h165.items())}
    result['smoothed_peak_histogram']={str(k):v for k,v in sorted(peaks.items())}
    return result


def run(path: Path, *, full_replay=True):
    meta, raw, ticks, events = load_dataset(path)
    gap_index = [i for i in range(1,len(ticks)) if ticks[i]-ticks[i-1]>2_000_000]  # >200ms
    marks=[e for e in events if e['record_kind']=='M_TWO_PHYSICAL_ONE_REPORTED']
    report = {'dataset_raster_sha256':meta['raster_concatenated_sha256'],
              'frames':meta['frame_count'],'relative_span_seconds':round(ticks[-1]/TICKS_PER_SECOND_PROVISIONAL,6),
              'timebase_status':'PROVISIONAL 10MHz, OS reference origin UNCALIBRATED',
              'raw_gap_indices':gap_index,
              'raw_gap_seconds':[round((ticks[i]-ticks[i-1])/TICKS_PER_SECOND_PROVISIONAL,6) for i in gap_index],
              'os_down_events':sum(e['record_kind']=='DOWN' for e in events),
              'os_up_events':sum(e['record_kind']=='UP' for e in events),
              'operator_markers':len(marks),
              'marker_windows':[window_report(raw,ticks,float(m['relative_seconds_from_first_pointer_down'])) for m in marks],
              'two_far_apart_reference':window_report(raw,ticks,25.0),
              'two_recovered_reference':window_report(raw,ticks,83.0),
              'limitations':['OS and WPR start times not formally aligned; samples near M markers are approximate.',
                             'Connected regions and smoothed peaks are NOT Windows classifier results.',
                             'Prototype uses baseline calibration frames which might contain initial touch.',
                             'Windows reported contact count is not an independent physical tracking oracle.']}
    if full_replay:
        proc=Processor(Config())
        counts=Counter();candidate_counts=Counter();valid_count=0
        events_out=[]; prev=0;resets=0
        for i in range(meta['frame_count']):
            if i>0 and ticks[i]-ticks[i-1]>2_000_000:
                proc.tracker.reset();resets+=1
            result=proc.process(i,raw[i*CELLS:(i+1)*CELLS]);valid_count+=1
            counts[len(result['contacts'])]+=1
            candidate_counts[len(result['candidates'])]+=1
            if i in {w['nearest_raw_frame_provisional'] for w in report['marker_windows']}:
                events_out.append({'frame':i,'contacts':result['contacts'],'candidates':result['candidates']})
        report['prototype_replay']={'processed':valid_count,'tracker_reset_on_200ms_real_capture_gap':resets,
          'output_contact_count_histogram':dict(sorted(counts.items())),
          'candidate_count_histogram':dict(sorted(candidate_counts.items())),
          'marked_frame_output_provisional':events_out}
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path,help='public sanitized ZIP, no private source required')
    p.add_argument('--out',type=Path,help='JSON report file')
    p.add_argument('--quick',action='store_true',help='skip full processor replay')
    args=p.parse_args(argv)
    report=run(args.dataset,full_replay=not args.quick)
    text=json.dumps(report,indent=2,sort_keys=True,allow_nan=False)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(text,encoding='utf-8')
    else: print(text)
    return 0

if __name__=='__main__':
    raise SystemExit(main())