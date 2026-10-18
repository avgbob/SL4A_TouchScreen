# SPDX-License-Identifier: GPL-2.0
import unittest

from guided_hold_compare import compare_holds


def frame(index, count, hold=None):
    return {'frame': index,
            'contacts': [{'id': item, 'x': item, 'y': item}
                         for item in range(count)],
            'guided_hold': hold}


class GuidedHoldCompareTest(unittest.TestCase):
    def test_aggregates_only_conservative_frames(self):
        conservative = {'stage': 2, 'event': 'CLOSE',
                        'physical_contacts': 2, 'conservative': True}
        edge = {**conservative, 'conservative': False}
        reference = [frame(0, 2, conservative), frame(1, 2, conservative),
                     frame(2, 1, edge)]
        experiment = [frame(0, 1), frame(1, 2), frame(2, 0)]
        result = compare_holds(reference, experiment)
        self.assertEqual(result['conservative_frames'], 2)
        self.assertEqual(result['exact_count_frames'], 1)
        self.assertEqual(result['exact_count_fraction'], .5)
        self.assertEqual(result['holds'][0]['count_pairs'], {
            'windows_2_prototype_1': 1,
            'windows_2_prototype_2': 1,
        })

    def test_rejects_coverage_mismatch_and_missing_holds(self):
        with self.assertRaisesRegex(ValueError, 'coverage mismatch'):
            compare_holds([frame(0, 0)], [])
        with self.assertRaisesRegex(ValueError, 'no conservative'):
            compare_holds([frame(0, 0)], [frame(0, 0)])


if __name__ == '__main__':
    unittest.main()
