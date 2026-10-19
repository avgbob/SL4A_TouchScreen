#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Evidence-bounded candidate feature kernels recovered from Windows.

This module covers only the portion between an already labelled component and
the ten inputs consumed by ``FUN_180601690``.  It intentionally does not label
a heatmap, split a component, select candidates, or infer missing configuration
constants.  Those operations remain separate evidence gates.

Recovered sources:

* ``FUN_1806042f0``: fallback values for the three split-stat byte pairs.
* ``FUN_180600c40``: covariance/eigenvalue features at offsets 0x8c/0x90 and
  the component-cell copy at 0x9e.
* ``FUN_180605960``: surrounding-score normalization and the 100.0 oversize
  fallback at offset 0x94.

All recovered arithmetic is rounded to IEEE-754 binary32 after each operation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from windows_classifier import CandidateClassifierInput, f32


WINDOWS_CANDIDATE_RECORD_SIZE = 0xB0
WINDOWS_OVERSIZE_SURROUNDING_SCORE = 100.0
WINDOWS_AXIS_FALLBACK = f32(1.15)
WINDOWS_TWO_PI = f32(6.283185307179586)
# Pinned DLL VA 0x180765c20 / PE file offset 0x764c20:
# little-endian double bytes 36 cd 93 40 e4 cb 96 40.
WINDOWS_AXIS_SCALE_180765C20 = float.fromhex('0x1.6cbe44093cd36p+10')


