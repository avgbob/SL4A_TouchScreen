#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Evidence-bound lifecycle audit on the public SL4 AMD 8232-frame pinch corpus.

Sensor segmentation timestamps are COMPARED with Windows pointer event-relative
seconds: the clock correspondence here is a behavioral estimate, not a verified
QPC-to-UTC map or internal Microsoft contact oracle. Nothing touches a device.

The four calibration control transitions are independently chosen from the
annotated *one-finger release, far-apart second finger DOWN, staggered lift,
last release*. Pinch failures are excluded from clock calibration.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from statistics import median

from processor import CELLS
from pinch_dataset import TICKS_PER_SECOND_PROVISIONAL, components, load_dataset, lobe_peaks

# Ordered V2 events are pseudonymous; stage/identity combination identifies
# four clear 'non-pinch' controls to calibrate a *behavioral* time offset.
CONTROL_EVENT_SPECS = (
    ('ONE_FINGER_RELEASE', 'UP', '1', 1, 0),
    ('FAR_APART_SECOND_DOWN', 'DOWN', '3', 1, 2),
    ('STAGGERED_INDEPENDENT_LIFT', 'UP', '3', 2, 1),
    ('FINAL_FINGER_RELEASE', 'UP', '7', 1, 0),
)


def count_sensor_regions(data: bytes, frame_count: int, *, threshold: int = 150) -> list[int]:
    """Strict per-frame component counts; extra regions are retained, not capped."""
    if len(data) != frame_count * CELLS:
        raise ValueError('incomplete or inconsistent frame bytes')
    return [len(components(data[i*CELLS:(i+1)*CELLS], threshold))
            for i in range(frame_count)]


def rolling_majority(counts: list[int], *, width: int = 15) -> list[int]:
    """Use median of a symmetrical odd frame window to remove 10-50ms noise."""
    if width < 1 or width % 2 != 1:
        raise ValueError('median width must be positive odd')
    half = width // 2
    return [int(median(counts[max(0,i-half):min(len(counts), i+half+1)]))
            for i in range(len(counts))]


def stable_transitions(times: list[float], smoothed: list[int], *,
                       support_seconds: float = .15) -> list[dict]:
    """Find durable 0/1/2 count transitions without requiring stationary edges.

    One transition is accepted iff the median observed count for 300ms *before*
    and *after* the candidate agrees with its immediate states. This is designed
    to ignore brief split blips during merged contacts. Does not fit Windows IDs.
    """
    if len(times) != len(smoothed) or any(b <= a for a,b in zip(times, times[1:])):
        raise ValueError('time and state records must be equal-sized and monotonic')
    out=[]
    for i in range(1,len(times)):
        if smoothed[i] == smoothed[i-1]:
            continue
        before=[smoothed[k] for k in range(i-1,-1,-1)
                if 0 <= times[i]-times[k] <= support_seconds]
        after=[smoothed[k] for k in range(i,len(times))
               if 0 <= times[k]-times[i] <= support_seconds]
        if (not before or not after or
            times[i] - times[max(0,i-len(before))] < .8*support_seconds or
            times[min(len(times)-1,i+len(after)-1)]-times[i] < .8*support_seconds):
            continue
        b,a=int(median(before)),int(median(after))
        if (b == smoothed[i-1] and a == smoothed[i] and b!=a):
            out.append({'frame_index':i,'raw_relative_seconds':round(times[i],6),
                        'before':b,'after':a})
    return out


def align_controls(events: list[dict], transitions: list[dict],
                   *, search_seconds: float = .35) -> dict:
    control=[]
    for label,kind,cid,before,after in CONTROL_EVENT_SPECS:
        matching=[e for e in events if e.get('record_kind')==kind and
                  e.get('anonymous_contact')==cid]
        if len(matching)!=1:
            raise ValueError('missing/duplicate control event '+label)
        event=matching[0]
        t=float(event['relative_seconds_from_first_pointer_down'])
        near=[x for x in transitions if x['before']==before and x['after']==after and
              abs(x['raw_relative_seconds']-t)<=search_seconds]
        if not near:
            control.append({'name':label,'os_seconds':t,'found':False})
            continue
        found=min(near,key=lambda r:abs(r['raw_relative_seconds']-t))
        control.append({'name':label,'os_seconds':t,'found':True,
                        'raw_seconds':found['raw_relative_seconds'],
                        'raw_minus_os_seconds':round(found['raw_relative_seconds']-t,6)})
    offsets=[x['raw_minus_os_seconds'] for x in control if x['found']]
    return {'controls':control,'controls_found':len(offsets),
            'median_raw_minus_os_seconds':round(median(offsets),6) if offsets else None,
            'min_raw_minus_os_seconds':min(offsets) if offsets else None,
            'max_raw_minus_os_seconds':max(offsets) if offsets else None,
            'timing_caveat':('These offsets reflect threshold crossings and Windows '+
              'presentation latency in four clear control gestures. '+
              'They are not independent WPR-QPC-to-UTC calibration. '+
              'Do not make claims of millisecond-precise frame identity.')}


