# SPDX-License-Identifier: GPL-2.0
"""Offline replay and peak experiment regression: no proprietary fixtures."""
import hashlib
import json
import csv
import io
import tempfile
import unittest
import zipfile
from math import exp
from pathlib import Path
from pinch_dataset import load_dataset, components, lobe_peaks, run
from processor import COLS, ROWS, CELLS


class PublicPinchReplayTest(unittest.TestCase):
    def make_dataset(self, path, *, corrupt=False, broken_clock=False):
        all_frames = bytes([180] * CELLS) * 35
        sha = hashlib.sha256(all_frames).hexdigest()
        metadata = {'frame_count':35, 'frame_width':COLS, 'frame_height':ROWS,
                    'raster_bytes_per_frame':CELLS, 'dtype':'uint8',
                    'raster_concatenated_sha256':('0'*64 if corrupt else sha)}
        times = io.StringIO()
        writer=csv.writer(times)
        writer.writerow(['frame_index','relative_wpr_ticks_at_10mhz'])
        for i in range(35):
            writer.writerow([i,(i*100000 if not broken_clock or i!=32 else 100)])
        events = 'relative_seconds_from_first_pointer_down,record_kind\n0,DOWN\n0.2,M_TWO_PHYSICAL_ONE_REPORTED\n'
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('metadata.json',json.dumps(metadata))
            z.writestr('heatmaps_u8.bin',all_frames)
            z.writestr('frame_relative_ticks.csv',times.getvalue())
            z.writestr('os_contact_transitions_relative.csv',events)

    def test_valid_replay_and_expected_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.zip';self.make_dataset(p)
            r=run(p,full_replay=True)
            self.assertEqual(r['frames'],35)
            self.assertEqual(r['operator_markers'],1)
            self.assertEqual(r['prototype_replay']['processed'],35)
            self.assertEqual(r['prototype_replay']['candidate_count_histogram'][0],35)
            self.assertEqual(r['prototype_replay']['tracker_reset_on_200ms_real_capture_gap'],0)

    def test_corrupt_sha_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.zip';self.make_dataset(p,corrupt=True)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                load_dataset(p)

    def test_nonmonotonic_times_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'clock.zip';self.make_dataset(p,broken_clock=True)
            with self.assertRaisesRegex(ValueError, 'non-monotonic'):
                load_dataset(p)

    def test_two_lobes_from_one_connected_blob(self):
        raster=bytearray([180] * CELLS)
        # Two Gaussians with a shared threshold-connected base. A simple
        # region detector sees one blob; smoothed local peaks detect two.
        for y in range(ROWS):
            for x in range(COLS):
                d1=(x-29)**2+(y-22)**2
                d2=(x-35)**2+(y-22)**2
                signal=round(110*exp(-d1/14)+110*exp(-d2/14))
                raster[y*COLS+x]=max(0,180-signal)
        regions=components(raster,150)
        peaks=lobe_peaks(raster,minimum_smoothed_depth=10)
        self.assertEqual(len(regions),1)
        self.assertEqual(len(peaks),2)
        self.assertEqual([p['x'] for p in peaks],[30,34])

    def test_single_peak_does_not_fabricate_second_finger(self):
        raster=bytearray([180] * CELLS)
        for y in range(ROWS):
            for x in range(COLS):
                raster[y*COLS+x]=max(0,180-round(110*exp(-((x-33)**2+(y-22)**2)/14)))
        self.assertEqual(len(components(raster,150)),1)
        self.assertEqual(len(lobe_peaks(raster)),1)


if __name__ == '__main__':
    unittest.main()