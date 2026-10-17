#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Aggregate real-Windows CapImg proxy-blob vs Linux-prototype candidate counts.

A byte<135 connected component is a *raw sensor region*, not a Windows contact,
track, classifier decision, palm decision, or true positive. Do not use these
metrics as final Windows equivalence or precision/recall claims.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from pathlib import Path

from processor import CELLS, COLS, ROWS, LUT, decode_frame
from replay import frames


def sensor_regions(raster: bytes, threshold: int = 135) -> list[tuple[int, int]]:
    if len(raster) != CELLS or not 0 <= threshold <= 255:
        raise ValueError('invalid raster or threshold')
    active = bytearray(b < threshold for b in raster)
    found: list[tuple[int, int]] = []
    for start in range(CELLS):
        if not active[start]:
            continue
        active[start] = 0
        q = deque([start])
        pixels = mass = 0
        while q:
            at = q.popleft()
            pixels += 1
            mass += LUT[raster[at]]
            y, x = divmod(at, COLS)
            for j in (at - 1 if x else -1,
                      at + 1 if x + 1 < COLS else -1,
                      at - COLS if y else -1,
                      at + COLS if y + 1 < ROWS else -1):
                if j >= 0 and active[j]:
                    active[j] = 0
                    q.append(j)
        found.append((pixels, mass))
    return found


def summarize(hex_frames: Path, processed: Path) -> dict:
    raw = (decode_frame(data) for _, data in frames(hex_frames))
    with processed.open(encoding='utf-8') as src:
        output = [json.loads(row) for row in src if row.strip()]
    totals = Counter()
    candidate_bins = Counter()
    proxy_bins = Counter()
    contact_bins = Counter()
    over = under = equal = 0
    index = 0
    for index, (raster, model) in enumerate(zip(raw, output, strict=True), 1):
        if model.get('frame') != index - 1:
            raise ValueError('nonaligned replay frame sequence')
        regions = sensor_regions(raster)
        # This filter reproduces the *static* two-pixel/weight proxy used in
        # previous raw-replay analysis. It is not DLL class validation.
        qualified = sum(pixels >= 2 and mass >= 1000 for pixels, mass in regions)
        totals['sensor_regions_all'] += len(regions)
        totals['sensor_regions_qualified_proxy'] += qualified
        if model['stage'] == 'baseline':
            totals['baseline_frames'] += 1
            continue
        if model['stage'] != 'tracking':
            raise ValueError('unrecognized replay stage')
        totals['tracking_frames'] += 1
        candidate = len(model['candidates'])
        contact = len(model['contacts'])
        totals['prototype_candidates'] += candidate
        totals['prototype_contacts'] += contact
        candidate_bins[candidate] += 1
        proxy_bins[qualified] += 1
        contact_bins[contact] += 1
        if candidate < qualified:
            under += 1
        elif candidate > qualified:
            over += 1
        else:
            equal += 1
    return {
        'frames': index, 'counts': dict(totals),
        'histograms': {'raw_qualified_regions': dict(proxy_bins),
                       'prototype_candidates': dict(candidate_bins),
                       'prototype_contacts': dict(contact_bins)},
        'candidate_versus_raw_proxy': {'fewer_frames': under,
                                       'more_frames': over,
                                       'equal_frames': equal},
        'warning': 'This uses raw byte<135 CCL with size/weight filters; it is NOT Windows processed contact ground truth.'
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('frames', type=Path, help='Windows-derived V0 frames.txt')
    p.add_argument('processor_jsonl', type=Path, help='Replay model JSONL')
    a = p.parse_args(argv)
    print(json.dumps(summarize(a.frames, a.processor_jsonl), indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