def last_collapse(transitions: list[dict], event_t: float):
    """Return FIRST collapse in the final merge episode before a close OS UP.

    Brief reappearance of two components (<150ms) is a flicker within an
    occlusion episode, not a new sustained separation. A sustained recovery
    resets the episode and later collapses become fresh episodes.
    """
    candidates=[p for p in transitions if p['before']==2 and p['after']==1
                and event_t-2 <= p['raw_relative_seconds'] <= event_t+.35]
    if not candidates:
        return None, []
    first=candidates[-1]
    flickers=[]
    for earlier in reversed(candidates[:-1]):
        intervening=[p for p in transitions if earlier['raw_relative_seconds'] <
                     p['raw_relative_seconds'] < first['raw_relative_seconds']
                     and p['before']==1 and p['after']==2]
        if len(intervening)!=1:
            break
        recovery=intervening[0]
        lifetime=first['raw_relative_seconds'] - recovery['raw_relative_seconds']
        if lifetime>=.15:
            break
        flickers.append({'start':recovery['raw_relative_seconds'],
                         'end':first['raw_relative_seconds'],
                         'duration_seconds':round(lifetime,6)})
        first=earlier
    return first, list(reversed(flickers))


def preloss_window(data: bytes, times: list[float], center: float,
                   *, seconds: float = 2.0) -> dict:
    """Compare final 2s preceding OS release, not just operator M examples."""
    region_hist=Counter()
    peak_hist=Counter()
    mass_by_regions={0:[],1:[],2:[]}
    indices=[i for i,t in enumerate(times) if center-seconds <= t <= center]
    # Subsample every 5 frames for expensive smoothed peak calculation. Full
    # component-count timeline is independently computed for every raw frame.
    sample=indices[::5]
    for i in sample:
        raster=data[i*CELLS:(i+1)*CELLS]
        blobs=components(raster,150)
        n=len(blobs)
        region_hist[n]+=1
        peak_hist[len(lobe_peaks(raster,10,4))]+=1
        if n in mass_by_regions:
            mass_by_regions[n].append(round(sum(b['mass'] for b in blobs)))
    return {'raw_window_seconds':[round(center-seconds,4),round(center,4)],
            'sample_stride_frames':5,'sampled_frames':len(sample),
            'component_count_histogram':dict(sorted(region_hist.items())),
            'smoothed_peak_count_histogram':dict(sorted(peak_hist.items())),
            'median_component_mass_by_count':{
                str(k):round(median(v),2) for k,v in mass_by_regions.items() if v},
            'warning':'Sampling for morphology; no recovered Microsoft classifier; one connected region may conceal two physical fingers.'}


def weak_peak_controls(raw: bytes, times: list[float], markers: list[dict],
                       offset_seconds: float, *, stride: int = 10) -> dict:
    """Sample depth sensitivity on controls AND physically marked loss windows.

    Smoothed strength=180-mean(3x3 cell values). NMS separation >=4 cells.
    This is NOT a deconvolution or evidence two physical peaks don't exist.
    """
    if stride < 1:
        raise ValueError('sample stride must be >=1')
    windows=[('SINGLE_FINGER_EARLY',3.,9.,stride),
             ('SINGLE_AFTER_INDEPENDENT_LIFT',85.,91.,stride),
             ('TWO_WIDE_APART',25.,28.,stride)]
    for i, m in enumerate(markers,1):
        center=float(m['relative_seconds_from_first_pointer_down'])+offset_seconds
        windows.append(('M'+str(i),center-.25,center+.25,2))
    result={}
    for name,start,end,step in windows:
        positions=[i for i,t in enumerate(times) if start<=t<=end][::step]
        per_frame=[lobe_peaks(raw[i*CELLS:(i+1)*CELLS],
                              minimum_smoothed_depth=2,
                              minimum_separation=4) for i in positions]
        depths={}
        for depth in (2,5,10,20):
            hist=Counter(sum(p['strength']>=depth for p in peaks) for peaks in per_frame)
            depths[str(depth)]={'peak_count_histogram':dict(sorted(hist.items())),
              'fraction_two_or_more':round(sum(n for k,n in hist.items() if k>=2)/
                                           len(positions),4) if positions else None}
        result[name]={'raw_seconds_approx':[round(start,5),round(end,5)],
                      'sampled_frames':len(positions),'thresholds':depths}
    return {'sampling':'Windowed subset; peak strength uses 3x3 mean-depth '
                       'relative to nominal 180 background and 4-cell NMS. '
                       'No true peak-splitting/classification inference.',
            'control_and_marker_windows':result}


