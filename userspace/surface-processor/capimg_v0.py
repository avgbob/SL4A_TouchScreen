#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Strict, side-effect-free decoder for MSHW0231 CapImg V0 frames.

The decoder accepts only the three observed transport envelopes or an explicit
72x48 capture-analysis raster used by offline tests. It does not access HID,
SPI, uinput, or a live device.
"""
from __future__ import annotations

from struct import unpack_from


# Capture-analysis geometry; not yet proven as Windows detector coordinates.
COLS = 72
ROWS = 48
CELLS = COLS * ROWS
V0_REPORT_ID = 0x0C
HEATMAP_SECTION_TYPE = 0x0100
VENDOR_SECTION_TYPE = 0xFF00


def _validate_heatmap_section(section: bytes) -> None:
    if len(section) < 7:
        raise ValueError('truncated heatmap section')
    section_length, section_type = unpack_from('<IH', section)
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
    run_count = 0
    while offset < len(section):
        if len(section) - offset < 8:
            raise ValueError('truncated heatmap run header')
        sample_count = unpack_from('<I', section, offset + 4)[0]
        offset += 8
        sample_bytes = sample_count * sample_width
        if sample_bytes > len(section) - offset:
            raise ValueError('truncated heatmap run samples')
        offset += sample_bytes
        run_count += 1
    if run_count == 0:
        raise ValueError('heatmap section has no runs')


def decode_heatmap_section(raw: bytes) -> bytes:
    """Return the complete validated ``0x0100`` section from a V0 frame.

    A bare 3,456-byte capture-analysis raster is wrapped as the canonical
    single-run 8-bit section used by the retained fixtures. Width and height
    are deliberately not inferred from the section because Windows obtains
    those values from separate runtime configuration.
    """
    if not isinstance(raw, bytes):
        raise TypeError('raw frame must be bytes')
    if len(raw) == CELLS:
        return ((16 + CELLS).to_bytes(4, 'little') +
                HEATMAP_SECTION_TYPE.to_bytes(2, 'little') +
                bytes((1, 8)) + bytes(4) + CELLS.to_bytes(4, 'little') + raw)
    if raw.startswith(b'\xff' * 5):
        raw = raw[5:]
    if len(raw) == 4300 and raw[0] == V0_REPORT_ID:
        raw = (4302).to_bytes(2, 'little') + raw
    if not (4300 <= len(raw) <= 4400 and raw[:3] == b'\xce\x10\x0c'):
        raise ValueError('not a supported CapImg V0 frame')

    payload = memoryview(raw)[5:]
    if len(payload) < 7:
        raise ValueError('truncated V0 payload')
    length = unpack_from('<I', payload)[0]
    if (length < 7 or length > min(len(payload), 4297)
            or unpack_from('<H', payload, 4)[0] != 0 or payload[6] != 0):
        raise ValueError('invalid V0 container header')

    offset = 7
    heatmap = None
    vendor_seen = False
    while offset < length:
        if length - offset < 7:
            raise ValueError('truncated CapImg section header')
        section_length, section_type = unpack_from('<IH', payload, offset)
        if section_length < 7 or section_length > length - offset:
            raise ValueError('invalid CapImg section length')
        if section_type == HEATMAP_SECTION_TYPE:
            if heatmap is not None:
                raise ValueError('duplicate heatmap section')
            heatmap = bytes(payload[offset:offset + section_length])
            _validate_heatmap_section(heatmap)
        elif section_type == VENDOR_SECTION_TYPE:
            if vendor_seen:
                raise ValueError('duplicate vendor section')
            vendor_seen = True
        offset += section_length

    if offset != length or heatmap is None or not vendor_seen:
        raise ValueError('missing required heatmap/vendor section')
    return heatmap


def decode_frame(raw: bytes) -> bytes:
    """Return the observed 3,456-byte capture-analysis raster.

    Accepted inputs are:

    - an explicit 3,456-byte raster for offline stage tests;
    - a 4,300-byte numbered HID report beginning with report ID ``0x0c``;
    - a 4,304-byte V0 body beginning ``ce 10 0c``;
    - an SPB payload with five ``0xff`` preamble bytes before the V0 body.

    Section lengths and required heatmap/vendor sections are validated. This
    compatibility API accepts only the retained single-run 8-bit layout; use
    :func:`decode_heatmap_section` for Windows section staging research.
    """
    section = decode_heatmap_section(raw)
    if (len(section) != 16 + CELLS or section[6:8] != bytes((1, 8))
            or unpack_from('<I', section, 8)[0] != 0
            or unpack_from('<I', section, 12)[0] != CELLS):
        raise ValueError('heatmap is not the observed single-run raster')
    return section[16:]
