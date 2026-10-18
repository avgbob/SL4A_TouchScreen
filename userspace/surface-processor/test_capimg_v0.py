# SPDX-License-Identifier: GPL-2.0
"""Focused contract tests for the strict CapImg V0 decoder."""
from struct import pack, pack_into
from pathlib import Path
import unittest

from capimg_v0 import CELLS, decode_frame


def v0_frame(raster: bytes) -> bytes:
    section = pack('<IHBBII', 16 + CELLS, 0x100, 1, 8, 0, CELLS) + raster
    vendor = pack('<IHB', 818, 0xff00, 0) + bytes(811)
    payload = pack('<IHB', 7 + len(section) + len(vendor), 0, 0) + section + vendor
    body = b'\xce\x10\x0c\x00\x00' + payload
    if not 4300 <= len(body) <= 4400:
        raise AssertionError('test fixture has wrong V0 length')
    return body


class CapImgV0Test(unittest.TestCase):
    def setUp(self):
        self.raster = bytes(range(256)) * 13 + bytes(range(128))
        self.body = v0_frame(self.raster)

    def test_all_observed_envelopes(self):
        self.assertEqual(decode_frame(self.raster), self.raster)
        self.assertEqual(decode_frame(self.body), self.raster)
        self.assertEqual(decode_frame(b'\xff' * 5 + self.body), self.raster)
        self.assertEqual(decode_frame(self.body[2:]), self.raster)

    def test_all_eight_tracked_hardware_fixtures(self):
        root = Path(__file__).parents[2]
        fixtures = sorted((root / 'captures' / 'id5-20260718' / 'frames').glob(
            'raw-slot-*.v0'))
        self.assertEqual(len(fixtures), 8)
        bodies = [path.read_bytes() for path in fixtures]
        rasters = [decode_frame(body) for body in bodies]
        self.assertEqual(len(set(bodies)), 8)
        self.assertTrue(all(len(raster) == CELLS for raster in rasters))
        # These eight transport bodies differ outside the heatmap; their idle
        # rasters are intentionally allowed to be identical.

    def test_rejects_bad_container_and_section_lengths(self):
        bad_container = bytearray(self.body)
        pack_into('<I', bad_container, 5, 0xffffffff)
        with self.assertRaisesRegex(ValueError, 'container header'):
            decode_frame(bytes(bad_container))

        bad_section = bytearray(self.body)
        pack_into('<I', bad_section, 12, 6)
        with self.assertRaisesRegex(ValueError, 'section length'):
            decode_frame(bytes(bad_section))

    def test_rejects_missing_or_duplicate_required_sections(self):
        missing_vendor = bytearray(self.body)
        pack_into('<H', missing_vendor, 12 + 16 + CELLS + 4, 0x2222)
        with self.assertRaisesRegex(ValueError, 'missing required'):
            decode_frame(bytes(missing_vendor))

        duplicate_heatmap = bytearray(self.body)
        vendor_offset = 12 + 16 + CELLS
        pack_into('<H', duplicate_heatmap, vendor_offset + 4, 0x100)
        with self.assertRaisesRegex(ValueError, 'heatmap'):
            decode_frame(bytes(duplicate_heatmap))

    def test_rejects_ambiguous_or_wrong_types(self):
        with self.assertRaisesRegex(ValueError, 'not a supported'):
            decode_frame(b'\x0c' * 10)
        with self.assertRaises(TypeError):
            decode_frame(bytearray(self.body))


if __name__ == '__main__':
    unittest.main()
