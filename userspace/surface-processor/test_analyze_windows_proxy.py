# SPDX-License-Identifier: GPL-2.0
import json
import tempfile
import unittest
from pathlib import Path

from analyze_windows_proxy import sensor_regions, summarize
from processor import CELLS
from test_processor import v0_frame, raster_at


class RawRegionProxyTest(unittest.TestCase):
    def test_no_regions_idle(self):
        self.assertEqual(sensor_regions(bytes([180] * CELLS)), [])

    def test_two_regions_and_merging(self):
        two = raster_at((8, 7), (40, 25))
        self.assertEqual(len(sensor_regions(two)), 2)
        merged = raster_at((8, 7), (10, 7))
        self.assertEqual(len(sensor_regions(merged)), 1)

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            sensor_regions(b'incomplete')

    def test_summary_uses_only_tracking_for_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sample = (v0_frame(bytes([180] * CELLS)) + b'\x00\x00').hex()
            (root / 'frames.txt').write_text(sample + '\n' + sample + '\n')
            (root / 'processed.jsonl').write_text('\n'.join([
                json.dumps({'frame':0,'stage':'baseline','contacts':[],'candidates':[]}),
                json.dumps({'frame':1,'stage':'tracking','contacts':[],'candidates':[]}),
            ]) + '\n')
            report = summarize(root / 'frames.txt', root / 'processed.jsonl')
            self.assertEqual(report['frames'], 2)
            self.assertEqual(report['counts']['tracking_frames'], 1)
            self.assertEqual(report['candidate_versus_raw_proxy']['equal_frames'], 1)
            self.assertIn('NOT Windows', report['warning'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
