# SPDX-License-Identifier: GPL-2.0
"""Regression for behavioral clock offsets, merge flicker and no-ghost policy."""
import unittest

from pinch_transition_audit import (CONTROL_EVENT_SPECS, align_controls,
                                    last_collapse, rolling_majority,
                                    stable_transitions, count_sensor_regions,
                                    weak_peak_controls)
from processor import CELLS


class TransitionAuditTest(unittest.TestCase):
    def test_region_count_from_true_sensor_rasters(self):
        one=bytearray([180]*CELLS)
        for off in (5+5*72,6+5*72,5+6*72,6+6*72):one[off]=80
        two=bytearray(one)
        for off in (45+35*72,46+35*72,45+36*72):two[off]=100
        result=count_sensor_regions(bytes(one+two),2)
        self.assertEqual(result,[1,2])

    def test_smooth_ignores_short_noise_and_is_monotone(self):
        counts=[1]*40+[2]*60+[1]*40
        counts[45]=1 # a single noisy frame must not create an extra transition
        times=[i*.01 for i in range(len(counts))]
        s=rolling_majority(counts)
        transitions=stable_transitions(times,s)
        self.assertEqual([(q['before'],q['after']) for q in transitions],[(1,2),(2,1)])
        self.assertLessEqual(abs(transitions[0]['raw_relative_seconds']-.40),.011)
        self.assertLessEqual(abs(transitions[1]['raw_relative_seconds']-1.00),.011)
        with self.assertRaisesRegex(ValueError,'monotonic'):
            stable_transitions([1.,1.],[1,2])
        with self.assertRaises(ValueError):
            rolling_majority([1,2,1],width=2)

    def test_control_based_offset_has_no_pinch_events(self):
        rows=[];changes=[]
        for idx,(_,kind,cid,before,after) in enumerate(CONTROL_EVENT_SPECS):
            t=idx*20.+10.
            rows.append({'record_kind':kind,'anonymous_contact':cid,
                         'relative_seconds_from_first_pointer_down':str(t)})
            changes.append({'before':before,'after':after,
                            'raw_relative_seconds':round(t+.06,6)})
        results=align_controls(rows,changes)
        self.assertEqual(results['controls_found'],4)
        self.assertAlmostEqual(results['median_raw_minus_os_seconds'],.06)
        self.assertIn('not independent', results['timing_caveat'].lower())
        self.assertIsNone(align_controls(rows,[],search_seconds=.35)['median_raw_minus_os_seconds'])
        with self.assertRaisesRegex(ValueError,'control'):
            align_controls(rows[:-1],changes)

    def test_brief_reappearance_is_one_merge_episode(self):
        raw=[{'before':2,'after':1,'raw_relative_seconds':4.0},
             {'before':1,'after':2,'raw_relative_seconds':4.5},
             {'before':2,'after':1,'raw_relative_seconds':4.58}]
        c,f=last_collapse(raw,4.9)
        self.assertEqual(c['raw_relative_seconds'],4.)
        self.assertEqual(len(f),1)
        self.assertAlmostEqual(f[0]['duration_seconds'],.08)
        longer=[raw[0],raw[1],{'before':2,'after':1,'raw_relative_seconds':4.85}]
        c,f=last_collapse(longer,4.9)
        self.assertEqual(c['raw_relative_seconds'],4.85)
        self.assertEqual(f,[])
        self.assertEqual(last_collapse([],4.9),(None,[]))

    def test_lift_policy_is_explicitly_not_contact_injection(self):
        # Evaluation code reports only evidence. It does not publish a second
        # pointer/track or change the processor, even if raw briefly merges.
        import inspect
        import pinch_transition_audit
        self.assertNotIn('uinput', inspect.getsource(pinch_transition_audit).lower())
        self.assertNotIn('emit_touch', inspect.getsource(pinch_transition_audit).lower())


if __name__=='__main__':
    unittest.main(verbosity=2)