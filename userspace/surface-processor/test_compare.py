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

    def test_requires_complete_reference_coverage(self):
        a = {1: [contact(1, 10, 10)], 2: [contact(1, 10, 10)]}
        b = {1: [contact(1, 10, 10)]}
        with self.assertRaisesRegex(ValueError, 'coverage mismatch'):
            compare(a, b)
        r = compare(a, b, allow_partial=True)
        self.assertFalse(r['coverage_complete'])
        self.assertEqual(r['reference_only_frames'], 1)

    def test_rejects_nan_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            compare({1: [contact(1, float('nan'), 1)]}, {1: []})
        with self.assertRaises(ValueError):
            compare({1: [contact(1, 1, 1), contact(1, 3, 4)]}, {1: []})

    def test_invalid_reference(self):
        with self.assertRaises(ValueError):
            compare({1: []}, {2: []})
        with self.assertRaises(ValueError):
            compare({1: []}, {1: []}, max_distance=float('nan'))

    def test_general_reference_affine(self):
        reference = {1: [contact('windows', 10, 20)]}
        experiment = {1: [contact('linux', 25, 3)]}
        # x' = 2*x + 0*y + 5; y' = 0*x + .25*y - 2
        affine = [[2, 0, 5], [0, .25, -2]]
        result = compare(reference, experiment, affine=affine)
        self.assertEqual(result['matched_contacts'], 1)
        self.assertEqual(result['max_grid_error'], 0)

    def test_affine_validation_and_scale_exclusion(self):
        reference = {1: []}
        with self.assertRaisesRegex(ValueError, '2x3'):
            compare(reference, reference, affine=[[1, 2]])
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            compare(reference, reference,
                    affine=[[1, 0, float('nan')], [0, 1, 0]])
        with self.assertRaisesRegex(ValueError, 'mutually exclusive'):
            compare(reference, reference,
                    affine=[[1, 0, 0], [0, 1, 0]], scale_x=2)


if __name__ == '__main__':
    unittest.main(verbosity=2)

# Test discovery intentionally uses unittest; additional edge-case coverage.
class FileValidationTest(unittest.TestCase):
    def test_jsonl_duplicate_frame_and_nonfinite(self):
        import tempfile
        from pathlib import Path
        from compare import read_jsonl
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'ref.jsonl'
            p.write_text('{"frame":1,"contacts":[]}\n{"frame":1,"contacts":[]}\n')
            with self.assertRaisesRegex(ValueError, 'duplicate/invalid frame'):
                read_jsonl(p)
            p.write_text('{"frame":1,"contacts":[{"id":1,"x":NaN,"y":2}]}\n')
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                read_jsonl(p)
