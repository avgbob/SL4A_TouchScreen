# SPDX-License-Identifier: GPL-2.0
import math
import unittest

from calibrate_pointer_oracle import (
    fit_affine,
    lower_cost_pairing,
    statistics,
    transform,
)


class CalibratePointerOracleTest(unittest.TestCase):
    def test_exact_general_affine_fit(self):
        pairs = []
        for x, y in ((0, 0), (10, 0), (0, 20), (7, 11), (-4, 6)):
            pairs.append((x, y, 2 * x + 3 * y + 4,
                          -x + .5 * y - 2))
        matrix = fit_affine(pairs)
        self.assertEqual(len(matrix), 2)
        for x, y, expected_x, expected_y in pairs:
            actual_x, actual_y = transform(matrix, x, y)
            self.assertAlmostEqual(actual_x, expected_x)
            self.assertAlmostEqual(actual_y, expected_y)

    def test_singular_fit_rejected(self):
        with self.assertRaisesRegex(ValueError, 'singular'):
            fit_affine([(0, 0, 0, 0), (1, 1, 1, 1), (2, 2, 2, 2)])

    def test_two_by_two_assignment_uses_geometry_not_input_order(self):
        errors = lower_cost_pairing([(0, 0), (10, 10)],
                                    [(10.1, 10), (.1, 0)])
        self.assertAlmostEqual(errors[0], .1)
        self.assertAlmostEqual(errors[1], .1)

    def test_statistics(self):
        result = statistics([0, 1, 2, 3])
        self.assertEqual(result['samples'], 4)
        self.assertEqual(result['median_cells'], 2)
        self.assertAlmostEqual(result['rmse_cells'], math.sqrt(3.5), places=6)
        self.assertEqual(statistics([]), {'samples': 0})


if __name__ == '__main__':
    unittest.main()
