#!/usr/bin/env python3
"""Minimal Gate-3 userspace Heat transport client for MSHW0231.

This intentionally stops at the Architecture-A boundary:
  HID descriptor -> GET_FEATURE 6 -> SET_FEATURE 5=1 -> hidraw report 0x0c.

It does not decode CapImg, synthesize contacts, or create a uinput device.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import glob
import hashlib
import os
import pathlib
import select
import struct
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Optional

TARGET_VENDOR = 0x045E
TARGET_PRODUCT = 0x0C19
EXPECTED_RDESC_SIZE = 936
ID6_REPORT = 0x06
ID6_DATA_LEN = 119
ID6_BUFFER_LEN = 1 + ID6_DATA_LEN
ID5_REPORT = 0x05
ID5_ENABLE = 0x01
HEAT_REPORT = 0x0C
HEAT_REPORT_LEN = 4300

# Linux asm-generic/ioctl.h encoding.
_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS
_IOC_WRITE = 1
_IOC_READ = 2


def _ioc(direction: int, type_char: str, nr: int, size: int) -> int:
    return (
        (direction << _IOC_DIRSHIFT)
        | (ord(type_char) << _IOC_TYPESHIFT)
        | (nr << _IOC_NRSHIFT)
        | (size << _IOC_SIZESHIFT)
    )


def _ior(type_char: str, nr: int, size: int) -> int:
    return _ioc(_IOC_READ, type_char, nr, size)


HIDIOCGRAWINFO = _ior("H", 0x03, 8)


def hid_iocgfeature(length: int) -> int:
    return _ioc(_IOC_READ | _IOC_WRITE, "H", 0x07, length)


def hid_iocsfeature(length: int) -> int:
    return _ioc(_IOC_READ | _IOC_WRITE, "H", 0x06, length)


@dataclass
class HidrawDevice:
    path: pathlib.Path
    fd: int
    bustype: int
    vendor: int
    product: int


def _raw_info(fd: int) -> tuple[int, int, int]:
    buf = bytearray(8)
    fcntl.ioctl(fd, HIDIOCGRAWINFO, buf, True)
    bustype, vendor, product = struct.unpack("@Ihh", buf)
    return bustype, vendor & 0xFFFF, product & 0xFFFF


def _open_candidate(path: pathlib.Path) -> HidrawDevice:
    fd = os.open(path, os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        bustype, vendor, product = _raw_info(fd)
        return HidrawDevice(path, fd, bustype, vendor, product)
    except Exception:
        os.close(fd)
        raise


def enumerate_hidraw() -> Iterable[tuple[pathlib.Path, Optional[HidrawDevice], Optional[BaseException]]]:
    for name in sorted(glob.glob("/dev/hidraw*")):
        path = pathlib.Path(name)
        try:
            yield path, _open_candidate(path), None
        except BaseException as exc:
            yield path, None, exc


def find_target(explicit: Optional[str] = None) -> HidrawDevice:
    if explicit:
        dev = _open_candidate(pathlib.Path(explicit))
        if (dev.vendor, dev.product) != (TARGET_VENDOR, TARGET_PRODUCT):
            os.close(dev.fd)
            raise RuntimeError(
                f"{explicit} is {dev.vendor:04x}:{dev.product:04x}, "
                f"not {TARGET_VENDOR:04x}:{TARGET_PRODUCT:04x}"
            )
        return dev

    denied = []
    for path, dev, exc in enumerate_hidraw():
        if dev is None:
            if isinstance(exc, PermissionError):
                denied.append(str(path))
            continue
        if (dev.vendor, dev.product) == (TARGET_VENDOR, TARGET_PRODUCT):
            return dev
        os.close(dev.fd)

    suffix = ""
    if denied:
        suffix = " (permission denied on: " + ", ".join(denied) + ")"
    raise RuntimeError(
        f"no hidraw device for {TARGET_VENDOR:04x}:{TARGET_PRODUCT:04x}{suffix}"
    )


def descriptor_path(dev_path: pathlib.Path) -> pathlib.Path:
    return pathlib.Path("/sys/class/hidraw") / dev_path.name / "device" / "report_descriptor"


def read_descriptor(dev_path: pathlib.Path) -> bytes:
    path = descriptor_path(dev_path)
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise RuntimeError(f"report descriptor not available at {path}") from exc
    if len(data) != EXPECTED_RDESC_SIZE:
        raise RuntimeError(
            f"unexpected report descriptor length {len(data)}; "
            f"expected {EXPECTED_RDESC_SIZE}"
        )
    return data


def get_feature6(fd: int) -> bytes:
    buf = bytearray(ID6_BUFFER_LEN)
    buf[0] = ID6_REPORT
    rc = fcntl.ioctl(fd, hid_iocgfeature(len(buf)), buf, True)
    returned = rc if isinstance(rc, int) and rc > 0 else len(buf)
    if returned != ID6_BUFFER_LEN:
        raise RuntimeError(
            f"GET_FEATURE 6 returned {returned} bytes; expected {ID6_BUFFER_LEN}"
        )
    if buf[0] != ID6_REPORT:
        raise RuntimeError(
            f"GET_FEATURE 6 returned report ID 0x{buf[0]:02x}, expected 0x06"
        )
    return bytes(buf)


def set_feature5(fd: int) -> None:
    buf = bytearray((ID5_REPORT, ID5_ENABLE))
    rc = fcntl.ioctl(fd, hid_iocsfeature(len(buf)), buf, True)
    if isinstance(rc, int) and rc < 0:
        raise OSError(errno.EIO, f"HIDIOCSFEATURE returned {rc}")


def is_heat_frame(frame: bytes) -> bool:
    return len(frame) == HEAT_REPORT_LEN and frame[0] == HEAT_REPORT


def capture_heat_frames(
    fd: int,
    output_dir: pathlib.Path,
    wanted: int,
    timeout_s: float,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    poller = select.poll()
    poller.register(fd, select.POLLIN | select.POLLERR | select.POLLHUP)

    deadline = time.monotonic() + timeout_s
    kept = 0
    seen = 0
    lengths: dict[int, int] = {}

    while kept < wanted:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        events = poller.poll(max(1, int(remaining * 1000)))
        if not events:
            break

        for _, flags in events:
            if flags & (select.POLLERR | select.POLLHUP):
                raise RuntimeError(f"hidraw poll failed: flags=0x{flags:x}")
            if not (flags & select.POLLIN):
                continue

            try:
                frame = os.read(fd, 16384)
            except BlockingIOError:
                continue
            if not frame:
                continue

            seen += 1
            lengths[len(frame)] = lengths.get(len(frame), 0) + 1
            if not is_heat_frame(frame):
                continue

            kept += 1
            stamp = time.time_ns()
            out = output_dir / f"heat-{kept:06d}-{stamp}.bin"
            out.write_bytes(frame)
            print(
                f"0x0c frame {kept}/{wanted}: {len(frame)} bytes -> {out}",
                flush=True,
            )

    print(
        "capture summary: "
        f"seen={seen} heat_0c={kept} "
        f"lengths={','.join(f'{k}:{v}' for k, v in sorted(lengths.items())) or 'none'}"
    )
    return kept


def list_devices() -> int:
    found = 0
    for path, dev, exc in enumerate_hidraw():
        if dev is None:
            print(f"{path}: ERROR {exc}")
            continue
        try:
            mark = " TARGET" if (dev.vendor, dev.product) == (TARGET_VENDOR, TARGET_PRODUCT) else ""
            print(
                f"{path}: bus=0x{dev.bustype:x} "
                f"vid:pid={dev.vendor:04x}:{dev.product:04x}{mark}"
            )
            found += 1
        finally:
            os.close(dev.fd)
    return 0 if found else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gate-3 hidraw checkpoint client for Surface MSHW0231"
    )
    parser.add_argument("--device", help="explicit /dev/hidrawN path")
    parser.add_argument("--list", action="store_true", help="list accessible hidraw devices")
    parser.add_argument(
        "--output-dir",
        default="gate3-heat-capture",
        help="directory for raw 0x0c frames",
    )
    parser.add_argument("--frames", type=int, default=20, help="number of 0x0c frames to save")
    parser.add_argument("--timeout", type=float, default=20.0, help="capture timeout in seconds")
    parser.add_argument(
        "--no-arm",
        action="store_true",
        help="verify device/descriptor only; do not GET6/SET5 or capture",
    )
    args = parser.parse_args(argv)

    if args.list:
        return list_devices()
    if args.frames < 1:
        parser.error("--frames must be >= 1")
    if args.timeout <= 0:
        parser.error("--timeout must be > 0")

    dev = find_target(args.device)
    try:
        print(
            f"device: {dev.path} bus=0x{dev.bustype:x} "
            f"vid:pid={dev.vendor:04x}:{dev.product:04x}"
        )
        rdesc = read_descriptor(dev.path)
        print(
            f"report descriptor: {len(rdesc)} bytes "
            f"sha256={hashlib.sha256(rdesc).hexdigest()}"
        )

        if args.no_arm:
            print("descriptor checkpoint complete (--no-arm)")
            return 0

        id6 = get_feature6(dev.fd)
        print(
            f"GET_FEATURE 6: {len(id6)} HID bytes "
            f"(id=0x{id6[0]:02x}, data={len(id6) - 1}) "
            f"head={id6[:16].hex()}"
        )

        set_feature5(dev.fd)
        print("SET_FEATURE 5: payload=01 accepted")

        print(
            f"capture: touch/drag the panel now; waiting for "
            f"{args.frames} x {HEAT_REPORT_LEN}-byte report 0x0c"
        )
        kept = capture_heat_frames(
            dev.fd,
            pathlib.Path(args.output_dir),
            args.frames,
            args.timeout,
        )
        if kept != args.frames:
            print(
                f"GATE3 checkpoint incomplete: captured {kept}/{args.frames} heat frames",
                file=sys.stderr,
            )
            return 2

        print("GATE3 HIDRAW CHECKPOINT PASS")
        return 0
    finally:
        os.close(dev.fd)


if __name__ == "__main__":
    raise SystemExit(main())