def _u8(value: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFF:
        raise ValueError(f'{label} must be a u8')
    return value


def _u16(value: int, label: str) -> int:
    if type(value) is not int or not 0 <= value <= 0xFFFF:
        raise ValueError(f'{label} must be a u16')
    return value


@dataclass(frozen=True)
class SplitFeaturePairs:
    """Three ``(component_count, max_component_cells)`` byte pairs.

    The semantic names reflect the scratch CCL writes at 0x19471 and 0x1946c.
    They do not assign a contact class to any threshold.
    """

    pairs: tuple[tuple[int, int], tuple[int, int], tuple[int, int]]
    provenance: str

    def __post_init__(self):
        pairs = tuple(tuple(pair) for pair in self.pairs)
        if len(pairs) != 3 or any(len(pair) != 2 for pair in pairs):
            raise ValueError('pairs must contain three byte pairs')
        for index, pair in enumerate(pairs):
            _u8(pair[0], f'pairs[{index}].component_count')
            _u8(pair[1], f'pairs[{index}].max_component_cells')
        object.__setattr__(self, 'pairs', pairs)


def fallback_split_features(component_cells: int) -> SplitFeaturePairs:
    """Return the exact pre-resegmentation initialization from FUN_1806042f0.

    Windows stores one component and the low byte of candidate offset 0x38 in
    each pair before deciding whether its three thresholded CCL passes run.
    A caller may use this result only when those passes are known not to run.
    """
    component_cells = _u16(component_cells, 'component_cells')
    pair = (1, component_cells & 0xFF)
    return SplitFeaturePairs((pair, pair, pair),
                             'FUN_1806042f0:no-resegmentation fallback')


@dataclass(frozen=True)
class MomentSums:
    """Weighted central sums accumulated by FUN_180600c40.

    ``normalizer`` is candidate float 0x10 (``pfVar12[4]``), the divisor used
    by Windows after accumulating the three central second-moment sums.
    ``component_cells`` is candidate u16 0x38.
    """

    sum_xx: float
    sum_yy: float
    sum_xy: float
    normalizer: float
    component_cells: int

    def __post_init__(self):
        for name in ('sum_xx', 'sum_yy', 'sum_xy', 'normalizer'):
            object.__setattr__(self, name, f32(getattr(self, name)))
        if self.normalizer <= 0.0:
            raise ValueError('normalizer must be positive')
        _u16(self.component_cells, 'component_cells')


@dataclass(frozen=True)
class GeometryFeatures:
    axis_ratio_008c: float
    trace_dispersion_0090: float
    provenance: str = 'FUN_180600c40:weighted central moments'

    def __post_init__(self):
        object.__setattr__(self, 'axis_ratio_008c', f32(self.axis_ratio_008c))
        object.__setattr__(self, 'trace_dispersion_0090',
                           f32(self.trace_dispersion_0090))


def geometry_features(moment_sums: MomentSums) -> GeometryFeatures:
    """Reproduce the two classifier geometry fields from sufficient statistics.

    The overlapping double ``_DAT_180765c20`` is read from the pinned DLL bytes,
    not inferred from the decompiler's incomplete static-data table.
    """
    if not isinstance(moment_sums, MomentSums):
        raise TypeError('moment_sums must be MomentSums')
    scale = f32(1.0 / moment_sums.normalizer)
    yy = f32(moment_sums.sum_yy * scale)
    xx = f32(moment_sums.sum_xx * scale)
    xy = f32(moment_sums.sum_xy * scale)
    trace = f32(yy + xx)
    determinant = f32(f32(yy * xx) - f32(xy * xy))
    discriminant = f32(f32(trace * trace) - f32(determinant * f32(4.0)))
    if discriminant < 0.0:
        raise ValueError('moment matrix produces a negative discriminant')
    root = f32(math.sqrt(discriminant))
    eigen_small = f32(f32(trace - root) * f32(0.5))
    eigen_large = f32(f32(trace + root) * f32(0.5))
    eigen_small = max(0.0, eigen_small)
    eigen_large = max(eigen_small, eigen_large)
    # The underscore-prefixed decompiler symbol is an overlapping double;
    # preserve the float-to-double multiply followed by assignment to float.
    major = f32(float(f32(math.sqrt(eigen_large))) *
                WINDOWS_AXIS_SCALE_180765C20)
    minor = f32(float(f32(math.sqrt(eigen_small))) *
                WINDOWS_AXIS_SCALE_180765C20)
    if major < 1.0:
        major = WINDOWS_AXIS_FALLBACK
    if minor < 1.0:
        minor = WINDOWS_AXIS_FALLBACK
    ratio = f32(major / minor)

    dispersion = f32(1.0)
    if moment_sums.component_cells > 1:
        dispersion = f32(
            f32(trace * WINDOWS_TWO_PI) /
            f32(float(moment_sums.component_cells - 1))
        )
    return GeometryFeatures(ratio, dispersion)


def surrounding_score(*, bbox_width: int, bbox_height: int,
                      accumulated_signal: float | None = None,
                      candidate_signal: float | None = None,
                      double_for_flag_0048: bool = False) -> float:
    """Return candidate offset 0x94 using FUN_180605960's final branches.

    For boxes at least 11 cells wide or high, Windows writes 100.0 without
    running its 16x16 neighbourhood walks.  For smaller boxes, the caller must
    provide the accumulator produced by those unresolved walks and the LUT
    signal selected by candidate byte 0x4b.
    """
    for value, label in ((bbox_width, 'bbox_width'),
                         (bbox_height, 'bbox_height')):
        if type(value) is not int or value <= 0:
            raise ValueError(f'{label} must be a positive integer')
    if type(double_for_flag_0048) is not bool:
        raise ValueError('double_for_flag_0048 must be bool')
    if bbox_width >= 11 or bbox_height >= 11:
        return f32(WINDOWS_OVERSIZE_SURROUNDING_SCORE)
    if accumulated_signal is None or candidate_signal is None:
        raise ValueError('small boxes require accumulated_signal and candidate_signal')
    accumulated_signal = f32(accumulated_signal)
    candidate_signal = f32(candidate_signal)
    if candidate_signal == 0.0:
        raise ValueError('candidate_signal must be nonzero')
    score = f32(accumulated_signal / candidate_signal)
    if double_for_flag_0048:
        score = f32(score + score)
    return score


@dataclass(frozen=True)
class GroundedCandidateFeatures:
    """The ten common-classifier inputs with explicit stage provenance."""

    component_cells: int
    split: SplitFeaturePairs
    geometry: GeometryFeatures
    surrounding_0094: float
    surrounding_provenance: str
    flag_004c: int = 0
    flag_004d: int = 0

    def __post_init__(self):
        _u16(self.component_cells, 'component_cells')
        if not isinstance(self.split, SplitFeaturePairs):
            raise TypeError('split must be SplitFeaturePairs')
        if not isinstance(self.geometry, GeometryFeatures):
            raise TypeError('geometry must be GeometryFeatures')
        object.__setattr__(self, 'surrounding_0094', f32(self.surrounding_0094))
        _u8(self.flag_004c, 'flag_004c')
        _u8(self.flag_004d, 'flag_004d')

    def classifier_input(self) -> CandidateClassifierInput:
        pairs = self.split.pairs
        features = (
            self.component_cells,
            pairs[0][1], pairs[1][1], pairs[2][1],
            pairs[0][0], pairs[1][0], pairs[2][0],
            self.geometry.axis_ratio_008c,
            self.geometry.trace_dispersion_0090,
            self.surrounding_0094,
        )
        return CandidateClassifierInput(features, self.component_cells,
                                        self.flag_004c, self.flag_004d)
