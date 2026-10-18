# SPDX-License-Identifier: GPL-2.0
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from windows_pointer_oracle import build_oracle, guided_holds, write_oracle


HEADER = ('StopwatchTicks,Stage,Event,PointerId,X,Y,RawX,RawY,ContactL,'
          'ContactT,ContactR,ContactB,Pressure,Orientation,PointerFlags,FrameId,'
          'OperatorPhysical\n')


def row(tick, stage, event, pointer=0, x=0, y=0, physical=-1):
    rect = f'{x-1},{y-1},{x+1},{y+1}' if pointer else ',,,'
    return (f'{tick},{stage},{event},{pointer},{x},{y},{x},{y},{rect},'
            f'{512 if pointer else ""},{0 if pointer else ""},0x00000000,'
            f'{tick // 1000},{physical}\n')


def write_run(run: Path, content: str, ticks: list[int], down: int, up: int):
    (run / 'pointer').mkdir()
    (run / 'offline-analysis').mkdir()
    pointer = run / 'pointer' / 'events.csv'
    pointer.write_text(content, encoding='utf-8')
    digest = hashlib.sha256(pointer.read_bytes()).hexdigest()
    (run / 'manifest.json').write_text(json.dumps({
        'files': [{'file': 'pointer\\events.csv', 'sha256': digest}],
    }), encoding='utf-8')
    coverage = {
        'physical_truth_protocol': 'V4_GUIDED_PHYSICAL_TRUTH',
        'manifest_created_utc': 'test',
        'physical_truth_v4': {'os_event_lifetimes': {'DOWN': down, 'UP': up}},
        'wpr': {
            'decoded_complete_0c_frames': len(ticks),
            'source_sha256': 'abc',
            'frames': [{'clock_100ns_raw': str(tick)} for tick in ticks],
        },
    }
    (run / 'offline-analysis' / 'coverage-report.json').write_text(
        json.dumps(coverage), encoding='utf-8')


class WindowsPointerOracleTest(unittest.TestCase):
    def test_guided_holds_reject_unfinished_stage(self):
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            guided_holds([{
                'Event': 'OPERATOR_CONFIRM_TEST', 'Stage': '4',
                'StopwatchTicks': '100', 'OperatorPhysical': '2',
            }])

    def test_frame_alignment_lifetimes_holds_and_tail_up(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            content = HEADER
            content += row(1_000_000, 0, 'OPERATOR_CONFIRM_TEST', physical=1)
            content += row(1_100_000, 0, 'DOWN', pointer=9, x=100, y=200)
            content += row(6_000_000, 0, 'UPDATE', pointer=9, x=110, y=210)
            content += row(21_000_000, 0, 'GUIDED_HOLD_COMPLETE', physical=1)
            content += row(22_000_000, 1, 'UP', pointer=9, x=110, y=210)
            ticks = [1_000_000, 2_000_000, 7_000_000, 20_000_000]
            write_run(run, content, ticks, 1, 1)

            frames, summary = build_oracle(run)
            self.assertEqual([len(frame['contacts']) for frame in frames],
                             [0, 1, 1, 1])
            self.assertEqual(frames[1]['transitions'][0]['event'], 'DOWN')
            self.assertEqual(frames[2]['contacts'][0]['x'], 110)
            self.assertTrue(frames[2]['guided_hold']['conservative'])
            self.assertEqual(summary['pointer_lifetimes'], {'DOWN': 1, 'UP': 1})
            self.assertEqual(summary['tail_transitions'][0]['event'], 'UP')
            self.assertEqual(summary['guided_holds'][0][
                'windows_contact_histogram'], {'1': 1})

            output = run / 'oracle.jsonl'
            first = write_oracle(frames, output)
            second = write_oracle(frames, output)
            self.assertEqual(first, second)
            self.assertEqual(len(output.read_text().splitlines()), 4)

    def test_manifest_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            content = HEADER + row(100, 0, 'DOWN', pointer=5, x=1, y=2)
            write_run(run, content, [200], 1, 0)
            pointer = run / 'pointer' / 'events.csv'
            pointer.write_text(content + row(150, 0, 'UPDATE', pointer=5),
                               encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA-256 differs'):
                build_oracle(run)

    def test_duplicate_down_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            content = (HEADER + row(100, 0, 'DOWN', pointer=5, x=1, y=2)
                       + row(200, 0, 'DOWN', pointer=5, x=1, y=2))
            write_run(run, content, [300], 2, 0)
            with self.assertRaisesRegex(ValueError, 'duplicate DOWN'):
                build_oracle(run)


if __name__ == '__main__':
    unittest.main()
