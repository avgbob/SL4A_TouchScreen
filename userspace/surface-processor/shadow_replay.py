#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Reproducible sensitivity sweep of offline-only contact-identity shadowing.

Runs the unmodified PR #12 Processor against published 8232 raw 72x48 frames;
adds shadow overlays only after prototype already emitted observed contacts.
No Windows ID fidelity claim, no synthetic finger report, no hardware access.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter
import json
from pathlib import Path

from pinch_dataset import load_dataset, TICKS_PER_SECOND_PROVISIONAL
from processor import CELLS, Config, Processor
from shadow_tracker import ShadowConfig, ShadowOverlay


def closest_frame(times, target):
    i=bisect_left(times,target)
    if i<=0: return 0
    if i>=len(times): return len(times)-1
    return i if abs(times[i]-target)<abs(times[i-1]-target) else i-1


def replay(path:Path, ttl_seconds=(.2,.4,1.,2.), offset_seconds=.058212):
    meta,raw,ticks,events=load_dataset(path)
    if not (meta['frame_count']==8232 and len(raw)==8232*CELLS):
        raise ValueError('not the verified public 8,232-frame corpus')
    times=[v/TICKS_PER_SECOND_PROVISIONAL for v in ticks]
    proc=Processor(Config())
    # Preserve this published audit's original immediate-recovery semantics.
    # The physical-truth replay tests the newer three-frame hysteresis.
    overlays={str(t):ShadowOverlay(ShadowConfig(ttl_seconds=t,recovery_frames=1))
              for t in ttl_seconds}
    baseline=Counter();counts=Counter();candidate=Counter();shadow_tally={k:Counter() for k in overlays}
    observations={k:[] for k in overlays}; events_log={k:[] for k in overlays}
    markers=[float(e['relative_seconds_from_first_pointer_down']) for e in events
             if e['record_kind']=='M_TWO_PHYSICAL_ONE_REPORTED']
    windows=[closest_frame(times,t+offset_seconds) for t in markers]
    controls=[3.,25.,83.,86.,90.]
    control_indices=[closest_frame(times,t+offset_seconds) for t in controls]
    wanted=set(windows+control_indices)
    # Preserve full real sensor t cadence; events are *not* a perfectly aligned reference.
    for i,tm in enumerate(times):
        if i>0 and times[i]-times[i-1]>.2:
            proc.tracker.reset()
        p=proc.process(i,raw[i*CELLS:(i+1)*CELLS])
        if p['stage']=='baseline':baseline['frames']+=1
        visible=p['contacts']
        counts[len(visible)]+=1
        candidate[len(p['candidates'])]+=1
        for key,overlay in overlays.items():
            r=overlay.observe(i,tm,visible)
            if len(r['observed_contacts'])!=len(visible):
                raise AssertionError('shadow output produced phantom contact')
            shadow_tally[key][len(overlay.shadows)]+=1
            if r['events'] and len(events_log[key])<10000:
                for evt in r['events']:
                    events_log[key].append({'raw_frame':i,'raw_relative_seconds':round(tm,6),**evt})
            if i in wanted:
                observations[key].append({'frame':i,'raw_relative_seconds':round(tm,6),
                                          'visible_count':len(visible),
                                          'internal_shadows':len(overlay.shadows),
                                          'contacts':[{'source':c['source_id'],'label':c['stable_label']}
                                                      for c in r['observed_contacts']]})
    output={
      'dataset_raster_sha256':meta['raster_concatenated_sha256'],
      'dataset_frames':meta['frame_count'],
      'processor_output_contact_histogram':dict(sorted(counts.items())),
      'processor_candidate_histogram':dict(sorted(candidate.items())),
      'reference_marker_windows_provisional_raw_frames':windows,
      'reference_marker_windows_warning':'behavioral relative offset, not independently synchronized QPC-to-UTC',
      'shadow_is_internal_only':True,
      'source_processor_modified':False,
      'ttl_sweep':{
        key:{'ttl_seconds':float(key),'counters':dict(o.totals),
            'internal_shadow_frames_histogram':dict(sorted(shadow_tally[key].items())),
            'default_actual_id_reuse_is_disabled':not o.cfg.allow_provisional_id_reuse,
            'diagnostic_events':events_log[key],
            'sampled_controls_and_M_frames':observations[key],
            'warning':'reassociated stable_label is not Windows ID truth; cannot infer physical continuity through occlusion'}
        for key,o in overlays.items()},
      'limits':[
        'OS marker and sensor epochs only behaviorally aligned; do not claim frame-exact Windows parity.',
        'The source detector sometimes loses a finger before the proximity requirement is met.',
        'Observed contact count can never increase with shadow overlay; no ghost is emitted.',
        'Internal relabeling could still falsely stitch a rapid same-place replacement touch.',
        'Raw close contacts may be physically indistinguishable; no true release labels per raw frame.'
       ]}
    return output


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dataset',type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--offset-seconds',type=float,default=.058212,
                    help='behavioral offset, not validated wall-clock conversion')
    x=ap.parse_args(argv)
    result=replay(x.dataset,offset_seconds=x.offset_seconds)
    txt=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'
    if x.output:
        x.output.parent.mkdir(parents=True,exist_ok=True)
        x.output.write_text(txt,encoding='utf-8')
    else:print(txt)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
