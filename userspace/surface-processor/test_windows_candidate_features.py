#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
import ctypes
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
import unittest

from windows_candidate_features import (
    GeometryFeatures,
    GroundedCandidateFeatures,
    MomentSums,
    SplitFeaturePairs,
    WINDOWS_AXIS_SCALE_180765C20,
    fallback_split_features,
    geometry_features,
    surrounding_score,
)
from windows_classifier import f32


class WindowsCandidateFeatureTests(unittest.TestCase):
    def test_fallback_split_pairs_copy_low_component_count_byte(self):
        split = fallback_split_features(0x123)
        self.assertEqual(split.pairs, ((1, 0x23),) * 3)
        self.assertIn('no-resegmentation', split.provenance)

    def test_isotropic_moments_produce_unit_ratio(self):
        result = geometry_features(
            MomentSums(16.0, 16.0, 0.0, 4.0, 9))
        self.assertEqual(result.axis_ratio_008c, 1.0)
        self.assertEqual(result.trace_dispersion_0090,
                         f32(f32(8.0 * f32(6.283185307179586)) / 8.0))

    def test_elongated_moments_produce_major_over_minor_ratio(self):
        result = geometry_features(
            MomentSums(36.0, 4.0, 0.0, 1.0, 10))
        major = f32(6.0 * WINDOWS_AXIS_SCALE_180765C20)
        minor = f32(2.0 * WINDOWS_AXIS_SCALE_180765C20)
        self.assertEqual(result.axis_ratio_008c, f32(major / minor))

    def test_axis_below_one_uses_recovered_1_15_fallback(self):
        result = geometry_features(
            MomentSums(4e-6, 4e-8, 0.0, 1.0, 2))
        major = f32(f32((f32(4e-6)) ** 0.5) *
                    WINDOWS_AXIS_SCALE_180765C20)
        self.assertEqual(result.axis_ratio_008c, f32(major / f32(1.15)))

    def test_single_cell_dispersion_is_one(self):
        result = geometry_features(
            MomentSums(1.0, 1.0, 0.0, 1.0, 1))
        self.assertEqual(result.trace_dispersion_0090, 1.0)

    def test_surrounding_score_oversize_and_small_box_paths(self):
        self.assertEqual(surrounding_score(bbox_width=11, bbox_height=2), 100.0)
        self.assertEqual(surrounding_score(
            bbox_width=10, bbox_height=10, accumulated_signal=9.0,
            candidate_signal=3.0), 3.0)
        self.assertEqual(surrounding_score(
            bbox_width=10, bbox_height=10, accumulated_signal=9.0,
            candidate_signal=3.0, double_for_flag_0048=True), 6.0)
        with self.assertRaisesRegex(ValueError, 'small boxes require'):
            surrounding_score(bbox_width=10, bbox_height=10)

    def test_typed_stages_emit_classifier_order(self):
        split = SplitFeaturePairs(((2, 20), (3, 30), (4, 40)), 'fixture')
        grounded = GroundedCandidateFeatures(
            component_cells=50,
            split=split,
            geometry=GeometryFeatures(1.5, 2.5),
            surrounding_0094=3.5,
            surrounding_provenance='fixture accumulator',
            flag_004c=1,
        )
        candidate = grounded.classifier_input()
        self.assertEqual(candidate.features,
                         (50.0, 20.0, 30.0, 40.0, 2.0, 3.0, 4.0,
                          1.5, 2.5, 3.5))
        self.assertEqual(candidate.flag_004c, 1)

    def test_axis_scale_is_exact_pinned_dll_double(self):
        self.assertEqual(WINDOWS_AXIS_SCALE_180765C20.hex(),
                         '0x1.6cbe44093cd36p+10')

    def test_rejects_nonpositive_normalizer(self):
        with self.assertRaisesRegex(ValueError, 'normalizer must be positive'):
            MomentSums(1.0, 1.0, 0.0, 0.0, 2)


@unittest.skipUnless(shutil.which('cc'), 'C compiler required for float oracle')
class CompiledCandidateFeatureOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        source = (Path(__file__).parent / 'c_oracle' /
                  'windows_candidate_features_oracle.c')
        library = Path(cls.temporary.name) / 'windows_candidate_features_oracle.so'
        subprocess.run([
            shutil.which('cc'), '-std=c11', '-O0', '-ffp-contract=off',
            '-shared', '-fPIC', str(source), '-lm', '-o', str(library),
        ], check=True, capture_output=True, text=True)
        cls.oracle = ctypes.CDLL(str(library)).windows_candidate_geometry_f32
        cls.oracle.argtypes = [
            ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
            ctypes.c_uint16, ctypes.POINTER(ctypes.c_float),
        ]
        cls.oracle.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_python_matches_compiled_float_operation_order(self):
        rng = random.Random(0x600C40)
        float2 = ctypes.c_float * 2
        for case in range(256):
            # Diagonal positive semidefinite moments exercise the recovered
            # arithmetic without manufacturing impossible covariance inputs.
            sums = MomentSums(
                f32(rng.uniform(0.000001, 10000.0)),
                f32(rng.uniform(0.000001, 10000.0)),
                0.0,
                f32(rng.uniform(0.1, 100.0)),
                rng.randrange(1, 1000),
            )
            python_result = geometry_features(sums)
            c_result = float2()
            self.oracle(sums.sum_xx, sums.sum_yy, sums.sum_xy,
                        sums.normalizer, sums.component_cells, c_result)
            self.assertEqual(
                (python_result.axis_ratio_008c.hex(),
                 python_result.trace_dispersion_0090.hex()),
                (float(c_result[0]).hex(), float(c_result[1]).hex()),
                f'float32 mismatch in randomized case {case}',
            )


if __name__ == '__main__':
    unittest.main()
