#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Synthetic Windows pointer / human annotation regression, no hardware."""
from __future__ import annotations
import unittest
from datetime import datetime,timedelta,timezone
from analyze_physical_truth import evaluate

T=datetime(2026,10,17,22,0,0,tzinfo=timezone.utc)

def ts(offset):
    return (T+timedelta(seconds=offset)).isoformat()

def mark(t,kind,physical,n=1):
    return {"Utc":ts(t),"Event":kind,"OperatorPhysical":str(physical),
            "MessageActive":str(n),"Stage":"3"}

def sample(t,reported):
    return {"Utc":ts(t),"MessageActive":str(reported),"Stage":"4"}

class PhysicalTruthTest(unittest.TestCase):
    def test_deliberate_lift_vs_close_occlusion(self):
        # BOTH down but second OS ID lost; then REAL lift -> OS count 1 correct;
        # then NEW second finger returns; then both OFF must show OS count 0.
        events=[mark(0,"OPERATOR_BOTH_DOWN",2,2),
                mark(4,"OPERATOR_BOTH_STILL_DOWN",2,1),
                mark(7,"OPERATOR_SECOND_INTENTIONALLY_LIFTED",1,1),
                mark(11,"OPERATOR_SECOND_RETURNED",2,2),
                mark(15,"OPERATOR_BOTH_LIFTED",0,0)]
        s=[]
        for i in range(160):
            t=i/10
            n=2 if (t<2 or 11<=t<15) else (1 if 2<=t<11 else 0)
            s.append(sample(t,n))
        r=evaluate(events,s)
        self.assertGreater(r['totals']['two_physical_one_windows_samples'],0)
        self.assertEqual(r['totals'].get('one_physical_two_plus_windows_samples',0),0)
        self.assertEqual(r['totals'].get('zero_physical_nonzero_windows_samples',0),0)
        self.assertGreaterEqual(r['totals']['intervals_with_sustained_mismatch'],1)
    def test_ghost_after_real_lift(self):
        e=[mark(0,"OPERATOR_BOTH_DOWN",2,2),mark(1,"OPERATOR_SECOND_INTENTIONALLY_LIFTED",1,2),mark(3,"OPERATOR_BOTH_LIFTED",0,1)]
        samples=[sample(i/10,2 if i<30 else 1) for i in range(40)]
        r=evaluate(e,samples)
        self.assertGreater(r['totals']['one_physical_two_plus_windows_samples'],0)
        self.assertGreater(r['totals']['zero_physical_nonzero_windows_samples'],0)
    def test_correction_discards_prior_interval_without_erasing_log(self):
        e=[mark(0,'OPERATOR_BOTH_DOWN',2),mark(1,'OPERATOR_ANNOTATION_INVALIDATED',-1),mark(2,'OPERATOR_SECOND_INTENTIONALLY_LIFTED',1)]
        s=[sample(i/10,1) for i in range(31)]
        r=evaluate(e,s)
        self.assertEqual(r['corrected_intervals_excluded'],1)
        self.assertEqual(len(r['stage_intervals']),1)
        self.assertEqual(r['stage_intervals'][0]['physical'],1)
    def test_invalid_timestamps_and_inconsistent_markers_rejected(self):
        with self.assertRaisesRegex(ValueError,'timezone'):
            evaluate([{"Utc":"2026-10-17T20:00:00", "Event":"OPERATOR_BOTH_DOWN","OperatorPhysical":"2","MessageActive":"2"}],[sample(0,2)])
        with self.assertRaisesRegex(ValueError,'inconsistent'):
            evaluate([mark(0,"OPERATOR_BOTH_DOWN",1)],[sample(.5,1)])
    def test_unknown_no_manual_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError,'no V3'):
            evaluate([mark(0,"DOWN",-1)],[sample(.5,1)])
    def test_zero_samples_during_silent_touch_interval(self):
        e=[mark(0,"OPERATOR_BOTH_DOWN",2),mark(.1,"OPERATOR_BOTH_LIFTED",0)]
        s=[sample(0,2),sample(.09,2),sample(.2,0)]
        r=evaluate(e,s)
        self.assertEqual(r['totals'].get('samples_evaluated',0),0)

if __name__=='__main__':unittest.main()