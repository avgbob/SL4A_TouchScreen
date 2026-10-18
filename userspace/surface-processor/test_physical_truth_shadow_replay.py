# SPDX-License-Identifier: GPL-2.0
import unittest

from physical_truth_shadow_replay import combine, regions
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


if __name__ == '__main__':
    unittest.main()
