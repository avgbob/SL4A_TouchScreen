# SPDX-License-Identifier: GPL-2.0
import unittest

from physical_truth_shadow_replay import (
    combine,
    guided_hold_summary,
    marker_summary,
    regions,
)
from processor import CELLS, COLS


class PhysicalTruthReplayTest(unittest.TestCase):
    def test_regions_and_combined_morphology(self):
        raster = bytearray([200] * CELLS)
        for x, y, value in ((10, 10, 100), (10, 11, 120),
                            (10, 14, 90), (11, 14, 110)):
            raster[y * COLS + x] = value
        found = regions(bytes(raster))
        self.assertEqual(len(found), 2)
        merged, morphology = combine(found)
        self.assertEqual(merged.pixels, 4)
        self.assertEqual(merged.weight, morphology.mass)
        self.assertGreater(morphology.major_variance, 1)

    def test_isolated_dark_noise_is_not_a_contact_region(self):
        raster = bytearray([200] * CELLS)
        raster[5 * COLS + 5] = 1
        self.assertEqual(regions(bytes(raster)), [])

    def test_bad_raster_rejected(self):
        with self.assertRaises(ValueError):
            regions(b'bad')

    def test_v4_markers_and_conservative_hold_summary(self):
        ticks = [10_000_000 + i * 1_000_000 for i in range(25)]
        results = [(1, 0)] * 25
        results[5:20] = [(1, 1)] * 15
        pointer = [
            {'Event': 'OPERATOR_CONFIRM_HORIZONTAL_CLOSE_BOTH_DOWN',
             'Stage': '2', 'StopwatchTicks': '10000000',
             'OperatorPhysical': '2', 'MessageActive': '1'},
            {'Event': 'GUIDED_HOLD_COMPLETE', 'Stage': '2',
             'StopwatchTicks': '30000000', 'OperatorPhysical': '2',
             'MessageActive': '1'},
            {'Event': 'OPERATOR_CONFIRM_EMPTY_FINISH', 'Stage': '18',
             'StopwatchTicks': '90000000', 'OperatorPhysical': '0',
             'MessageActive': '0'},
        ]
        markers = marker_summary(pointer, ticks, results)
        self.assertEqual(markers[0]['operator_physical'], 2)
        self.assertEqual(markers[0]['windows_at_marker'], 1)
        self.assertIsNotNone(markers[0]['nearest_raw_frame'])
        self.assertIsNone(markers[1]['nearest_raw_frame'])
        holds = guided_hold_summary(pointer, ticks, results)
        self.assertEqual(len(holds), 1)
        self.assertEqual(holds[0]['event'],
                         'OPERATOR_CONFIRM_HORIZONTAL_CLOSE_BOTH_DOWN')
        self.assertGreater(holds[0]['raw_frames'], 0)
        self.assertEqual(holds[0]['operator_physical'], 2)


if __name__ == '__main__':
    unittest.main()
