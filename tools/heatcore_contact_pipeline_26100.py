#!/usr/bin/env python3
"""Build-locked, offline Windows HeatCore contact byte-copy model.

Source: 401408-byte Windows HeatCore.dll 10.0.26100.9278, SHA256 pinned.
Models the observed record-copy operations for pointer input formats 1
(0x20 -> 0x3A -> 0x21) and 2 (0x24 -> 0x3C -> 0x23).
Does not model eligibility, identities, lifetimes, calibration, OS report
semantics, or prove the producer/consumer connection.
No Windows DLL content is embedded in this script.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_HASH = 'b295b095acf574007b894f841ef083e8cb06a72a256ee0bb75b4be80f2fcd5df'
CHECKS = {
    'pointer_1_first_flag_bit': (0x35050, '448442fe'),
    'pointer_1_second_flag_bit': (0x3505c, 'f642fe02'),
    'pointer_1_third_flag_bit': (0x35064, 'f642fe04'),
    'pointer_1_input_stride': (0x350a8, '4883c220'),
    'pointer_1_output_stride': (0x350ac, '4883c13a'),
    'pointer_2_flag_helper_bit_1': (0x34a87, '84d1'),
    'pointer_2_flag_helper_bit_2': (0x34a8f, 'f6c202'),
    'pointer_2_flag_helper_bit_4': (0x34a96, 'f6c204'),
    'pointer_2_input_stride': (0x35269, '4d8d5224'),
    'pointer_2_output_stride': (0x3526d, '4d8d493c'),
    'hid_1_input_stride': (0x14964, '486bc83a'),
    'hid_1_output_stride': (0x1495b, '486bd021'),
    'hid_1_packet_limit': (0x149c8, '4183f805'),
    'hid_2_input_stride': (0x14b52, '486bc83c'),
    'hid_2_output_stride': (0x14b4c, '486bd023'),
    'hid_2_packet_limit': (0x14b6a, '4183f805'),
}

# Field movement only. Source and destination offsets are zero-based.
# Matching layouts do not independently prove the two virtual calls connect.
COMMON_FROM_POINTER_TO_HID = [
    (8, 1, 2), (10, 0, 1), (19, 3, 4), (35, 7, 4),
    (43, 11, 4), (23, 15, 4), (39, 19, 4), (47, 23, 4),
    (51, 27, 2), (53, 29, 4),
]

def pointer_record(data: bytes, fmt: int) -> bytes:
    if fmt not in (1, 2):
        raise ValueError('Only two pointer reporter formats have been traced')
    need = 0x20 if fmt == 1 else 0x24
    size = 0x3a if fmt == 1 else 0x3c
    if len(data) != need:
        raise ValueError(f'Expected {need} raw bytes; got {len(data)}')
    out = bytearray(size)
    struct.pack_into('<Q', out, 0, size)
    out[8:10] = data[0:2]
    out[10] = data[2] & 0x07
    out[11:19] = out[19:27] = data[4:12]
    out[27:35] = out[35:43] = data[12:20]
    if fmt == 1:
        out[43:47] = data[20:24]
        out[47:51] = data[24:28]
        out[51:53] = data[28:30]
    else:
        out[43:47] = data[24:28]
        out[47:51] = data[28:32]
        out[51:53] = data[32:34]
        out[58:60] = data[20:22]
    return bytes(out)

def hid_record(intermediate: bytes, fmt: int) -> bytes:
    if fmt not in (1, 2):
        raise ValueError('Unsupported format')
    intermediate_size, size = ((0x3a, 0x21) if fmt == 1 else (0x3c, 0x23))
    if len(intermediate) != intermediate_size:
        raise ValueError('Unexpected intermediary size')
    out = bytearray(size)
    for src, dst, length in COMMON_FROM_POINTER_TO_HID:
        out[dst:dst+length] = intermediate[src:src+length]
    if fmt == 2:
        out[33:35] = intermediate[58:60]
    return bytes(out)

def rva_to_offset(data: bytes, rva: int, width: int) -> int:
    peoff = struct.unpack_from('<I', data, 0x3c)[0]
    if data[:2] != b'MZ' or data[peoff:peoff+4] != b'PE\x00\x00':
        raise ValueError('Not a PE image')
    count = struct.unpack_from('<H', data, peoff+6)[0]
    sec_header = peoff + 24 + struct.unpack_from('<H', data, peoff+20)[0]
    for i in range(count):
        p = sec_header + 40*i
        _, start, rawlen, offset = struct.unpack_from('<IIII', data, p+8)
        if start <= rva and rva+width <= start+rawlen:
            return offset + rva - start
    raise ValueError(f'RVA 0x{rva:x} not contained in on-disk PE section')

def verify(dll: Path):
    image = dll.read_bytes()
    h = hashlib.sha256(image).hexdigest()
    if h != EXPECTED_HASH:
        raise ValueError(f'Wrong binary hash {h}; requires {EXPECTED_HASH}')
    for label, (rva, code) in CHECKS.items():
        expected = bytes.fromhex(code)
        o = rva_to_offset(image, rva, len(expected))
        if image[o:o+len(expected)] != expected:
            raise AssertionError(f'{label}: wrong code bytes at RVA 0x{rva:x}')
    return {'sha256':h, 'verified_instruction_signatures':len(CHECKS),
            'signatures':{k:hex(v[0]) for k,v in CHECKS.items()}}

def selftest():
    for fmt in (1, 2):
        length = 0x20 if fmt == 1 else 0x24
        for bits in range(256):
            source = bytearray((i*29+31) & 0xff for i in range(length))
            source[0:2] = bytes.fromhex('cdab')
            source[2] = bits
            ptr = pointer_record(source, fmt)
            hid = hid_record(ptr, fmt)
            assert ptr[10] == bits & 7 and hid[0] == bits & 7
            assert ptr[8:10] == source[0:2] and hid[1:3] == source[0:2]
            assert hid[3:7] == source[4:8]
            assert hid[7:11] == source[12:16]
            assert hid[15:19] == source[8:12]
            assert hid[19:23] == source[16:20]
            if fmt == 1:
                assert len(ptr) == 58 and len(hid) == 33
                assert hid[11:15] == source[20:24]
                assert hid[23:27] == source[24:28]
                assert hid[27:29] == source[28:30]
                assert hid[29:33] == b'\0'*4
            else:
                assert len(ptr) == 60 and len(hid) == 35
                assert hid[11:15] == source[24:28]
                assert hid[23:27] == source[28:32]
                assert hid[27:29] == source[32:34]
                assert hid[29:33] == b'\0'*4
                assert hid[33:35] == source[20:22]
    return {'format1_vectors':256, 'format2_vectors':256,
            'conclusion':'Byte-copy modeling and flag/ID continuity only; not measured Windows end-user touches'}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('dll', type=Path, nargs='?', help='Optional private HeatCore.dll 26100.9278')
    args = p.parse_args()
    print(json.dumps({'binary': verify(args.dll) if args.dll else
                      'not checked (private DLL not supplied)',
                      'model_selftest':selftest()}, indent=2))
