#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Clean-room model of the recovered FUN_180601690 score kernel.

Names intentionally describe storage and arithmetic, not unproved Windows
contact classes.  This module does not choose a class, emit a contact, or
provide configuration coefficients: the runtime 0C19 configuration has not
yet been captured.
"""

from dataclasses import dataclass
import math
import struct


FEATURE_COUNT = 10
SCORE_COUNT = 4
WINDOWS_DEFAULT_SCORE = -9999.0
WINDOWS_NORM_SCALE = 0.5
RUNTIME_CONFIG_MIN_SIZE = 0x8d8


def _finite_tuple(values, size, label):
    values = tuple(float(value) for value in values)
    if len(values) != size:
        raise ValueError(f'{label} must contain {size} values')
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f'{label} must contain only finite values')
    return values


def _byte_tuple(values, size, label):
    values = tuple(values)
    if len(values) != size or any(type(value) is not int or not 0 <= value <= 255
                                  for value in values):
        raise ValueError(f'{label} must contain {size} bytes')
    return values


@dataclass(frozen=True)
class CandidateClassifierInput:
    """Fields consumed by the recovered four-score kernel.

    ``features`` preserves the exact field order observed in FUN_180601690:
    candidate offsets 009e:u16, 0099:u8, 009b:u8, 009d:u8, 0098:u8,
    009a:u8, 009c:u8, 008c:f32, 0090:f32, 0094:f32.
    """

    features: tuple
    component_cells_0038: int
    flag_004c: int = 0
    flag_004d: int = 0

    def __post_init__(self):
        object.__setattr__(self, 'features',
                           _finite_tuple(self.features, FEATURE_COUNT, 'features'))
        if (type(self.component_cells_0038) is not int or
                not 0 <= self.component_cells_0038 <= 0xffff):
            raise ValueError('component_cells_0038 must be a u16')
        for name in ('flag_004c', 'flag_004d'):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 255:
                raise ValueError(f'{name} must be a byte')


@dataclass(frozen=True)
class ScoreBlock:
    """One 0x1d0-byte score block, represented without guessed semantics."""

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
        rows = tuple(tuple(float(value) for value in row) for row in self.upper_rows)
        if (len(rows) != FEATURE_COUNT or
                any(len(row) != FEATURE_COUNT - index
                    for index, row in enumerate(rows))):
            raise ValueError('upper_rows must have lengths 10, 9, ..., 1')
        if not all(math.isfinite(value) for row in rows for value in row):
            raise ValueError('upper_rows must contain only finite values')
        object.__setattr__(self, 'upper_rows', rows)
        object.__setattr__(self, 'means',
                           _finite_tuple(self.means, FEATURE_COUNT, 'means'))
        for name in ('base_penalty', 'limit_mode_0', 'limit_mode_1'):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f'{name} must be finite')
            object.__setattr__(self, name, value)


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
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f'{name} must be finite')
            object.__setattr__(self, name, value)


def classifier_config_from_runtime_bytes(data):
    """Decode the recovered fields from a *runtime* 0C19 config snapshot.

    The DLL's on-disk ``DAT_1808e0460`` bytes are not such a snapshot: this
    parser intentionally rejects their non-finite float interpretation.  A
    usable snapshot must be collected after the Windows initialization path.
    """
    view = memoryview(data)
    if len(view) < RUNTIME_CONFIG_MIN_SIZE:
        raise ValueError(f'runtime config needs at least {RUNTIME_CONFIG_MIN_SIZE} bytes')

    def f32(offset):
        return struct.unpack_from('<f', view, offset)[0]

    blocks = []
    for block_index in range(SCORE_COUNT):
        base = 0x134 + block_index * 0x1d0
        rows = tuple(tuple(f32(base + row * 0x2c + column * 4)
                           for column in range(FEATURE_COUNT - row))
                     for row in range(FEATURE_COUNT))
        blocks.append(ScoreBlock(
            max_component_cells=struct.unpack_from('<I', view,
                                                    0x870 + block_index * 4)[0],
            upper_rows=rows,
            means=tuple(f32(base + 0x198 + index * 4)
                        for index in range(FEATURE_COUNT)),
            base_penalty=f32(base + 0x190),
            limit_mode_0=f32(base + 0x1c0),
            limit_mode_1=f32(base + 0x1c4),
        ))
    return ClassifierConfig(
        forced_suppression=tuple(view[0x10c:0x116]),
        conditional_suppression=tuple(view[0x11c:0x126]),
        blocks=tuple(blocks),
        score3_penalty_flag_004c=f32(0x8d0),
        score3_penalty_flag_004d=f32(0x8d4),
    )


def candidate_input_from_record(record):
    """Decode only the candidate fields directly read by FUN_180601690."""
    view = memoryview(record)
    if len(view) < 0xa0:
        raise ValueError('candidate record must contain at least 0xa0 bytes')
    features = (
        float(struct.unpack_from('<H', view, 0x9e)[0]),
        float(view[0x99]), float(view[0x9b]), float(view[0x9d]),
        float(view[0x98]), float(view[0x9a]), float(view[0x9c]),
        float(struct.unpack_from('<f', view, 0x8c)[0]),
        float(struct.unpack_from('<f', view, 0x90)[0]),
        float(struct.unpack_from('<f', view, 0x94)[0]),
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


def _block_score(features, suppressed, block, *, mode_1, runtime_bias):
    delta = tuple(0.0 if suppressed[index] else features[index] - block.means[index]
                  for index in range(FEATURE_COUNT))
    transformed = []
    for row_index, row in enumerate(block.upper_rows):
        transformed.append(sum(coefficient * delta[column_index]
                               for column_index, coefficient in
                               enumerate(row, row_index)))
    squared_norm = sum(value * value for value in transformed)
    limit = block.limit_mode_1 if mode_1 else block.limit_mode_0
    return (limit - block.base_penalty * WINDOWS_NORM_SCALE + runtime_bias -
            squared_norm * WINDOWS_NORM_SCALE)


def score_candidate(candidate, config, *, dynamic_mask_byte, mode_1=False,
                    runtime_bias=0.0):
    """Return the four recovered scores before unresolved override paths.

    The score-3 edge penalty is included because its control flow and constants
    are explicit.  FUN_180605550 overrides and the spatial +100 adjustment are
    deliberately excluded; their upstream predicates are not represented here.
    """
    if not isinstance(candidate, CandidateClassifierInput):
        raise TypeError('candidate must be CandidateClassifierInput')
    if not isinstance(config, ClassifierConfig):
        raise TypeError('config must be ClassifierConfig')
    runtime_bias = float(runtime_bias)
    if not math.isfinite(runtime_bias):
        raise ValueError('runtime_bias must be finite')
    suppressed = effective_suppression(config, dynamic_mask_byte)
    scores = []
    for block in config.blocks:
        if candidate.component_cells_0038 <= block.max_component_cells:
            score = _block_score(candidate.features, suppressed, block,
                                 mode_1=bool(mode_1), runtime_bias=runtime_bias)
        else:
            score = config.default_score
        scores.append(score)
    if candidate.flag_004c == 1:
        scores[3] -= config.score3_penalty_flag_004c
    elif candidate.flag_004d == 1:
        scores[3] -= config.score3_penalty_flag_004d
    return tuple(scores)
