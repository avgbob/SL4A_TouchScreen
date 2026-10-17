# SPDX-License-Identifier: GPL-2.0
"""Ground-truth comparison regression checks."""
import unittest
from compare import compare


def contact(i, x, y):
    return {'id': i, 'x': x, 'y': y}


class CompareTest(unittest.TestCase):
    def test_matching_count_error_and_ids(self):
        reference = {1: [contact('a', 10, 11), contact('b', 30, 12)],
                     2: [contact('a', 11, 11), contact('b', 31, 12)]}
        experiment = {1: [contact(1, 10.3, 11), contact(2, 30, 12)],
                      2: [contact(2, 11, 11), contact(3, 31, 12)]}
        r = compare(reference, experiment)
        self.assertEqual(r['matched_contacts'], 4)
        self.assertEqual(r['tracking_id_switches'], 2)
        self.assertEqual(r['missed_contacts'], 0)
        self.assertAlmostEqual(r['max_grid_error'], .3)

    def test_false_positive_and_missing(self):
        a = {1: [contact(5, 15, 15), contact(6, 30, 30)]}
        b = {1: [contact(1, 15, 15), contact(2, 5, 5)]}
        r = compare(a, b)
        self.assertEqual(r['matched_contacts'], 1)
        self.assertEqual(r['missed_contacts'], 1)
        self.assertEqual(r['extra_contacts'], 1)

    def test_invalid_reference(self):
        with self.assertRaises(ValueError):
            compare({1: []}, {2: []})
        with self.assertRaises(ValueError):
            compare({1: []}, {1: []}, max_distance=float('nan'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
