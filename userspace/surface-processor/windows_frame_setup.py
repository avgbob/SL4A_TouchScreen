#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Recovered Windows per-frame threshold selection before the initial CCL.

``FUN_1806003b0`` takes the maximum of a per-frame u16 metadata array.
``FUN_180600820`` uses that maximum to select and clamp one signal threshold
from the processing configuration at selected PSDB offset ``+0xecc``.  It then
passes the staged byte grid directly to ``FUN_180604ab0``; no pixel baseline
subtraction or gain conversion occurs in this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct

from windows_classifier import f32


WINDOWS_0C19_FRAME_CONFIG_OFFSET = 0xECC
FRAME_THRESHOLD_COUNT_OFFSET = 0x10
FRAME_THRESHOLD_STEPS_OFFSET = 0x14
FRAME_THRESHOLD_STEP_SIZE = 8


def _f32_from_bits(bits: int) -> float:
    return struct.unpack('<f', struct.pack('<I', bits))[0]


@dataclass(frozen=True)
class FrameSignalSchedule:
    lower: float
    upper: float
    minimum_peak_signal: float
    steps: tuple[tuple[float, int], ...]
    provenance: str = 'TouchPenProcessor0C19!FUN_1806003b0/FUN_180600820'

    def __post_init__(self) -> None:
        lower = f32(self.lower)
        upper = f32(self.upper)
        minimum_peak = f32(self.minimum_peak_signal)
        if lower > upper:
            raise ValueError('lower threshold exceeds upper threshold')
        if not 1 <= len(self.steps) <= 256:
            raise ValueError('threshold schedule must contain 1..256 steps')
        normalized = []
        for threshold, cutoff in self.steps:
            threshold = f32(threshold)
            if type(cutoff) is not int or not 0 <= cutoff <= 0xFFFFFFFF:
                raise ValueError('threshold cutoff must be a u32')
            normalized.append((threshold, cutoff))
        object.__setattr__(self, 'lower', lower)
        object.__setattr__(self, 'upper', upper)
        object.__setattr__(self, 'minimum_peak_signal', minimum_peak)
        object.__setattr__(self, 'steps', tuple(normalized))

    @classmethod
    def from_config_bytes(cls, config: bytes) -> 'FrameSignalSchedule':
        """Parse the fields addressed by ``FUN_180600820``."""
        if not isinstance(config, bytes):
            raise TypeError('config must be bytes')
        if len(config) < FRAME_THRESHOLD_STEPS_OFFSET:
            raise ValueError('truncated frame threshold configuration')
        lower, upper = struct.unpack_from('<ff', config)
        minimum_peak = struct.unpack_from('<f', config, 0x0C)[0]
        count = struct.unpack_from('<I', config,
                                   FRAME_THRESHOLD_COUNT_OFFSET)[0]
        if not 1 <= count <= 256:
            raise ValueError('threshold step count must be in 1..256')
        required = FRAME_THRESHOLD_STEPS_OFFSET + count * FRAME_THRESHOLD_STEP_SIZE
        if required > len(config):
            raise ValueError('truncated frame threshold steps')
        steps = tuple(struct.unpack_from('<fI', config,
                                         FRAME_THRESHOLD_STEPS_OFFSET +
                                         index * FRAME_THRESHOLD_STEP_SIZE)
                      for index in range(count))
        return cls(lower, upper, minimum_peak, steps)

    def select(self, maximum_metric: int) -> float:
        """Select a threshold with the recovered u8-index loop and clamps."""
        if type(maximum_metric) is not int or not 0 <= maximum_metric <= 0xFFFF:
            raise ValueError('maximum_metric must be a u16')
        index = 0
        if len(self.steps) != 1:
            while True:
                if maximum_metric < self.steps[index][1]:
                    break
                index += 1
                if index >= len(self.steps) - 1:
                    break
        selected = self.steps[index][0]
        if selected <= self.lower:
            selected = self.lower
        if self.upper <= selected:
            selected = self.upper
        return selected


def maximum_frame_metric(values) -> int:
    """Return ``FUN_1806003b0``'s maximum over the frame's u16 metadata."""
    maximum = 0
    for value in values:
        if type(value) is not int or not 0 <= value <= 0xFFFF:
            raise ValueError('frame metric values must be u16')
        maximum = max(maximum, value)
    return maximum


_WINDOWS_0C19_STEP_BITS = (
    (0x3CCCCCCD, 41), (0x3CF5C28F, 59), (0x3D0F5C29, 80),
    (0x3D23D70A, 105), (0x3D3851EC, 133), (0x3D4CCCCD, 164),
    (0x3D6147AE, 198), (0x3D75C28F, 236), (0x3D851EB8, 277),
    (0x3D8F5C29, 321), (0x3D99999A, 369), (0x3DA3D70A, 419),
    (0x3DAE147B, 473), (0x3DB851EC, 531), (0x3DC28F5C, 591),
    (0x3DCCCCCD, 655), (0x3DD70A3D, 722), (0x3DE147AE, 793),
    (0x3DEB851F, 867), (0x3DF5C28F, 944),
)

WINDOWS_0C19_FRAME_SIGNAL_SCHEDULE = FrameSignalSchedule(
    lower=_f32_from_bits(0x3D23D70A),
    upper=_f32_from_bits(0x3DF5C28F),
    minimum_peak_signal=_f32_from_bits(0x3D6147AE),
    steps=tuple((_f32_from_bits(bits), cutoff)
                for bits, cutoff in _WINDOWS_0C19_STEP_BITS),
)
