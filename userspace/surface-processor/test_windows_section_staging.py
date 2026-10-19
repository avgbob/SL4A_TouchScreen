#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
import ctypes
from pathlib import Path
import random
import shutil
import struct
import subprocess
import tempfile
import unittest

from windows_classifier import f32
from windows_section_staging import (
    PSDB_HEIGHT_OFFSET,
    PSDB_STREAM_RECORD_SIZE,
    PSDB_WIDTH_OFFSET,
    WINDOWS_16BIT_RETURN_LENGTH,
    WINDOWS_0C19_STREAM0_HEIGHT,
    WINDOWS_0C19_STREAM0_WIDTH,
    WINDOWS_8BIT_RETURN_LENGTH,
    convert_u16_sample,
    read_psdb_stream_geometry,
    stage_heatmap_section,
)


def section8(*runs):
    body = bytearray((1, 8))
    for destination, samples in runs:
        body.extend(struct.pack('<II', destination, len(samples)))
        body.extend(samples)
    return struct.pack('<IH', 6 + len(body), 0x0100) + body


def section16(*runs):
    body = bytearray((0,))
    for destination, samples in runs:
        body.extend(struct.pack('<II', destination, len(samples)))
        body.extend(struct.pack(f'<{len(samples)}H', *samples))
    return struct.pack('<IH', 6 + len(body), 0x0100) + body


class WindowsSectionStagingTests(unittest.TestCase):
    def test_complete_8bit_run_uses_direct_view(self):
        samples = bytes(range(256)) * 13 + bytes(range(128))
        result = stage_heatmap_section(
            section8((0, samples)), width=WINDOWS_0C19_STREAM0_WIDTH,
            height=WINDOWS_0C19_STREAM0_HEIGHT)
        self.assertTrue(result.direct_view)
        self.assertEqual(result.pixels, samples)
        self.assertEqual(result.packed_active_grid(), samples)
        self.assertEqual(result.windows_return_length,
                         WINDOWS_8BIT_RETURN_LENGTH)

    def test_psdb_geometry_layout_and_pinned_0c19_values(self):
        config = bytearray(PSDB_STREAM_RECORD_SIZE * 2 + 4)
        # Privacy-safe four-byte slice at pinned DLL file offset 0x8df09c:
        # little-endian stream-0 height followed by width.
        config[PSDB_HEIGHT_OFFSET:PSDB_WIDTH_OFFSET + 2] = bytes.fromhex(
            '30004800')
        self.assertEqual(read_psdb_stream_geometry(bytes(config)), (72, 48))
        self.assertEqual((WINDOWS_0C19_STREAM0_WIDTH,
                          WINDOWS_0C19_STREAM0_HEIGHT), (72, 48))
        self.assertEqual(read_psdb_stream_geometry(bytes(config), 1), (0, 0))

        with self.assertRaisesRegex(ValueError, 'truncated'):
            read_psdb_stream_geometry(bytes(config[:PSDB_WIDTH_OFFSET + 1]))
        with self.assertRaisesRegex(ValueError, 'non-negative'):
            read_psdb_stream_geometry(bytes(config), -1)

    def test_multirun_8bit_destination_translation_is_once_per_run(self):
        result = stage_heatmap_section(
            section8((0, b'ab'), (4, b'cdef')), width=4, height=2)
        self.assertFalse(result.direct_view)
        self.assertEqual(result.pixels[:2], b'ab')
        self.assertEqual(result.pixels[288:292], b'cdef')
        self.assertEqual(result.packed_active_grid(), b'ab\x00\x00cdef')

    def test_16bit_scale_bias_truncation_and_clamp(self):
        result = stage_heatmap_section(
            section16((2, (0, 3, 20, 1000))), width=8, height=1,
            scale=0.5, bias=-2.25)
        self.assertFalse(result.direct_view)
        self.assertEqual(result.pixels[:6], bytes((0, 0, 0, 0, 7, 255)))
        self.assertEqual(result.windows_return_length,
                         WINDOWS_16BIT_RETURN_LENGTH)

    def test_16bit_converted_grid_is_packed_not_288_strided(self):
        result = stage_heatmap_section(
            section16((0, (1, 2, 3, 4, 5, 6))), width=3, height=2)
        self.assertEqual(result.packed_active_grid(),
                         bytes((1, 2, 3, 4, 5, 6)))

    def test_rejects_malformed_sections_and_impossible_geometry(self):
        truncated_run = bytearray(section8((0, b'abc')))
        struct.pack_into('<I', truncated_run, 12, 4)
        with self.assertRaisesRegex(ValueError, 'truncated'):
            stage_heatmap_section(bytes(truncated_run),
                                  width=3, height=1)
        with self.assertRaisesRegex(ValueError, 'row stride'):
            stage_heatmap_section(section8((0, b'abc')),
                                  width=289, height=1)
        bad_width = bytearray(section8((0, b'abc')))
        bad_width[7] = 16
        with self.assertRaisesRegex(ValueError, '8-bit'):
            stage_heatmap_section(bytes(bad_width), width=3, height=1)


@unittest.skipUnless(shutil.which('cc'), 'C compiler required for oracle')
class CompiledSectionStagingOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        source = (Path(__file__).parent / 'c_oracle' /
                  'windows_section_staging_oracle.c')
        library = Path(cls.temporary.name) / 'windows_section_staging_oracle.so'
        subprocess.run([
            shutil.which('cc'), '-std=c11', '-O0', '-ffp-contract=off',
            '-shared', '-fPIC', str(source), '-o', str(library),
        ], check=True, capture_output=True, text=True)
        dll = ctypes.CDLL(str(library))
        cls.c_destination = dll.windows_8bit_destination
        cls.c_destination.argtypes = [ctypes.c_uint32, ctypes.c_uint16]
        cls.c_destination.restype = ctypes.c_uint32
        cls.c_convert = dll.windows_convert_u16
        cls.c_convert.argtypes = [ctypes.c_uint16, ctypes.c_float,
                                  ctypes.c_float]
        cls.c_convert.restype = ctypes.c_uint8

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_python_matches_c_destination_and_calibration_arithmetic(self):
        rng = random.Random(0x68E990)
        for case in range(512):
            width = rng.randrange(1, 289)
            destination = rng.randrange(width * 48)
            expected_destination = (destination +
                                    (288 - width) * (destination // width))
            self.assertEqual(self.c_destination(destination, width),
                             expected_destination, case)

            sample = rng.randrange(1001)
            scale = f32(rng.uniform(-0.5, 0.5))
            bias = f32(rng.uniform(-100.0, 300.0))
            self.assertEqual(convert_u16_sample(sample, scale, bias),
                             self.c_convert(sample, scale, bias), case)


if __name__ == '__main__':
    unittest.main()
