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
from windows_initial_ccl import (
    WINDOWS_SIGNAL_LUT,
    adjusted_weight,
    initial_ccl,
    threshold_raw_index,
)


def float_bits(value):
    return struct.pack('<f', value)


class WindowsInitialCclTests(unittest.TestCase):
    def test_lut_has_only_the_255_initialized_windows_slots(self):
        self.assertEqual(len(WINDOWS_SIGNAL_LUT), 255)
        self.assertEqual(float_bits(WINDOWS_SIGNAL_LUT[0]),
                         bytes.fromhex('cccccc3e'))
        self.assertLess(WINDOWS_SIGNAL_LUT[254], 0.0)
        with self.assertRaisesRegex(ValueError, 'initialized c590'):
            adjusted_weight(255, 0.04)

    def test_threshold_conversion_and_weight_floor(self):
        gate = threshold_raw_index(0.04)
        self.assertEqual(gate, 162)
        self.assertGreater(adjusted_weight(gate, 0.04), 0.0)

    def test_main_pass_is_eight_connected(self):
        # Diagonal cells are one component in the main pass.
        grid = bytes((100, 255, 255, 100))
        result = initial_ccl(grid, width=2, height=2,
                             signal_threshold=0.04,
                             minimum_peak_signal=1.0)
        self.assertEqual(result.provisional_label_count, 1)
        self.assertEqual(result.candidates[0].component_cells, 2)

    def test_bridge_records_equivalence_and_merges_to_low_label(self):
        grid = bytes((100, 255, 100,
                      255, 100, 255))
        result = initial_ccl(grid, width=3, height=2,
                             signal_threshold=0.04,
                             minimum_peak_signal=1.0)
        self.assertEqual(result.provisional_label_count, 2)
        self.assertEqual(result.equivalence_pair_count, 1)
        self.assertEqual(result.canonical_labels, (0, 1, 1))
        self.assertEqual(len(result.candidates), 1)
        candidate = result.candidates[0]
        self.assertEqual(candidate.component_cells, 3)
        self.assertEqual((candidate.left, candidate.top,
                          candidate.right, candidate.bottom), (0, 0, 2, 1))
        self.assertTrue(candidate.accepted)

    def test_small_component_peak_gate_matches_strict_comparison(self):
        weak = initial_ccl(bytes((100,)), width=1, height=1,
                           signal_threshold=0.04,
                           minimum_peak_signal=0.2)
        strong = initial_ccl(bytes((50,)), width=1, height=1,
                             signal_threshold=0.04,
                             minimum_peak_signal=0.2)
        self.assertFalse(weak.candidates[0].accepted)
        self.assertTrue(strong.candidates[0].accepted)

    def test_three_cells_pass_without_peak_gate(self):
        result = initial_ccl(bytes((100, 100, 100)), width=3, height=1,
                             signal_threshold=0.04,
                             minimum_peak_signal=1.0)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.max_accepted_cells, 3)

    def test_accumulator_fields_use_recovered_signal_and_adjusted_weights(self):
        result = initial_ccl(bytes((100, 101)), width=2, height=1,
                             signal_threshold=0.04,
                             minimum_peak_signal=1.0)
        candidate = result.candidates[0]
        first_weight = adjusted_weight(100, 0.04)
        second_weight = adjusted_weight(101, 0.04)
        self.assertEqual(float_bits(candidate.adjusted_sum),
                         float_bits(f32(second_weight + first_weight)))
        self.assertEqual(float_bits(candidate.adjusted_x_sum),
                         float_bits(second_weight))
        self.assertEqual(candidate.peak_raw_index, 100)

    def test_initial_candidate_serializes_recovered_record_offsets(self):
        result = initial_ccl(bytes((50, 50, 50)), width=3, height=1,
                             signal_threshold=0.04,
                             minimum_peak_signal=0.2)
        candidate = result.candidates[0]
        record = candidate.record_bytes()
        self.assertEqual(len(record), 0xB0)
        self.assertEqual(struct.unpack_from('<H', record, 0x38)[0], 3)
        self.assertEqual(struct.unpack_from('<H', record, 0x3C)[0], 0)
        self.assertEqual(record[0x40:0x43], bytes((1, 1, 1)))
        self.assertEqual(record[0x4B], 50)

        rejected = initial_ccl(bytes((100,)), width=1, height=1,
                               signal_threshold=0.04,
                               minimum_peak_signal=0.2).candidates[0]
        rejected_record = rejected.record_bytes()
        self.assertEqual(rejected_record[0x40:0x43], bytes((4, 0, 1)))

    def test_provisional_label_capacity_is_enforced(self):
        grid = bytes((100, 255, 100))
        with self.assertRaisesRegex(OverflowError, 'provisional-label'):
            initial_ccl(grid, width=3, height=1,
                        signal_threshold=0.04,
                        minimum_peak_signal=0.0,
                        max_labels=1)

    def test_rejects_wire_or_mismatched_input_shape(self):
        with self.assertRaisesRegex(ValueError, 'length'):
            initial_ccl(bytes(10), width=3, height=4,
                        signal_threshold=0.04,
                        minimum_peak_signal=0.0)


@unittest.skipUnless(shutil.which('cc'), 'C compiler required for float oracle')
class CompiledInitialCclScalarOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        source = (Path(__file__).parent / 'c_oracle' /
                  'windows_initial_ccl_oracle.c')
        library = Path(cls.temporary.name) / 'windows_initial_ccl_oracle.so'
        subprocess.run([
            shutil.which('cc'), '-std=c11', '-O0', '-ffp-contract=off',
            '-shared', '-fPIC', str(source), '-o', str(library),
        ], check=True, capture_output=True, text=True)
        dll = ctypes.CDLL(str(library))
        cls.c_lut = dll.windows_c590_value
        cls.c_lut.argtypes = [ctypes.c_uint8]
        cls.c_lut.restype = ctypes.c_float
        cls.c_threshold = dll.windows_threshold_raw
        cls.c_threshold.argtypes = [ctypes.c_float]
        cls.c_threshold.restype = ctypes.c_uint8
        cls.c_weight = dll.windows_adjusted_weight
        cls.c_weight.argtypes = [ctypes.c_uint8, ctypes.c_float]
        cls.c_weight.restype = ctypes.c_float

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_python_matches_c_scalar_operation_order(self):
        rng = random.Random(0x604AB0)
        for case in range(512):
            raw = rng.randrange(255)
            threshold = f32(rng.uniform(-0.1, 0.35))
            self.assertEqual(float_bits(WINDOWS_SIGNAL_LUT[raw]),
                             float_bits(self.c_lut(raw)), case)
            self.assertEqual(threshold_raw_index(threshold),
                             self.c_threshold(threshold), case)
            self.assertEqual(float_bits(adjusted_weight(raw, threshold)),
                             float_bits(self.c_weight(raw, threshold)), case)


if __name__ == '__main__':
    unittest.main()
