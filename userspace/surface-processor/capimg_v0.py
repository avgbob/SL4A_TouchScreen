#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Strict, side-effect-free decoder for MSHW0231 CapImg V0 frames.

The decoder accepts only the three observed transport envelopes or an explicit
72x48 raster used by offline tests. It does not access HID, SPI, uinput, or a
live device.
"""
from __future__ import annotations

from struct import unpack_from


COLS = 72
ROWS = 48
CELLS = COLS * ROWS
V0_REPORT_ID = 0x0C
HEATMAP_SECTION_TYPE = 0x0100
VENDOR_SECTION_TYPE = 0xFF00


def decode_frame(raw: bytes) -> bytes:
    """Return the 3,456-byte raster from one validated CapImg V0 frame.

    Accepted inputs are:

    - an explicit 3,456-byte raster for offline stage tests;
    - a 4,300-byte numbered HID report beginning with report ID ``0x0c``;
    - a 4,304-byte V0 body beginning ``ce 10 0c``;
    - an SPB payload with five ``0xff`` preamble bytes before the V0 body.

    Section lengths and required heatmap/vendor sections are validated. Fixed
    raster offsets are deliberately not assumed.
    """
    if not isinstance(raw, bytes):
        raise TypeError('raw frame must be bytes')
    if len(raw) == CELLS:
        return raw
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
            if (heatmap is not None or section_length != 16 + CELLS
                    or payload[offset + 6] != 1 or payload[offset + 7] != 8
                    or unpack_from('<I', payload, offset + 8)[0] != 0
                    or unpack_from('<I', payload, offset + 12)[0] != CELLS):
                raise ValueError('invalid or duplicate heatmap section')
            start = offset + 16
            heatmap = bytes(payload[start:start + CELLS])
        elif section_type == VENDOR_SECTION_TYPE:
            if vendor_seen:
                raise ValueError('duplicate vendor section')
            vendor_seen = True
        offset += section_length

    if offset != length or heatmap is None or not vendor_seen:
        raise ValueError('missing required heatmap/vendor section')
    return heatmap
