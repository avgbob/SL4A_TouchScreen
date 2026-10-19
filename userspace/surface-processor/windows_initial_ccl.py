#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Initial Windows candidate CCL over an already converted byte grid.

This is a transcription of the main-pass behavior recovered from
``FUN_180604ab0``, ``FUN_180604fe0``, and ``FUN_180604bd0``.  It accepts the
converted byte grid consumed by TouchPenProcessor0C19; it does not claim that a
wire-format V0 heatmap can be passed here without the still-unrecovered
conversion stage.

The main pass uses row-major provisional labels, four already-visited
neighbours (left, upper-left, up, upper-right), equivalence merging, and one
0xb0-style accumulator per provisional component.  This is eight-connected
CCL, not the historical Linux four-connected approximation.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from windows_classifier import f32


WINDOWS_MAX_PROVISIONAL_LABELS = 0x30
WINDOWS_MAX_EQUIVALENCE_PAIRS = 0x2D0


def _f32_from_bits(bits: int) -> float:
    return struct.unpack('<f', struct.pack('<I', bits))[0]


WINDOWS_SIGNAL_ONE = _f32_from_bits(0x3F800000)
WINDOWS_SIGNAL_OFFSET = _f32_from_bits(0x3F19999A)
WINDOWS_SIGNAL_STEP = _f32_from_bits(0x3B11835D)
WINDOWS_WEIGHT_EPSILON = _f32_from_bits(0x38D1B717)


def windows_signal_lut() -> tuple[float, ...]:
    """Return the 255 initialized c590 entries from FUN_1805ff7e0.

    The Windows loop is strictly ``i < 0xff``.  Slot 255 is intentionally not
    invented here.
    """
    values = []
    for raw in range(0xFF):
        product = f32(f32(float(raw)) * WINDOWS_SIGNAL_STEP)
        values.append(f32(WINDOWS_SIGNAL_ONE -
                          f32(product + WINDOWS_SIGNAL_OFFSET)))
    return tuple(values)


WINDOWS_SIGNAL_LUT = windows_signal_lut()


def threshold_raw_index(signal_threshold: float) -> int:
    """Convert the selected signal threshold to FUN_180604ab0's raw byte gate."""
    signal_threshold = f32(signal_threshold)
    numerator = f32(f32(WINDOWS_SIGNAL_ONE - signal_threshold) -
                    WINDOWS_SIGNAL_OFFSET)
    quotient = f32(numerator / WINDOWS_SIGNAL_STEP)
    raw_index = int(f32(quotient + f32(0.5))) & 0xFF
    if raw_index == 0xFF:
        raise ValueError('threshold would require unresolved c590 slot 255')
    return raw_index


def adjusted_weight(raw_value: int, signal_threshold: float) -> float:
    """Return FUN_180604fe0's threshold-relative per-cell accumulator weight."""
    if type(raw_value) is not int or not 0 <= raw_value < 0xFF:
        raise ValueError('raw_value must index an initialized c590 slot (0..254)')
    threshold = f32(signal_threshold)
    baseline = f32(threshold - WINDOWS_SIGNAL_STEP)
    weight = f32(WINDOWS_SIGNAL_LUT[raw_value] - baseline)
    if weight <= WINDOWS_WEIGHT_EPSILON:
        weight = WINDOWS_WEIGHT_EPSILON
    return weight


@dataclass(frozen=True)
class InitialCandidate:
    """Recovered accumulator fields for one canonical provisional component."""

    label: int
    accepted: bool
    adjusted_sum: float
    adjusted_square_sum: float
    adjusted_x_sum: float
    adjusted_y_sum: float
    signal_sum: float
    signal_square_sum: float
    signal_x_sum: float
    signal_y_sum: float
    left: int
    top: int
    right: int
    bottom: int
    component_cells: int
    largest_unmerged_cells: int
    peak_raw_index: int

    def record_bytes(self) -> bytes:
        """Serialize the fields established by the initial pass in a 0xb0 record.

        Fields populated only by later Windows stages remain zero.  Rejected
        canonical records have status 4 and a cleared byte at offset 0x41.
        """
        record = bytearray(0xB0)
        for offset, value in zip(
                (0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x1C),
                (self.adjusted_sum, self.adjusted_square_sum,
                 self.adjusted_x_sum, self.adjusted_y_sum,
                 self.signal_sum, self.signal_square_sum,
                 self.signal_x_sum, self.signal_y_sum)):
            struct.pack_into('<f', record, offset, value)
        struct.pack_into('<HHHHHHHH', record, 0x30,
                         self.left, self.top, self.right, self.bottom,
                         self.component_cells, self.largest_unmerged_cells,
                         self.label - 1, 0)
        record[0x40] = 1 if self.accepted else 4
        record[0x41] = self.label if self.accepted else 0
        record[0x42] = self.label
        record[0x4B] = self.peak_raw_index
        return bytes(record)


