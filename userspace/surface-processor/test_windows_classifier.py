#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
import math
import struct
import unittest

from windows_classifier import (
    CandidateClassifierInput,
    ClassifierConfig,
    ScoreBlock,
    candidate_input_from_record,
    classifier_config_from_runtime_bytes,
    effective_suppression,
    score_candidate,
)


def identity_rows():
    return tuple(tuple(1.0 if column == row else 0.0
                       for column in range(row, 10))
                 for row in range(10))


def block(**overrides):
    values = dict(max_component_cells=100, upper_rows=identity_rows(),
                  means=(0.0,) * 10, base_penalty=2.0,
                  limit_mode_0=20.0, limit_mode_1=30.0)
    values.update(overrides)
    return ScoreBlock(**values)


def config(**overrides):
    values = dict(forced_suppression=(0,) * 10,
                  conditional_suppression=(0,) * 10,
                  blocks=(block(),) * 4,
                  score3_penalty_flag_004c=0.75,
                  score3_penalty_flag_004d=0.25)
    values.update(overrides)
    return ClassifierConfig(**values)


class WindowsClassifierTests(unittest.TestCase):
    def test_candidate_record_field_order(self):
        record = bytearray(0xb0)
        struct.pack_into('<H', record, 0x38, 321)
        struct.pack_into('<H', record, 0x9e, 654)
        for offset, value in zip((0x99, 0x9b, 0x9d, 0x98, 0x9a, 0x9c),
                                 (1, 2, 3, 4, 5, 6)):
            record[offset] = value
        for offset, value in zip((0x8c, 0x90, 0x94), (7.5, 8.5, 9.5)):
            struct.pack_into('<f', record, offset, value)
        record[0x4c], record[0x4d] = 1, 2
        candidate = candidate_input_from_record(record)
        self.assertEqual(candidate.features,
                         (654.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0,
                          7.5, 8.5, 9.5))
        self.assertEqual(candidate.component_cells_0038, 321)
        self.assertEqual((candidate.flag_004c, candidate.flag_004d), (1, 2))

    def test_effective_suppression_preserves_byte_logic(self):
        cfg = config(forced_suppression=(0, 1) + (0,) * 8,
                     conditional_suppression=(2, 0, 4) + (0,) * 7)
        self.assertEqual(effective_suppression(cfg, 6)[:4], (2, 1, 4, 0))
        self.assertEqual(effective_suppression(cfg, 1)[:4], (0, 1, 0, 0))

    def test_identity_transform_score_mode_and_bias(self):
        candidate = CandidateClassifierInput(tuple(range(1, 11)), 10)
        # sum(1^2..10^2) = 385; score = 20 - 1 + 2 - 192.5
        scores = score_candidate(candidate, config(), dynamic_mask_byte=0,
                                 runtime_bias=2.0)
        self.assertTrue(all(math.isclose(score, -171.5) for score in scores))
        mode_1 = score_candidate(candidate, config(), dynamic_mask_byte=0,
                                 mode_1=True, runtime_bias=2.0)
        self.assertTrue(all(math.isclose(score, -161.5) for score in mode_1))

    def test_suppressed_features_have_zero_delta(self):
        cfg = config(forced_suppression=(1,) + (0,) * 9)
        candidate = CandidateClassifierInput((100.0,) + (0.0,) * 9, 1)
        self.assertEqual(score_candidate(candidate, cfg, dynamic_mask_byte=0),
                         (19.0, 19.0, 19.0, 19.0))

    def test_upper_triangular_storage_is_not_dense_row_indexing(self):
        rows = ((2.0,) + (0.0,) * 9,
                (3.0,) + (0.0,) * 8,
                (4.0,) + (0.0,) * 7,
                (5.0,) + (0.0,) * 6,
                (6.0,) + (0.0,) * 5,
                (7.0,) + (0.0,) * 4,
                (8.0,) + (0.0,) * 3,
                (9.0,) + (0.0,) * 2,
                (10.0, 0.0),
                (11.0,))
        b = block(upper_rows=rows, base_penalty=0, limit_mode_0=0)
        candidate = CandidateClassifierInput((1.0,) * 10, 1)
        expected_norm = sum(value * value for value in range(2, 12))
        self.assertEqual(score_candidate(candidate, config(blocks=(b,) * 4),
                                         dynamic_mask_byte=0),
                         (-0.5 * expected_norm,) * 4)

    def test_count_gate_and_edge_penalty_priority(self):
        candidate = CandidateClassifierInput((0.0,) * 10, 101,
                                             flag_004c=1, flag_004d=1)
        self.assertEqual(score_candidate(candidate, config(), dynamic_mask_byte=0),
                         (-9999.0, -9999.0, -9999.0, -9999.75))

    def test_nonfinite_values_and_bad_shapes_are_rejected(self):
        with self.assertRaises(ValueError):
            CandidateClassifierInput((0.0,) * 9 + (float('nan'),), 1)
        with self.assertRaises(ValueError):
            block(upper_rows=((0.0,) * 10,) * 10)
        with self.assertRaises(ValueError):
            score_candidate(CandidateClassifierInput((0.0,) * 10, 1), config(),
                            dynamic_mask_byte=256)

    def test_runtime_config_layout_uses_packed_upper_rows(self):
        raw = bytearray(0x8d8)
        raw[0x10c:0x116] = bytes(range(10))
        raw[0x11c:0x126] = bytes(range(10, 20))
        for block_index in range(4):
            base = 0x134 + block_index * 0x1d0
            for row in range(10):
                for packed_column in range(10 - row):
                    struct.pack_into('<f', raw,
                                     base + row * 0x2c + packed_column * 4,
                                     1000 * block_index + 100 * row + packed_column)
            struct.pack_into('<f', raw, base + 0x190, block_index + 0.25)
            for index in range(10):
                struct.pack_into('<f', raw, base + 0x198 + index * 4,
                                 block_index * 10 + index)
            struct.pack_into('<f', raw, base + 0x1c0, block_index + 0.5)
            struct.pack_into('<f', raw, base + 0x1c4, block_index + 0.75)
            struct.pack_into('<I', raw, 0x870 + block_index * 4,
                             100 + block_index)
        struct.pack_into('<f', raw, 0x8d0, 1.25)
        struct.pack_into('<f', raw, 0x8d4, 2.25)

        cfg = classifier_config_from_runtime_bytes(raw)
        self.assertEqual(cfg.forced_suppression, tuple(range(10)))
        self.assertEqual(cfg.conditional_suppression, tuple(range(10, 20)))
        self.assertEqual(cfg.blocks[2].max_component_cells, 102)
        self.assertEqual(cfg.blocks[2].upper_rows[3][4], 2304.0)
        self.assertEqual(cfg.blocks[2].means[7], 27.0)
        self.assertEqual(cfg.blocks[2].base_penalty, 2.25)
        self.assertEqual((cfg.blocks[2].limit_mode_0,
                          cfg.blocks[2].limit_mode_1), (2.5, 2.75))
        self.assertEqual((cfg.score3_penalty_flag_004c,
                          cfg.score3_penalty_flag_004d), (1.25, 2.25))

    def test_static_like_nonfinite_runtime_config_is_rejected(self):
        raw = bytearray(0x8d8)
        struct.pack_into('<I', raw, 0x134, 0x7fc00000)
        with self.assertRaisesRegex(ValueError, 'upper_rows'):
            classifier_config_from_runtime_bytes(raw)


if __name__ == '__main__':
    unittest.main()