def audit(dataset: Path, *, all_windows: bool = True, threshold: int = 150) -> dict:
    meta,raw,ticks,events=load_dataset(dataset)
    sec=[x/TICKS_PER_SECOND_PROVISIONAL for x in ticks]
    counts=count_sensor_regions(raw,meta['frame_count'],threshold=threshold)
    smoothed=rolling_majority(counts)
    transitions=stable_transitions(sec,smoothed)
    calibration=align_controls(events,transitions)
    if calibration['controls_found']<3:
        raise ValueError('too few independent control transitions for approximate clock comparison')
    offset=calibration['median_raw_minus_os_seconds']
    # Pinch events after second DOWN but before independent late-stage UP.
    pinch_ups=[e for e in events if e['record_kind']=='UP' and
                e.get('anonymous_contact') in ('2','4','5','6')]
    markers=[e for e in events if e['record_kind']=='M_TWO_PHYSICAL_ONE_REPORTED']
    rows=[]
    for ev in pinch_ups:
        t=float(ev['relative_seconds_from_first_pointer_down'])
        # Only behavioral calibration; offset uncertainty ~ range of control offsets.
        raw_est=t+offset
        matched,flickers=last_collapse(transitions,raw_est)
        item={'os_release_relative_seconds':t,
              'contact':ev['anonymous_contact'],
              'raw_time_estimated_from_controls':round(raw_est,6),
              'qualifying_collapse':matched,
              'short_two_region_reappearances_within_merge_episode':flickers,
              'raw_collapse_leads_presented_os_up_by_seconds':(
                  round(raw_est-matched['raw_relative_seconds'],6) if matched else None),
              'physical_contact_at_os_release':'UNKNOWN (M annotations later, not at each UP)',
              'later_operator_two_physical_confirmation_before_new_DOWN':any(
                 float(m['relative_seconds_from_first_pointer_down'])>t and
                 float(m['relative_seconds_from_first_pointer_down'])<min(
                    (float(d['relative_seconds_from_first_pointer_down'])
                    for d in events if d['record_kind']=='DOWN' and
                    float(d['relative_seconds_from_first_pointer_down'])>t),default=float('inf'))
                 for m in markers)}
        if all_windows:
            item['preloss_signal']=preloss_window(raw,sec,raw_est)
        rows.append(item)
    # Controls ensure true deliberate releases do NOT justify maintaining a
    # reported contact after OS UP. A shadow hypothesis is diagnosis only.
    result={'dataset_raster_sha256':meta['raster_concatenated_sha256'],
            'dataset_frames':meta['frame_count'],
            'raw_timebase':'nominal 10MHz, behavioral offset estimate only',
            'event_clock_qualification':calibration,
            'raw_component_count_histogram':dict(sorted(Counter(counts).items())),
            'durable_raw_transitions':transitions,
            'pinch_stage_releases':rows,
            'operator_m_times':[float(e['relative_seconds_from_first_pointer_down']) for e in markers],
            'weak_peak_sensitivity':weak_peak_controls(raw,sec,markers,offset) if all_windows else None,
            'diagnostic_policy':('Two-to-one region collapse may be a temporary occlusion, '
              'but may also be a genuine lift. A tracker may mark a shadow track '
              'for investigation, but must NOT publish a second contact solely '
              'because it previously existed; genuine lift controls would ghost.'),
            'limitations':['No physical video synchronized to individual UP events.',
             'Behavioral alignment, not a calibrated ETL QPC/UTC conversion.',
             'One raw region is not proof of one physical touch or a hardware defect.',
             'No Windows TouchAndPen classified candidate/quality output was recorded.']}
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--no-morphology',action='store_true')
    args=p.parse_args(argv)
    out=audit(args.dataset, all_windows=not args.no_morphology)
    result=json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(result,encoding='utf-8')
    else:
        print(result)
    return 0

if __name__=='__main__':
    raise SystemExit(main())