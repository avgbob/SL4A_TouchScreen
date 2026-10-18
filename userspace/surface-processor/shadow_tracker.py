#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Opt-in OFFLINE shadow contact-identity overlay (no synthetic HID contacts).

This records a possibly occluded second finger *internally*, only when two
confirmed prototype contacts become one nearby contact. It can relabel a NEW,
actually detected contact after separation but NEVER adds a contact to output.
Unknown whether any disappearance is a real finger lift; a shadow is a hypothesis.
Default mode NEVER reuses old IDs; it logs a candidate reattachment for review.
ID reuse is an explicit experiment that can misidentify a rapid new finger touch.

No device access and no modification to processor.py / kernel / uinput.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite


@dataclass(frozen=True)
class ShadowConfig:
    ttl_seconds: float = 0.40
    max_merge_distance: float = 7.0
    max_recovery_distance: float = 3.0
    min_recovery_separation: float = 1.5
    ambiguity_margin: float = .50
    gap_reset_seconds: float = .20
    min_visible_age: int = 3
    max_shadows: int = 8
    allow_provisional_id_reuse: bool = False  # NEVER recommended for normal output

    def __post_init__(self):
        if (not all(isfinite(x) and x > 0 for x in (
              self.ttl_seconds, self.max_merge_distance,
              self.max_recovery_distance, self.min_recovery_separation,
              self.ambiguity_margin, self.gap_reset_seconds))
            or self.max_shadows < 1 or self.max_shadows > 48
            or self.min_visible_age < 1):
            raise ValueError('invalid shadow research policy')


@dataclass
class Visible:
    source: int
    label: int
    x: float
    y: float
    age: int


@dataclass
class Shadow:
    label: int
    x: float
    y: float
    lost_at_seconds: float
    anchor_label: int


