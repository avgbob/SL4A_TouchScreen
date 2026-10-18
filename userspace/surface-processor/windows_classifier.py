#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Float32 executable specification of the common FUN_180601690 score kernel.

Names describe storage and arithmetic, not unproved Windows contact classes.
This module does not choose a final class, apply the three unresolved override
paths, emit a contact, or bundle Microsoft configuration coefficients.

Every arithmetic operation in the score path is rounded to IEEE-754 binary32.
The operation order is cross-checked against ``c_oracle/windows_classifier_oracle.c``.
This is stronger than the v1 binary64 transcription, but is still not a golden
Windows runtime comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct


FEATURE_COUNT = 10
SCORE_COUNT = 4
WINDOWS_DEFAULT_SCORE = -9999.0
WINDOWS_NORM_SCALE = 0.5
RUNTIME_CONFIG_MIN_SIZE = 0x8d8


def f32(value: float) -> float:
    """Round one value to IEEE-754 binary32 and return it as a Python float."""
    try:
        rounded = struct.unpack('<f', struct.pack('<f', float(value)))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError('value is outside finite float32 range') from exc
    if not math.isfinite(rounded):
        raise ValueError('value must be finite float32')
    return rounded


def _finite_f32_tuple(values, size, label):
    try:
        values = tuple(f32(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} must contain only finite float32 values') from exc
    if len(values) != size:
        raise ValueError(f'{label} must contain {size} values')
    return values


def _byte_tuple(values, size, label):
    values = tuple(values)
    if len(values) != size or any(type(value) is not int or not 0 <= value <= 255
                                  for value in values):
        raise ValueError(f'{label} must contain {size} bytes')
    return values


@dataclass(frozen=True)
class CandidateClassifierInput:
    """Fields consumed by the recovered four-score common kernel.

    ``features`` preserves the observed order of candidate offsets:
    ``009e:u16, 0099:u8, 009b:u8, 009d:u8, 0098:u8, 009a:u8, 009c:u8,
    008c:f32, 0090:f32, 0094:f32``.
    """

    features: tuple
    component_cells_0038: int
    flag_004c: int = 0
    flag_004d: int = 0

    def __post_init__(self):
        object.__setattr__(self, 'features',
                           _finite_f32_tuple(self.features, FEATURE_COUNT,
                                             'features'))
        if (type(self.component_cells_0038) is not int or
                not 0 <= self.component_cells_0038 <= 0xffff):
            raise ValueError('component_cells_0038 must be a u16')
        for name in ('flag_004c', 'flag_004d'):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 255:
                raise ValueError(f'{name} must be a byte')


@dataclass(frozen=True)
class ScoreBlock:
    """One recovered 0x1d0-byte score block, without semantic class names."""

    max_component_cells: int
    upper_rows: tuple
    means: tuple
    base_penalty: float
    limit_mode_0: float
    limit_mode_1: float

    def __post_init__(self):
        if (type(self.max_component_cells) is not int or
                not 0 <= self.max_component_cells <= 0xffffffff):
            raise ValueError('max_component_cells must be a u32')
        rows = tuple(tuple(row) for row in self.upper_rows)
        if (len(rows) != FEATURE_COUNT or
                any(len(row) != FEATURE_COUNT - index
                    for index, row in enumerate(rows))):
            raise ValueError('upper_rows must have lengths 10, 9, ..., 1')
        try:
            rows = tuple(tuple(f32(value) for value in row) for row in rows)
        except (TypeError, ValueError) as exc:
            raise ValueError('upper_rows must contain only finite float32 values') from exc
        object.__setattr__(self, 'upper_rows', rows)
        object.__setattr__(self, 'means',
                           _finite_f32_tuple(self.means, FEATURE_COUNT, 'means'))
        for name in ('base_penalty', 'limit_mode_0', 'limit_mode_1'):
            object.__setattr__(self, name, f32(getattr(self, name)))


@dataclass(frozen=True)
class ClassifierConfig:
    forced_suppression: tuple
    conditional_suppression: tuple
    blocks: tuple
    score3_penalty_flag_004c: float
    score3_penalty_flag_004d: float
    default_score: float = WINDOWS_DEFAULT_SCORE

    def __post_init__(self):
        object.__setattr__(self, 'forced_suppression',
                           _byte_tuple(self.forced_suppression, FEATURE_COUNT,
                                       'forced_suppression'))
        object.__setattr__(self, 'conditional_suppression',
                           _byte_tuple(self.conditional_suppression, FEATURE_COUNT,
                                       'conditional_suppression'))
        blocks = tuple(self.blocks)
        if len(blocks) != SCORE_COUNT or any(not isinstance(block, ScoreBlock)
                                             for block in blocks):
            raise ValueError('blocks must contain four ScoreBlock values')
        object.__setattr__(self, 'blocks', blocks)
        for name in ('score3_penalty_flag_004c', 'score3_penalty_flag_004d',
                     'default_score'):
            object.__setattr__(self, name, f32(getattr(self, name)))


def classifier_config_from_runtime_bytes(data):
    """Decode fields relative to the classifier configuration object.

    For the pinned 0C19 image, initialization stores
    ``DAT_1808e0460 + 0xecc`` at tracker-context offset ``0x16480``. The
    enclosing product-record base is not valid input to this parser.
    """
    view = memoryview(data)
    if len(view) < RUNTIME_CONFIG_MIN_SIZE:
        raise ValueError(f'runtime config needs at least {RUNTIME_CONFIG_MIN_SIZE} bytes')

    def read_f32(offset):
        return struct.unpack_from('<f', view, offset)[0]

    blocks = []
    for block_index in range(SCORE_COUNT):
        base = 0x134 + block_index * 0x1d0
        rows = tuple(tuple(read_f32(base + row * 0x2c + column * 4)
                           for column in range(FEATURE_COUNT - row))
                     for row in range(FEATURE_COUNT))
        blocks.append(ScoreBlock(
            max_component_cells=struct.unpack_from(
                '<I', view, 0x870 + block_index * 4)[0],
            upper_rows=rows,
            means=tuple(read_f32(base + 0x198 + index * 4)
                        for index in range(FEATURE_COUNT)),
            base_penalty=read_f32(base + 0x190),
            limit_mode_0=read_f32(base + 0x1c0),
            limit_mode_1=read_f32(base + 0x1c4),
        ))
    return ClassifierConfig(
        forced_suppression=tuple(view[0x10c:0x116]),
        conditional_suppression=tuple(view[0x11c:0x126]),
        blocks=tuple(blocks),
        score3_penalty_flag_004c=read_f32(0x8d0),
        score3_penalty_flag_004d=read_f32(0x8d4),
    )


def candidate_input_from_record(record):
    """Decode only candidate fields directly read by FUN_180601690."""
    view = memoryview(record)
    if len(view) < 0xa0:
        raise ValueError('candidate record must contain at least 0xa0 bytes')
    features = (
        struct.unpack_from('<H', view, 0x9e)[0],
        view[0x99], view[0x9b], view[0x9d],
        view[0x98], view[0x9a], view[0x9c],
        struct.unpack_from('<f', view, 0x8c)[0],
        struct.unpack_from('<f', view, 0x90)[0],
        struct.unpack_from('<f', view, 0x94)[0],
    )
    return CandidateClassifierInput(
        features=features,
        component_cells_0038=struct.unpack_from('<H', view, 0x38)[0],
        flag_004c=view[0x4c],
        flag_004d=view[0x4d],
    )


def effective_suppression(config, dynamic_mask_byte):
    """Reproduce ``conditional[i] & dynamic | forced[i]`` for ten fields."""
    if type(dynamic_mask_byte) is not int or not 0 <= dynamic_mask_byte <= 255:
        raise ValueError('dynamic_mask_byte must be a byte')
    return tuple((conditional & dynamic_mask_byte) | forced
                 for forced, conditional in
                 zip(config.forced_suppression, config.conditional_suppression))


def score_block_f32(features, suppressed, block, *, mode_1, runtime_bias):
    """Evaluate one block with binary32 rounding after every arithmetic op."""
    runtime_bias = f32(runtime_bias)
    delta = tuple(
        0.0 if suppressed[index]
        else f32(features[index] - block.means[index])
        for index in range(FEATURE_COUNT)
    )
    transformed = []
    for row_index, row in enumerate(block.upper_rows):
        accumulator = 0.0
        for column_index, coefficient in enumerate(row, row_index):
            product = f32(coefficient * delta[column_index])
            accumulator = f32(accumulator + product)
        transformed.append(accumulator)
    squared_norm = 0.0
    for value in transformed:
        square = f32(value * value)
        squared_norm = f32(squared_norm + square)
    limit = block.limit_mode_1 if mode_1 else block.limit_mode_0
    base_half = f32(block.base_penalty * WINDOWS_NORM_SCALE)
    result = f32(limit - base_half)
    result = f32(result + runtime_bias)
    norm_half = f32(squared_norm * WINDOWS_NORM_SCALE)
    return f32(result - norm_half)


def score_candidate(candidate, config, *, dynamic_mask_byte, mode_1=False,
                    runtime_bias=0.0):
    """Return four common-path scores before unresolved override paths."""
    if not isinstance(candidate, CandidateClassifierInput):
        raise TypeError('candidate must be CandidateClassifierInput')
    if not isinstance(config, ClassifierConfig):
        raise TypeError('config must be ClassifierConfig')
    if type(mode_1) is not bool:
        raise ValueError('mode_1 must be bool')
    runtime_bias = f32(runtime_bias)
    suppressed = effective_suppression(config, dynamic_mask_byte)
    scores = []
    for block in config.blocks:
        if candidate.component_cells_0038 <= block.max_component_cells:
            score = score_block_f32(candidate.features, suppressed, block,
                                    mode_1=mode_1,
                                    runtime_bias=runtime_bias)
        else:
            score = config.default_score
        scores.append(score)
    if candidate.flag_004c == 1:
        scores[3] = f32(scores[3] - config.score3_penalty_flag_004c)
    elif candidate.flag_004d == 1:
        scores[3] = f32(scores[3] - config.score3_penalty_flag_004d)
    return tuple(scores)
