#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Clean-room model of the recovered Windows four-score transition gates.

This module models FUN_180607050 and FUN_1806071c0 only.  It deliberately does
not model the surrounding FUN_1806067d0 state machine, later corrections, or
the semantic meaning of numeric classes 0..4.
"""

from dataclasses import dataclass
import math
import struct


SCORE_COUNT = 4
STORED_CLASS_COUNT = 5
TRANSITION_CELL_BASE = 0x8d8
TRANSITION_CELL_STRIDE = 0x30
MODE1_WINDOW_ADD_BASE = 0x92a
MODE1_CANDIDATE_BIAS_OFFSET = 0x8f2
TRANSITION_CONFIG_MIN_SIZE = (
    MODE1_WINDOW_ADD_BASE +
    (STORED_CLASS_COUNT * SCORE_COUNT - 1) * TRANSITION_CELL_STRIDE + 1
)


def _scores(values, label):
    values = tuple(float(value) for value in values)
    if len(values) != SCORE_COUNT:
        raise ValueError(f'{label} must contain four scores')
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f'{label} must contain only finite values')
    return values


def _numeric_class(value, *, stored=False):
    limit = STORED_CLASS_COUNT if stored else SCORE_COUNT
    if type(value) is not int or not 0 <= value < limit:
        kind = 'stored class' if stored else 'proposed class'
        raise ValueError(f'{kind} must be in range 0..{limit - 1}')
    return value


@dataclass(frozen=True)
class TransitionCell:
    """One old-class/proposed-class gate entry, without semantic names."""

    history_margins: tuple
    current_margins: tuple
    absolute_floor: int
    candidate_flag_bias: int
    history_window: int
    mode1_current_enabled: bool
    mode1_history_window_add: int

    def __post_init__(self):
        for name in ('history_margins', 'current_margins'):
            values = tuple(getattr(self, name))
            if (len(values) != SCORE_COUNT or
                    any(type(value) is not int or
                        not -0x80000000 <= value <= 0x7fffffff
                        for value in values)):
                raise ValueError(f'{name} must contain four s32 values')
            object.__setattr__(self, name, values)
        if type(self.absolute_floor) is not int or not -32768 <= self.absolute_floor <= 32767:
            raise ValueError('absolute_floor must be an s16')
        for name in ('candidate_flag_bias', 'mode1_history_window_add'):
            value = getattr(self, name)
            if type(value) is not int or not -128 <= value <= 127:
                raise ValueError(f'{name} must be an s8')
        if type(self.history_window) is not int or not 0 <= self.history_window <= 255:
            raise ValueError('history_window must be a byte')
        if type(self.mode1_current_enabled) is not bool:
            raise ValueError('mode1_current_enabled must be bool')


@dataclass(frozen=True)
class TransitionConfig:
    """The recovered 5x4 numeric transition table and one global bias."""

    cells: tuple
    mode1_candidate_flag_bias: int

    def __post_init__(self):
        rows = tuple(tuple(row) for row in self.cells)
        if (len(rows) != STORED_CLASS_COUNT or
                any(len(row) != SCORE_COUNT for row in rows) or
                any(not isinstance(cell, TransitionCell)
                    for row in rows for cell in row)):
            raise ValueError('cells must be a 5x4 TransitionCell table')
        object.__setattr__(self, 'cells', rows)
        if (type(self.mode1_candidate_flag_bias) is not int or
                not -128 <= self.mode1_candidate_flag_bias <= 127):
            raise ValueError('mode1_candidate_flag_bias must be an s8')

    def cell(self, old_class, proposed_class):
        return self.cells[_numeric_class(old_class, stored=True)][
            _numeric_class(proposed_class)]


def transition_config_from_runtime_bytes(data):
    """Decode gate fields from bytes addressed by context ``+0x16480``."""
    view = memoryview(data)
    if len(view) < TRANSITION_CONFIG_MIN_SIZE:
        raise ValueError(f'transition config needs at least {TRANSITION_CONFIG_MIN_SIZE} bytes')

    def s8(offset):
        return struct.unpack_from('<b', view, offset)[0]

    rows = []
    for old_class in range(STORED_CLASS_COUNT):
        row = []
        for proposed_class in range(SCORE_COUNT):
            index = old_class * SCORE_COUNT + proposed_class
            base = TRANSITION_CELL_BASE + index * TRANSITION_CELL_STRIDE
            row.append(TransitionCell(
                history_margins=struct.unpack_from('<4i', view, base + 0x28),
                current_margins=struct.unpack_from('<4i', view, base + 0x3c),
                absolute_floor=struct.unpack_from('<h', view, base + 0x4c)[0],
                candidate_flag_bias=s8(base + 0x4e),
                history_window=view[base + 0x4f],
                mode1_current_enabled=view[base + 0x51] != 0,
                mode1_history_window_add=s8(
                    MODE1_WINDOW_ADD_BASE + index * TRANSITION_CELL_STRIDE),
            ))
        rows.append(tuple(row))
    return TransitionConfig(
        cells=tuple(rows),
        mode1_candidate_flag_bias=s8(MODE1_CANDIDATE_BIAS_OFFSET),
    )


def argmax_lower_tie(scores):
    """Return the largest of four scores, preserving the lower index on ties."""
    scores = _scores(scores, 'scores')
    winner = 0
    for index in range(1, SCORE_COUNT):
        if scores[index] > scores[winner]:
            winner = index
    return winner


def current_transition_gate(scores, old_class, proposed_class, config, *,
                            mode_1=False, candidate_flag=False,
                            spatial_special=False, spatial_margin_bias=0.0):
    """Model FUN_180607050's current-frame gate.

    ``spatial_special`` represents the separately recovered predicate for the
    numeric 4 -> 0 path.  It forces the current-frame absolute floor to 20 and
    adds ``spatial_margin_bias`` to pairwise margins.
    """
    scores = _scores(scores, 'scores')
    if not isinstance(config, TransitionConfig):
        raise TypeError('config must be TransitionConfig')
    for name, value in (('mode_1', mode_1),
                        ('candidate_flag', candidate_flag),
                        ('spatial_special', spatial_special)):
        if type(value) is not bool:
            raise ValueError(f'{name} must be bool')
    cell = config.cell(old_class, proposed_class)
    old_class = _numeric_class(old_class, stored=True)
    proposed_class = _numeric_class(proposed_class)
    if spatial_special and (old_class, proposed_class) != (4, 0):
        raise ValueError('spatial_special is valid only for numeric 4 -> 0')
    if mode_1 and not cell.mode1_current_enabled:
        return False
    flag_bias = 0
    if candidate_flag:
        flag_bias = cell.candidate_flag_bias
        if mode_1:
            flag_bias += config.mode1_candidate_flag_bias
    spatial_margin_bias = float(spatial_margin_bias)
    if not math.isfinite(spatial_margin_bias):
        raise ValueError('spatial_margin_bias must be finite')
    margin_bias = spatial_margin_bias if spatial_special else 0.0
    for competitor in range(SCORE_COUNT):
        if competitor != proposed_class:
            required = cell.current_margins[competitor] + flag_bias + margin_bias
            if scores[proposed_class] - scores[competitor] < required:
                return False
    absolute_floor = 20 if spatial_special else cell.absolute_floor
    return scores[proposed_class] >= absolute_floor + flag_bias


def history_transition_gate(history_scores, old_class, proposed_class, config, *,
                            mode_1=False, candidate_flag=False,
                            spatial_special=False, spatial_margin_bias=0.0):
    """Model FUN_1806071c0 over newest-first score samples."""
    old_class = _numeric_class(old_class, stored=True)
    proposed_class = _numeric_class(proposed_class)
    if not isinstance(config, TransitionConfig):
        raise TypeError('config must be TransitionConfig')
    for name, value in (('mode_1', mode_1),
                        ('candidate_flag', candidate_flag),
                        ('spatial_special', spatial_special)):
        if type(value) is not bool:
            raise ValueError(f'{name} must be bool')
    if old_class == proposed_class:
        return True
    if spatial_special and (old_class, proposed_class) != (4, 0):
        raise ValueError('spatial_special is valid only for numeric 4 -> 0')
    # Windows caps available track history at the ten-entry ring capacity.
    samples = tuple(_scores(sample, 'history sample')
                    for sample in history_scores)[:10]
    cell = config.cell(old_class, proposed_class)
    window = cell.history_window
    if mode_1:
        window = (window + cell.mode1_history_window_add) & 0xff
    if len(samples) < window:
        return False
    flag_bias = 0
    if candidate_flag:
        flag_bias = (config.mode1_candidate_flag_bias if mode_1
                     else cell.candidate_flag_bias)
    spatial_margin_bias = float(spatial_margin_bias)
    if not math.isfinite(spatial_margin_bias):
        raise ValueError('spatial_margin_bias must be finite')
    margin_bias = spatial_margin_bias if spatial_special else 0.0
    for scores in samples[:window]:
        for competitor in range(SCORE_COUNT):
            if competitor != proposed_class:
                required = cell.history_margins[competitor] + flag_bias + margin_bias
                if scores[proposed_class] - scores[competitor] < required:
                    return False
        if scores[proposed_class] < cell.absolute_floor + flag_bias:
            return False
    return True