class ShadowOverlay:
    """Conservative annotation of prototype contacts, with bounded identity memory.

    NOTE: No claim of Windows classifier equivalence or actual finger presence.
    All live output coordinates/contacts come directly from the input.
    """
    def __init__(self, config: ShadowConfig | None = None):
        self.cfg = config or ShadowConfig()
        self.visible: dict[int, Visible] = {}
        self.shadows: dict[int, Shadow] = {}
        self.next_label = 1
        self.last_frame: int | None = None
        self.last_time: float | None = None
        self.totals = {key: 0 for key in (
            'occluded', 'reassociated', 'expired', 'cleared_after_no_contacts',
            'cleared_on_gap', 'unqualified_loss', 'ambiguous_reassociation',
            'new_identity', 'frame_reset', 'proposed_reassociation')}

    def observe(self, frame: int, seconds: float, contacts: list[dict]) -> dict:
        """Process one timed set of *already observed* prototype contacts.

        This function does not run a detector and never produces extra contacts.
        Input dicts need id,x,y,age. Positive age must be observed in upstream
        history rather than inferred as a physical-contact ground truth.
        """
        if type(frame) is not int or frame < 0 or (self.last_frame is not None and frame <= self.last_frame):
            raise ValueError('invalid or repeated frame')
        if not isfinite(seconds) or seconds < 0 or (self.last_time is not None and seconds <= self.last_time):
            raise ValueError('nonmonotonic timestamp')
        if not isinstance(contacts, list) or len(contacts) > 48:
            raise ValueError('invalid visible count')
        parsed: dict[int, Visible] = {}
        for c in contacts:
            try:
                source, x, y, age = c['id'], c['x'], c['y'], c['age']
            except (KeyError, TypeError) as exc:
                raise ValueError('malformed contact') from exc
            if (type(source) is not int or source < 1 or source in parsed or
                    type(age) is not int or age < 1 or
                    not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or
                    not isfinite(x) or not isfinite(y) or
                    not (0 <= x < 72 and 0 <= y < 48)):
                raise ValueError('invalid contact id/position/age')
            parsed[source] = Visible(source, -1, float(x), float(y), age)
        events: list[dict] = []
        if self.last_time is not None and (seconds - self.last_time > self.cfg.gap_reset_seconds or
                                            frame - self.last_frame > 5):
            if self.shadows:
                self.totals['cleared_on_gap'] += len(self.shadows)
            self.visible.clear()
            self.shadows.clear()
            self.totals['frame_reset'] += 1
            events.append({'action':'gap_reset'})
        self.last_frame, self.last_time = frame, seconds
        for label, s in list(self.shadows.items()):
            if seconds - s.lost_at_seconds > self.cfg.ttl_seconds:
                del self.shadows[label]
                self.totals['expired'] += 1
                events.append({'action':'expired', 'label':label})
        prev = self.visible
        old_ids = set(prev)
        current_ids = set(parsed)
        gone = sorted(old_ids - current_ids)
        if not current_ids:
            self.totals['cleared_after_no_contacts'] += len(self.shadows)
            self.shadows.clear()
        elif len(prev) == 2 and len(parsed) == 1 and len(gone) == 1:
            lost = prev[gone[0]]
            anchor = next(iter(parsed.values()))
            prior_anchor = prev.get(anchor.source)
            d = hypot(lost.x - prior_anchor.x, lost.y - prior_anchor.y) if prior_anchor else float('inf')
            if (lost.age >= self.cfg.min_visible_age and prior_anchor is not None and
                    d <= self.cfg.max_merge_distance and len(self.shadows) < self.cfg.max_shadows):
                self.shadows[lost.label] = Shadow(lost.label, lost.x, lost.y, seconds, prior_anchor.label)
                self.totals['occluded'] += 1
                events.append({'action':'occluded','label':lost.label,'last_distance':round(d,3)})
            else:
                self.totals['unqualified_loss'] += 1
        else:
            self.totals['unqualified_loss'] += len(gone)
        for key in sorted(current_ids & old_ids):
            parsed[key].label = prev[key].label
        newborn = sorted(current_ids - old_ids)
        # Reassociation is only possible when 2+ *detected* contacts are on hand.
        # Never emit a shadow as a second output contact during occlusion.
        for source in newborn:
            obs = parsed[source]
            eligible = []
            if len(parsed) >= 2:
                for s in self.shadows.values():
                    anchors = [v for v in parsed.values() if v.label == s.anchor_label]
                    if len(anchors) != 1:
                        continue
                    if hypot(obs.x-anchors[0].x, obs.y-anchors[0].y) < self.cfg.min_recovery_separation:
                        continue
                    d = hypot(obs.x-s.x,obs.y-s.y)
                    if d <= self.cfg.max_recovery_distance:
                        eligible.append((d,s.label))
            eligible.sort()
            if eligible and (len(eligible)==1 or eligible[1][0]-eligible[0][0]>=self.cfg.ambiguity_margin):
                distance, label = eligible[0]
                del self.shadows[label]
                self.totals['proposed_reassociation'] += 1
                events.append({'action':'proposed_reassociation','label':label,'source':source,
                               'last_distance':round(distance,3),
                               'id_reused':self.cfg.allow_provisional_id_reuse})
                if self.cfg.allow_provisional_id_reuse:
                    obs.label = label
                    self.totals['reassociated'] += 1
                else:
                    obs.label = self.next_label
                    self.next_label += 1
                    self.totals['new_identity'] += 1
            else:
                if len(eligible)>1:
                    self.totals['ambiguous_reassociation'] += 1
                obs.label = self.next_label
                self.next_label += 1
                self.totals['new_identity'] += 1
        self.visible = parsed
        result = [{'source_id':v.source,'stable_label':v.label,'x':v.x,'y':v.y,'age':v.age}
                  for v in sorted(parsed.values(),key=lambda x:x.source)]
        assert len(result) == len(contacts) and all(v['stable_label'] > 0 for v in result)
        return {'frame':frame,'observed_contacts':result,
                'internal_shadow_count':len(self.shadows),'events':events}