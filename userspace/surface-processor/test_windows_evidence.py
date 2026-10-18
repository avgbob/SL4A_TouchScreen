# SPDX-License-Identifier: GPL-2.0
"""Windows ETW extractor regression tests (no proprietary fixture required)."""
import csv
import tempfile
import unittest
from pathlib import Path
from test_processor import v0_frame
from processor import CELLS
from windows_evidence import extract, main


class WindowsEvidenceTest(unittest.TestCase):
    def sample(self, path, *, padded=True, chunks=False, bad=False):
        rows = []
        def add(event, act='ACTIVITY-ONE', clock='123456', direction='', data=''):
            r = [''] * 22
            r[0] = 'Microsoft-Windows-SPB-ClassExtension'
            r[1] = event
            r[14], r[16], r[20], r[21] = act, clock, direction, data
            rows.append(r)
        add('IoSpbPayloadStart')
        add('IoSpbPayloadTdStart', direction='"ToDevice "')
        # A TX body is not an RX and must not be mistakenly accepted.
        add('IoSpbPayloadTdBuffer', data='0x' + (v0_frame(bytes([180] * CELLS)) + b'\x00\x00').hex())
        add('IoSpbPayloadTdStart', direction='"FromDevice "')
        body = (b'\xff'*5 if padded else b'') + v0_frame(bytes([180] * CELLS)) + b'\x00\x00'
        if bad:
            body = body[:-3]
        if chunks:
            add('IoSpbPayloadTdBuffer', data='0x' + body[:900].hex())
            add('IoSpbPayloadTdBuffer', data='0x' + body[900:].hex())
        else:
            add('IoSpbPayloadTdBuffer', data='0x' + body.hex())
        add('IoSpbPayloadStop')
        with path.open('w', encoding='latin-1', newline='') as f:
            w = csv.writer(f)
            w.writerows(rows)

    def test_padded_and_chunked(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'test_trace.csv'
            self.sample(p, chunks=True)
            records, report = extract(p)
            self.assertEqual(report['decoded_capimg_frames'], 1)
            self.assertEqual(len(records[0]['_body']), 4304)
            self.assertEqual(records[0]['clock_100ns'], '123456')
            self.assertEqual(report['processed_touch_provider_probe'], {})
            self.assertEqual(report['errors'], {})

    def test_unpadded(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'raw.csv'
            self.sample(p, padded=False)
            self.assertEqual(len(extract(p)[0]), 1)

    def test_invalid_body_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'raw.csv'
            self.sample(p, bad=True)
            self.assertEqual(extract(p)[0], [])

    def test_cli_manifest_and_hex_replay(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'raw.csv'
            self.sample(p)
            self.assertEqual(main([str(p), '--output-dir', str(Path(t) / 'out')]), 0)
            folder = Path(t) / 'out' / 'raw'
            self.assertTrue((folder / 'manifest.json').exists())
            from replay import frames
            stream = list(frames(folder / 'frames.txt'))
            self.assertEqual(len(stream), 1)
            self.assertEqual(len(stream[0][1]), 4304)

    def test_no_fabricated_windows_contact_oracle(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'raw.csv'
            self.sample(p)
            _, r = extract(p)
            self.assertIn('not Windows processed', r['warning'])
            self.assertIsNone(r['matches_historical_count'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
