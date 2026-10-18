#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
import struct
import unittest

from windows_class_transition import (
    TRANSITION_CONFIG_MIN_SIZE,
    TransitionCell,
    TransitionConfig,
    argmax_lower_tie,
    current_transition_gate,
    history_transition_gate,
    transition_config_from_runtime_bytes,
)


def cell(**overrides):
    values = dict(history_margins=(0, 0, 0, 0),
                  current_margins=(0, 0, 0, 0), absolute_floor=-100,
                  candidate_flag_bias=2, history_window=2,
                  mode1_current_enabled=True,
                  mode1_history_window_add=0)
    values.update(overrides)
    return TransitionCell(**values)


def config(target=None, *, old=4, proposed=0, global_bias=20):
    rows = [[cell() for _ in range(4)] for _ in range(5)]
    if target is not None:
        rows[old][proposed] = target
    return TransitionConfig(tuple(tuple(row) for row in rows), global_bias)


class WindowsClassTransitionTests(unittest.TestCase):
    def test_argmax_ties_keep_lower_numeric_class(self):
        self.assertEqual(argmax_lower_tie((8, 8, 7, 8)), 0)
        self.assertEqual(argmax_lower_tie((1, 3, 3, 2)), 1)

    def test_current_gate_checks_every_competitor_and_floor(self):
        target = cell(current_margins=(2, 3, 4, 5), absolute_floor=10)
        cfg = config(target)
        self.assertTrue(current_transition_gate((12, 9, 8, 7), 4, 0, cfg))
        self.assertFalse(current_transition_gate((12, 10, 8, 7), 4, 0, cfg))
        self.assertFalse(current_transition_gate((9, 0, 0, 0), 4, 0, cfg))

    def test_mode1_current_enable_and_candidate_bias(self):
        disabled = config(cell(mode1_current_enabled=False))
        self.assertFalse(current_transition_gate((100, 0, 0, 0), 4, 0,
                                                 disabled, mode_1=True))
        target = cell(current_margins=(0, 5, 5, 5), absolute_floor=0)
        cfg = config(target, global_bias=20)
        self.assertTrue(current_transition_gate((27, 0, 0, 0), 4, 0, cfg,
                                                mode_1=True,
                                                candidate_flag=True))
        self.assertFalse(current_transition_gate((21, 0, 0, 0), 4, 0, cfg,
                                                 mode_1=True,
                                                 candidate_flag=True))

    def test_spatial_special_forces_current_floor_20(self):
        cfg = config(cell(absolute_floor=-9999))
        self.assertFalse(current_transition_gate((19, 0, 0, 0), 4, 0, cfg,
                                                 spatial_special=True))
        self.assertTrue(current_transition_gate((20, 0, 0, 0), 4, 0, cfg,
                                                spatial_special=True))

    def test_history_same_class_short_circuits(self):
        cfg = config(old=2, proposed=2)
        self.assertTrue(history_transition_gate((), 2, 2, cfg))

    def test_history_requires_depth_and_all_selected_samples(self):
        target = cell(history_margins=(0, 5, 5, 5), history_window=2,
                      absolute_floor=0)
        cfg = config(target)
        self.assertFalse(history_transition_gate(((10, 0, 0, 0),), 4, 0, cfg))
        self.assertTrue(history_transition_gate(((10, 0, 0, 0),
                                                 (6, 0, 0, 0)), 4, 0, cfg))
        self.assertFalse(history_transition_gate(((10, 0, 0, 0),
                                                  (4, 0, 0, 0)), 4, 0, cfg))

    def test_history_depth_is_capped_at_ten_ring_entries(self):
        cfg = config(cell(history_window=11))
        self.assertFalse(history_transition_gate(((100, 0, 0, 0),) * 11,
                                                 4, 0, cfg))

    def test_history_mode1_window_and_flag_bias_are_distinct(self):
        target = cell(history_margins=(0, 1, 1, 1), history_window=1,
                      mode1_history_window_add=1)
        cfg = config(target, global_bias=3)
        samples = ((5, 0, 0, 0), (4, 0, 0, 0))
        self.assertTrue(history_transition_gate(samples, 4, 0, cfg,
                                                mode_1=True))
        self.assertTrue(history_transition_gate(samples, 4, 0, cfg,
                                                mode_1=True,
                                                candidate_flag=True))
        self.assertFalse(history_transition_gate(((5, 0, 0, 0),
                                                  (3, 0, 0, 0)), 4, 0, cfg,
                                                 mode_1=True,
                                                 candidate_flag=True))

    def test_runtime_layout_is_five_by_four_and_signed(self):
        raw = bytearray(TRANSITION_CONFIG_MIN_SIZE)
        raw[0x8f2] = 0xec  # -20 as s8
        for old in range(5):
            for proposed in range(4):
                index = old * 4 + proposed
                base = 0x8d8 + index * 0x30
                struct.pack_into('<4i', raw, base + 0x28,
                                 index, index + 1, index + 2, index + 3)
                struct.pack_into('<4i', raw, base + 0x3c,
                                 -index, -index - 1, -index - 2, -index - 3)
                struct.pack_into('<h', raw, base + 0x4c, -500 + index)
                struct.pack_into('<b', raw, base + 0x4e, -2)
                raw[base + 0x4f] = index
                raw[base + 0x51] = index & 1
                struct.pack_into('<b', raw, 0x92a + index * 0x30, -3)
        cfg = transition_config_from_runtime_bytes(raw)
        final = cfg.cell(4, 3)
        self.assertEqual(cfg.mode1_candidate_flag_bias, -20)
        self.assertEqual(final.history_margins, (19, 20, 21, 22))
        self.assertEqual(final.current_margins, (-19, -20, -21, -22))
        self.assertEqual((final.absolute_floor, final.candidate_flag_bias,
                          final.history_window, final.mode1_current_enabled,
                          final.mode1_history_window_add),
                         (-481, -2, 19, True, -3))

    def test_invalid_shapes_and_nonfinite_scores_fail_closed(self):
        with self.assertRaises(ValueError):
            argmax_lower_tie((1, 2, 3))
        with self.assertRaises(ValueError):
            current_transition_gate((1, 2, float('nan'), 4), 4, 0, config())
        with self.assertRaises(ValueError):
            config().cell(5, 0)
        with self.assertRaisesRegex(ValueError, 'mode_1'):
            current_transition_gate((1, 0, 0, 0), 4, 0, config(), mode_1=1)
        with self.assertRaisesRegex(ValueError, '4 -> 0'):
            current_transition_gate((1, 0, 0, 0), 1, 0, config(),
                                    spatial_special=True)
        with self.assertRaisesRegex(ValueError, 's32'):
            cell(current_margins=(0, 0, 0, 0x80000000))
        with self.assertRaisesRegex(ValueError, 'at least'):
            transition_config_from_runtime_bytes(bytes(TRANSITION_CONFIG_MIN_SIZE - 1))


if __name__ == '__main__':
    unittest.main()
