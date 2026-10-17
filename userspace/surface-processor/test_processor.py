# SPDX-License-Identifier: GPL-2.0
"""Offline regression tests: capture format, boundaries, assignment, IDs."""
import unittest
from struct import pack
from processor import (CELLS, COLS, Config, Candidate, Processor, Tracker,
                       Signal, Detector, assignment, decode_frame, c590)


def v0_frame(raster):
    section = pack('<IHBBII', 16 + CELLS, 0x100, 1, 8, 0, CELLS) + raster
    vendor = pack('<IHB', 818, 0xff00, 0) + bytes(811)
    payload = pack('<IHB', 7 + len(section) + len(vendor), 0, 0) + section + vendor
    body = b'\xce\x10\x0c\x00\x00' + payload
    assert 4300 <= len(body) <= 4400
    return body


def raster_at(*points):
    r = bytearray([180] * CELLS)
    for x, y in points:
        for dx, dy, byte in ((0, 0, 40), (-1, 0, 80), (1, 0, 80),
                             (0, -1, 80), (0, 1, 80)):
            r[(y + dy) * COLS + x + dx] = byte
    return bytes(r)


def cand(x, y):
    return Candidate(x, y, 2000, 5, 800)


class DecoderTest(unittest.TestCase):
    def test_v0_and_spb(self):
        raster = bytes(range(256)) * 13 + bytes(range(128))  # 3456
        body = v0_frame(raster)
        self.assertEqual(decode_frame(body), raster)
        self.assertEqual(decode_frame(b'\xff' * 5 + body), raster)
        self.assertEqual(decode_frame(body[2:]), raster)  # hidraw 0c + content
        self.assertEqual(decode_frame(raster), raster)

    def test_corrupt_section_rejected(self):
        data = bytearray(v0_frame(bytes([180] * CELLS)))
        data[16] = 0xff  # break section header
        with self.assertRaises(ValueError):
            decode_frame(bytes(data))
        with self.assertRaises(ValueError):
            decode_frame(b'\x0c' * 10)

    def test_c590(self):
        self.assertEqual(c590(0), 4000)
        self.assertEqual(c590(255), 0)
        self.assertLessEqual(c590(180), 4)


class TrackerTest(unittest.TestCase):
    def test_hungarian_global_optimum(self):
        # Greedy chooses 0->0 and strands 1; global solution swaps assignments.
        self.assertEqual(assignment([[1, 2], [1.1, 100]]), [1, 0])

    def test_close_contacts_retained_as_records(self):
        tracker = Tracker(Config(birth_frames=1, association_scale=10))
        contacts, _ = tracker.update(1, [cand(10, 10), cand(13, 10)])
        self.assertEqual(len(contacts), 2)
        self.assertEqual(len({c.id for c in contacts}), 2)
        self.assertEqual({c.status for c in contacts}, {7})
        self.assertEqual(len({c.group for c in contacts}), 1)
        for _ in range(2, 6):
            contacts, _ = tracker.update(_, [cand(10, 10), cand(13, 10)])
        self.assertEqual(sorted(c.id for c in contacts), [1, 2])
        self.assertTrue(all(len(t.history) == 5 for t in tracker.tracks.values()))

    def test_strict_coalesce_boundary(self):
        tracker = Tracker(Config(birth_frames=1))
        contacts, _ = tracker.update(0, [cand(5, 10), cand(11, 10)])
        self.assertEqual([c.status for c in contacts], [1, 1])
        self.assertEqual(len({c.group for c in contacts}), 2)

    def test_gap_forces_reset(self):
        tracker = Tracker(Config(birth_frames=1))
        a, _ = tracker.update(2, [cand(15, 15)])
        b, reset = tracker.update(9, [cand(15, 15)])
        self.assertTrue(reset)
        self.assertNotEqual(a[0].id, b[0].id)
        self.assertEqual(len(tracker.tracks), 1)

    def test_lift_and_debounce(self):
        t = Tracker(Config(birth_frames=3, hold_frames=1))
        self.assertEqual(t.update(0, [cand(10, 10)])[0], [])
        self.assertEqual(t.update(1, [cand(10, 10)])[0], [])
        self.assertEqual(len(t.update(2, [cand(10, 10)])[0]), 1)
        self.assertEqual(t.update(3, [])[0], [])
        self.assertEqual(len(t.tracks), 1)
        self.assertEqual(t.update(4, [])[0], [])
        self.assertEqual(len(t.tracks), 0)
        with self.assertRaises(ValueError):
            t.update(4, [])


class PipelineTest(unittest.TestCase):
    def test_synthetic_two_fingers(self):
        p = Processor(Config(association_scale=10, birth_frames=1))
        idle = bytes([180] * CELLS)
        for i in range(30):
            self.assertEqual(p.process(i, idle)['stage'], 'baseline')
        result = p.process(30, raster_at((14, 15), (45, 20)))
        self.assertEqual(result['stage'], 'tracking')
        self.assertEqual(len(result['candidates']), 2)
        self.assertEqual(len(result['contacts']), 2)
        self.assertEqual(result['track_count'], 2)
        self.assertEqual(p.process(31, idle)['contacts'], [])

    def test_malformed_rejected_without_state_mutation(self):
        p = Processor()
        with self.assertRaises(ValueError):
            p.process(0, b'bad')
        self.assertEqual(p.signal.frames, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
