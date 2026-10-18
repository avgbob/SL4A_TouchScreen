# SPDX-License-Identifier: GPL-2.0
"""Independent offline guardrails for temporary *internal-only* occlusion memory."""
import unittest

from shadow_tracker import ShadowConfig, ShadowOverlay


def c(cid,x,y,age=5):
    return {'id':cid,'x':x,'y':y,'age':age}


class ShadowTrackerTest(unittest.TestCase):
    def test_close_occlusion_reassociates_only_when_real_second_contact_exists(self):
        s=ShadowOverlay(ShadowConfig(allow_provisional_id_reuse=True))
        a=s.observe(0,0,[c(1,11,12),c(2,15,12)])
        original={i['source_id']:i['stable_label'] for i in a['observed_contacts']}
        during=s.observe(1,.01,[c(1,12,12)])
        self.assertEqual(len(during['observed_contacts']),1)
        self.assertEqual(during['internal_shadow_count'],1)
        self.assertEqual(during['events'][0]['action'],'occluded')
        again=s.observe(2,.02,[c(1,12,12),c(3,15,12)])
        mapped={i['source_id']:i['stable_label'] for i in again['observed_contacts']}
        self.assertEqual(mapped[3],original[2])
        self.assertEqual(s.totals['reassociated'],1)

    def test_default_only_proposes_but_never_reuses_identity(self):
        s=ShadowOverlay()
        start=s.observe(0,0,[c(1,10,10),c(2,14,10)])
        lost_label=start['observed_contacts'][1]['stable_label']
        s.observe(1,.01,[c(1,11,10)])
        returned=s.observe(2,.02,[c(1,11,10),c(3,14,10)])
        self.assertNotEqual(returned['observed_contacts'][1]['stable_label'],lost_label)
        self.assertEqual(s.totals['proposed_reassociation'],1)
        self.assertEqual(s.totals['reassociated'],0)
        self.assertFalse(returned['events'][0]['id_reused'])

    def test_adversarial_genuine_lift_then_new_touch_same_place(self):
        # This sequence is physically INDETERMINATE without synchronized ground truth.
        # The conservative default must not silently stitch IDs across it.
        s=ShadowOverlay()
        start=s.observe(0,0,[c(1,10,10),c(2,14,10)])
        s.observe(1,.01,[c(1,11,10)])  # finger 2 genuinely lifts
        new=s.observe(2,.02,[c(1,11,10),c(3,14,10)])  # DIFFERENT finger touches
        self.assertEqual(len(new['observed_contacts']),2)
        self.assertNotEqual(new['observed_contacts'][1]['stable_label'],start['observed_contacts'][1]['stable_label'])
        self.assertEqual(s.totals['proposed_reassociation'],1)  # a potential FALSE POSITIVE
        self.assertEqual(s.totals['reassociated'],0)

    def test_no_ghost_contact_after_close_independent_lift(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,11,12),c(2,14,12)])
        released=s.observe(1,.01,[c(1,11,12)])
        self.assertEqual(len(released['observed_contacts']),1)
        for i in range(2,70):
            r=s.observe(i,i/100,[c(1,11,12)])
            self.assertEqual(len(r['observed_contacts']),1)
        self.assertEqual(r['internal_shadow_count'],0)
        self.assertEqual(s.totals['reassociated'],0)
        self.assertEqual(s.totals['expired'],1)

    def test_wide_independent_lift_cannot_be_marked_occlusion(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,5,5),c(2,50,35)])
        s.observe(1,.01,[c(1,5,5)])
        self.assertEqual(s.totals['occluded'],0)

    def test_new_far_away_contact_is_never_reassigned(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,10,10),c(2,14,10)])
        s.observe(1,.01,[c(1,11,10)])
        r=s.observe(2,.02,[c(1,11,10),c(3,42,41)])
        self.assertEqual(r['internal_shadow_count'],1)
        self.assertEqual(s.totals['reassociated'],0)

    def test_proximity_to_anchor_required(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,10,10),c(2,13,10)])
        s.observe(1,.01,[c(1,11,10)])
        r=s.observe(2,.02,[c(1,12,10),c(3,12.2,10)])
        self.assertEqual(s.totals['reassociated'],0)
        self.assertEqual(len(r['observed_contacts']),2)

    def test_zero_contacts_clears_stale_shadow(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,11,12),c(2,14,12)])
        s.observe(1,.01,[c(1,11,12)])
        r=s.observe(2,.02,[])
        self.assertEqual(r['internal_shadow_count'],0)
        n=s.observe(3,.03,[c(3,14,12)])
        self.assertEqual(n['internal_shadow_count'],0)
        self.assertEqual(s.totals['reassociated'],0)

    def test_time_gap_clears_on_resume(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,11,12),c(2,14,12)])
        s.observe(1,.01,[c(1,11,12)])
        r=s.observe(2,.25,[c(1,11,12),c(3,14,12)])
        self.assertEqual(r['internal_shadow_count'],0)
        self.assertEqual(s.totals['frame_reset'],1)
        self.assertEqual(s.totals['reassociated'],0)

    def test_missed_frame_index_clears_before_reassociation(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,11,12),c(2,14,12)])
        s.observe(1,.01,[c(1,11,12)])
        s.observe(8,.02,[c(1,11,12),c(3,14,12)])
        self.assertEqual(s.totals['frame_reset'],1)
        self.assertEqual(s.totals['reassociated'],0)

    def test_identity_age_gate_and_unqualified_older_loss(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,11,12,5),c(2,14,12,1)])
        r=s.observe(1,.01,[c(1,11,12,6)])
        self.assertEqual(r['internal_shadow_count'],0)
        self.assertEqual(s.totals['unqualified_loss'],1)

    def test_reject_invalid_data_without_state_mutation(self):
        s=ShadowOverlay()
        s.observe(0,0,[c(1,5,5)])
        for frame,t,records in [(1,.01,[c(1,float('nan'),5)]),
                                (0,.02,[c(1,5,5)]),
                                (1,-1,[c(1,5,5)]),
                                (1,.01,[c(1,5,5),c(1,6,6)])]:
            with self.assertRaises(ValueError):
                s.observe(frame,t,records)
        self.assertEqual(s.visible[1].x,5)
        self.assertEqual(s.last_frame,0)
        self.assertEqual(s.last_time,0)
        s.observe(1,.01,[c(1,5,5)])

    def test_shadow_memory_bounded_and_labels_not_source_id(self):
        s=ShadowOverlay(ShadowConfig(max_shadows=1))
        a=s.observe(0,0,[c(101,10,10),c(220,14,10)])
        self.assertEqual([x['stable_label'] for x in a['observed_contacts']],[1,2])
        s.observe(1,.01,[c(101,11,10)])
        self.assertEqual(len(s.shadows),1)
        r=s.observe(2,.02,[c(101,11,10),c(400,25,25)])
        self.assertEqual(r['observed_contacts'][1]['stable_label'],3)

    def test_no_reassociate_after_ttl(self):
        s=ShadowOverlay(ShadowConfig(ttl_seconds=.05))
        s.observe(0,0,[c(1,11,12),c(2,14,12)])
        s.observe(1,.01,[c(1,11,12)])
        s.observe(2,.04,[c(1,11,12)])
        r=s.observe(3,.08,[c(1,11,12),c(3,14,12)])
        self.assertEqual(s.totals['reassociated'],0)
        self.assertEqual(s.totals['expired'],1)
        self.assertEqual(len(r['observed_contacts']),2)


if __name__=='__main__':
    unittest.main()