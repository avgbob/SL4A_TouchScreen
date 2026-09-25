#!/usr/bin/env python3
"""Host-only invariants for the minimal sl4a-heat Gate-3 client."""

import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLIENT = ROOT / "userspace" / "sl4a-heat" / "sl4a_heat.py"

spec = importlib.util.spec_from_file_location("sl4a_heat", CLIENT)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load sl4a_heat.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def check(cond, message):
    if not cond:
        raise AssertionError(message)


def main():
    check(mod.HIDIOCGRAWINFO == 0x80084803, "HIDIOCGRAWINFO ioctl encoding drifted")
    check(mod.hid_iocgfeature(120) == 0xC0784807, "HIDIOCGFEATURE(120) encoding drifted")
    check(mod.hid_iocsfeature(2) == 0xC0024806, "HIDIOCSFEATURE(2) encoding drifted")

    check(mod.EXPECTED_RDESC_SIZE == 936, "Gate-2 descriptor length drifted")
    check(mod.ID6_BUFFER_LEN == 120, "ID6 HID ABI length drifted")
    check(mod.HEAT_REPORT_LEN == 4300, "0x0c HID ABI length drifted")

    good = bytes([mod.HEAT_REPORT]) + bytes(mod.HEAT_REPORT_LEN - 1)
    wrong_id = bytes([0x40]) + bytes(mod.HEAT_REPORT_LEN - 1)
    short = good[:-1]
    check(mod.is_heat_frame(good), "full 0x0c report rejected")
    check(not mod.is_heat_frame(wrong_id), "wrong report ID accepted")
    check(not mod.is_heat_frame(short), "truncated 0x0c report accepted")

    print("sl4a_heat_host_test: PASS")


if __name__ == "__main__":
    main()