@dataclass(frozen=True)
class InitialCclResult:
    width: int
    height: int
    threshold_raw: int
    eligible_cells: int
    provisional_label_count: int
    equivalence_pair_count: int
    accepted_count: int
    max_accepted_cells: int
    provisional_labels: bytes
    canonical_labels: tuple[int, ...]
    candidates: tuple[InitialCandidate, ...]
    provenance: str = ('FUN_180604ab0/FUN_180604fe0/FUN_180604bd0:'
                       'main converted-grid pass')


@dataclass
class _Record:
    label: int
    adjusted_sum: float = 0.0
    adjusted_square_sum: float = 0.0
    adjusted_x_sum: float = 0.0
    adjusted_y_sum: float = 0.0
    signal_sum: float = 0.0
    signal_square_sum: float = 0.0
    signal_x_sum: float = 0.0
    signal_y_sum: float = 0.0
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    component_cells: int = 0
    largest_unmerged_cells: int = 0
    peak_raw_index: int = 0xFF
    live: bool = True

    @classmethod
    def first_cell(cls, label: int, x: int, y: int, raw: int,
                   threshold: float) -> '_Record':
        signal = WINDOWS_SIGNAL_LUT[raw]
        weight = adjusted_weight(raw, threshold)
        return cls(
            label=label,
            adjusted_sum=weight,
            adjusted_square_sum=f32(weight * weight),
            adjusted_x_sum=f32(f32(float(x)) * weight),
            adjusted_y_sum=f32(f32(float(y)) * weight),
            signal_sum=signal,
            signal_square_sum=f32(signal * signal),
            signal_x_sum=f32(f32(float(x)) * signal),
            signal_y_sum=f32(f32(float(y)) * signal),
            left=x, top=y, right=x, bottom=y,
            component_cells=1,
            largest_unmerged_cells=1,
            peak_raw_index=raw,
        )

    def add_cell(self, x: int, y: int, raw: int, threshold: float) -> None:
        signal = WINDOWS_SIGNAL_LUT[raw]
        weight = adjusted_weight(raw, threshold)
        self.left = min(self.left, x)
        self.top = min(self.top, y)
        self.right = max(self.right, x)
        self.bottom = max(self.bottom, y)
        self.adjusted_sum = f32(weight + self.adjusted_sum)
        self.signal_sum = f32(signal + self.signal_sum)
        self.component_cells += 1
        self.adjusted_x_sum = f32(f32(float(x) * weight) + self.adjusted_x_sum)
        self.adjusted_y_sum = f32(f32(float(y) * weight) + self.adjusted_y_sum)
        self.signal_x_sum = f32(f32(float(x) * signal) + self.signal_x_sum)
        self.signal_y_sum = f32(f32(float(y) * signal) + self.signal_y_sum)
        self.adjusted_square_sum = f32(f32(weight * weight) +
                                           self.adjusted_square_sum)
        self.signal_square_sum = f32(f32(signal * signal) +
                                         self.signal_square_sum)
        self.largest_unmerged_cells = max(self.largest_unmerged_cells,
                                          self.component_cells)
        self.peak_raw_index = min(self.peak_raw_index, raw)

    def merge_from(self, source: '_Record') -> None:
        for name in ('adjusted_sum', 'adjusted_square_sum', 'adjusted_x_sum',
                     'adjusted_y_sum', 'signal_sum', 'signal_square_sum',
                     'signal_x_sum', 'signal_y_sum'):
            setattr(self, name, f32(getattr(source, name) + getattr(self, name)))
        self.left = min(self.left, source.left)
        self.top = min(self.top, source.top)
        self.right = max(self.right, source.right)
        self.bottom = max(self.bottom, source.bottom)
        self.component_cells += source.component_cells
        self.peak_raw_index = min(self.peak_raw_index, source.peak_raw_index)
        source.live = False


