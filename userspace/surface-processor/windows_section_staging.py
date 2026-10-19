#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Recovered Windows CapImg ``0x0100`` section staging behavior.

This module transcribes ``FUN_18068e990`` from the hash-pinned
TouchPenProcessor0C19 DLL. The section itself does not carry width or height;
Windows loads them from the selected PSDB configuration record. The pinned
0C19 record configures stream 0 as 72 columns by 48 rows.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from windows_classifier import f32


HEATMAP_SECTION_TYPE = 0x0100
WINDOWS_ROW_STRIDE = 0x120
WINDOWS_8BIT_RETURN_LENGTH = 0xB468
WINDOWS_16BIT_RETURN_LENGTH = 0xB467
PSDB_STREAM_RECORD_SIZE = 0x3C
PSDB_HEIGHT_OFFSET = 0x3C
PSDB_WIDTH_OFFSET = 0x3E
WINDOWS_0C19_STREAM0_WIDTH = 72
WINDOWS_0C19_STREAM0_HEIGHT = 48


@dataclass(frozen=True)
class HeatRun:
    destination: int
    sample_count: int
    samples: bytes


@dataclass(frozen=True)
class StagedHeatmap:
    width: int
    height: int
    row_stride: int
    encoding: int
    pixels: bytes
    direct_view: bool
    windows_return_length: int
    runs: tuple[HeatRun, ...]
    provenance: str = 'TouchPenProcessor0C19!FUN_18068e990'

    def packed_active_grid(self) -> bytes:
        """Pack the explicit active rectangle, failing on impossible geometry."""
        # Windows returns a full 8-bit run as its original packed sample view.
        # Converted 16-bit runs are also written at packed destinations. Only
        # copied 8-bit partial/multi-run data uses the 288-byte staging stride.
        source_stride = (self.row_stride
                         if self.encoding == 1 and not self.direct_view
                         else self.width)
        if self.width > source_stride:
            raise ValueError('width exceeds source row stride')
        required = (self.height - 1) * source_stride + self.width
        if required > len(self.pixels):
            raise ValueError('staged buffer cannot satisfy supplied geometry')
        if source_stride == self.width:
            return self.pixels[:self.width * self.height]
        return b''.join(
            self.pixels[row * source_stride:
                        row * source_stride + self.width]
            for row in range(self.height)
        )


def read_psdb_stream_geometry(config: bytes, stream_index: int = 0,
                              ) -> tuple[int, int]:
    """Read ``(width, height)`` from a selected PSDB configuration record."""
    if not isinstance(config, bytes):
        raise TypeError('config must be bytes')
    if type(stream_index) is not int or stream_index < 0:
        raise ValueError('stream_index must be a non-negative integer')
    record = stream_index * PSDB_STREAM_RECORD_SIZE
    end = record + PSDB_WIDTH_OFFSET + 2
    if end > len(config):
        raise ValueError('truncated PSDB stream geometry')
    height = struct.unpack_from('<H', config, record + PSDB_HEIGHT_OFFSET)[0]
    width = struct.unpack_from('<H', config, record + PSDB_WIDTH_OFFSET)[0]
    return width, height


def _validate_geometry(width: int, height: int, row_stride: int) -> None:
    for value, name in ((width, 'width'), (height, 'height'),
                        (row_stride, 'row_stride')):
        if type(value) is not int or value <= 0 or value > 0xFFFF:
            raise ValueError(f'{name} must be a positive u16')
    if row_stride != WINDOWS_ROW_STRIDE:
        raise ValueError('recovered Windows row stride must be 288')
    if width > row_stride:
        raise ValueError('width exceeds physical row stride')


def _parse_runs(section: bytes) -> tuple[int, tuple[HeatRun, ...]]:
    if not isinstance(section, bytes):
        raise TypeError('section must be bytes')
    if len(section) < 7:
        raise ValueError('truncated heatmap section')
    section_length, section_type = struct.unpack_from('<IH', section)
    if section_length != len(section) or section_type != HEATMAP_SECTION_TYPE:
        raise ValueError('invalid heatmap section header')
    encoding = section[6]
    if encoding == 1:
        if len(section) < 8 or section[7] != 8:
            raise ValueError('invalid 8-bit heatmap encoding')
        offset, sample_width = 8, 1
    elif encoding == 0:
        offset, sample_width = 7, 2
    else:
        raise ValueError('unsupported heatmap encoding')

    runs = []
    while offset < len(section):
        if len(section) - offset < 8:
            raise ValueError('truncated heatmap run header')
        destination, sample_count = struct.unpack_from('<II', section, offset)
        offset += 8
        byte_count = sample_count * sample_width
        if byte_count > len(section) - offset:
            raise ValueError('truncated heatmap run samples')
        runs.append(HeatRun(destination, sample_count,
                            section[offset:offset + byte_count]))
        offset += byte_count
    if not runs:
        raise ValueError('heatmap section has no runs')
    return encoding, tuple(runs)


def convert_u16_sample(sample: int, scale: float, bias: float) -> int:
    """Apply the recovered binary32 calibration, truncation, and clamp."""
    if type(sample) is not int or not 0 <= sample <= 0xFFFF:
        raise ValueError('sample must be a u16')
    converted = int(f32(f32(f32(float(sample)) * f32(scale)) + f32(bias)))
    return min(255, max(0, converted))


def stage_heatmap_section(section: bytes, *, width: int, height: int,
                          scale: float = 1.0, bias: float = 0.0,
                          row_stride: int = WINDOWS_ROW_STRIDE,
                          ) -> StagedHeatmap:
    """Stage a validated section using the recovered Windows operation order.

    The 8-bit full-frame fast path returns the first run's bytes directly when
    its count equals ``width * height``. Multi-run 8-bit destinations are
    translated from packed coordinates to the 288-byte staging stride once per
    run, followed by a contiguous copy. Encoding 0 converts each little-endian
    u16 through binary32 scale/bias arithmetic and truncates toward zero.
    """
    _validate_geometry(width, height, row_stride)
    encoding, runs = _parse_runs(section)
    active_count = width * height

    if encoding == 1 and runs[0].sample_count == active_count:
        return StagedHeatmap(
            width, height, row_stride, encoding, runs[0].samples, True,
            WINDOWS_8BIT_RETURN_LENGTH, runs)

    buffer_size = max(WINDOWS_8BIT_RETURN_LENGTH,
                      (height - 1) * row_stride + width)
    staging = bytearray(buffer_size)
    if encoding == 1:
        for run in runs:
            row = run.destination // width
            target = run.destination + (row_stride - width) * row
            end = target + run.sample_count
            if target >= buffer_size or end > buffer_size:
                raise ValueError('8-bit run exceeds staging buffer')
            staging[target:end] = run.samples
        return_length = WINDOWS_8BIT_RETURN_LENGTH
    else:
        scale, bias = f32(scale), f32(bias)
        for run in runs:
            end = run.destination + run.sample_count
            if run.destination >= buffer_size or end > buffer_size:
                raise ValueError('16-bit run exceeds staging buffer')
            for index in range(run.sample_count):
                sample = struct.unpack_from('<H', run.samples, index * 2)[0]
                staging[run.destination + index] = convert_u16_sample(
                    sample, scale, bias)
        return_length = WINDOWS_16BIT_RETURN_LENGTH

    return StagedHeatmap(width, height, row_stride, encoding, bytes(staging),
                         False, return_length, runs)