def initial_ccl(converted_grid: bytes, *, width: int, height: int,
                signal_threshold: float, minimum_peak_signal: float,
                max_labels: int = WINDOWS_MAX_PROVISIONAL_LABELS,
                max_equivalence_pairs: int = WINDOWS_MAX_EQUIVALENCE_PAIRS,
                ) -> InitialCclResult:
    """Run the recovered initial main-pass CCL on a packed converted grid.

    ``minimum_peak_signal`` is configuration float ``+0x0c`` used by
    FUN_180604bd0 to retain one- and two-cell components.  Components with more
    than two cells pass independently of this peak gate.
    """
    if not isinstance(converted_grid, bytes):
        raise TypeError('converted_grid must be bytes')
    for value, label in ((width, 'width'), (height, 'height')):
        if type(value) is not int or value <= 0 or value > 0xFFFF:
            raise ValueError(f'{label} must be a positive u16')
    if len(converted_grid) != width * height:
        raise ValueError('converted_grid length does not match width * height')
    if type(max_labels) is not int or not 1 <= max_labels <= 0xFF:
        raise ValueError('max_labels must be in 1..255')
    if (type(max_equivalence_pairs) is not int or
            max_equivalence_pairs <= 0 or max_equivalence_pairs > 0xFFFF):
        raise ValueError('max_equivalence_pairs must be in 1..65535')
    threshold = f32(signal_threshold)
    minimum_peak_signal = f32(minimum_peak_signal)
    raw_gate = threshold_raw_index(threshold)

    labels = bytearray(width * height)
    records: list[_Record | None] = [None]
    equivalences: list[tuple[int, int]] = []
    eligible_cells = 0

    for y in range(height):
        for x in range(width):
            index = y * width + x
            raw = converted_grid[index]
            if raw > raw_gate:
                continue
            eligible_cells += 1
            neighbours = []
            if x > 0:
                neighbours.append(labels[index - 1])
            if y > 0:
                if x > 0:
                    neighbours.append(labels[index - width - 1])
                neighbours.append(labels[index - width])
                if x + 1 < width:
                    neighbours.append(labels[index - width + 1])

            first = 0
            seen = set()
            for neighbour in neighbours:
                if neighbour == 0:
                    continue
                if first == 0:
                    first = neighbour
                    labels[index] = first
                    record = records[first]
                    if record is None:
                        raise AssertionError('missing provisional record')
                    record.add_cell(x, y, raw, threshold)
                elif neighbour != first and neighbour not in seen:
                    pair = (min(first, neighbour), max(first, neighbour))
                    # Windows suppresses duplicates only within this cell's
                    # neighbour list; repeated pairs in later cells consume
                    # additional entries in the fixed equivalence buffer.
                    if len(equivalences) + 1 >= max_equivalence_pairs:
                        raise OverflowError('Windows equivalence-pair capacity exceeded')
                    equivalences.append(pair)
                seen.add(neighbour)

            if first == 0:
                label = len(records)
                if label > max_labels:
                    raise OverflowError('Windows provisional-label capacity exceeded')
                labels[index] = label
                records.append(_Record.first_cell(label, x, y, raw, threshold))

    parent = list(range(len(records)))

    def find(label: int) -> int:
        while parent[label] != label:
            parent[label] = parent[parent[label]]
            label = parent[label]
        return label

    for left, right in equivalences:
        left_root, right_root = find(left), find(right)
        winner = min(left_root, right_root)
        parent[left_root] = winner
        parent[right_root] = winner

    canonical = tuple(find(label) for label in range(len(records)))
    for label in range(1, len(records)):
        target = canonical[label]
        if target == label:
            continue
        target_record = records[target]
        source_record = records[label]
        if target_record is None or source_record is None:
            raise AssertionError('missing merge record')
        target_record.merge_from(source_record)

    candidates = []
    accepted_count = 0
    max_accepted_cells = 0
    for label in range(1, len(records)):
        record = records[label]
        if record is None or not record.live:
            continue
        peak_signal = WINDOWS_SIGNAL_LUT[record.peak_raw_index]
        accepted = (record.component_cells > 2 or
                    (peak_signal >= minimum_peak_signal and
                     peak_signal != minimum_peak_signal))
        if accepted:
            accepted_count += 1
            max_accepted_cells = max(max_accepted_cells, record.component_cells)
        candidates.append(InitialCandidate(
            label=label,
            accepted=accepted,
            adjusted_sum=record.adjusted_sum,
            adjusted_square_sum=record.adjusted_square_sum,
            adjusted_x_sum=record.adjusted_x_sum,
            adjusted_y_sum=record.adjusted_y_sum,
            signal_sum=record.signal_sum,
            signal_square_sum=record.signal_square_sum,
            signal_x_sum=record.signal_x_sum,
            signal_y_sum=record.signal_y_sum,
            left=record.left, top=record.top,
            right=record.right, bottom=record.bottom,
            component_cells=record.component_cells,
            largest_unmerged_cells=record.largest_unmerged_cells,
            peak_raw_index=record.peak_raw_index,
        ))

    return InitialCclResult(
        width=width,
        height=height,
        threshold_raw=raw_gate,
        eligible_cells=eligible_cells,
        provisional_label_count=len(records) - 1,
        equivalence_pair_count=len(equivalences),
        accepted_count=accepted_count,
        max_accepted_cells=max_accepted_cells,
        provisional_labels=bytes(labels),
        canonical_labels=canonical,
        candidates=tuple(candidates),
    )
