#!/usr/bin/env python3
"""Verify a real Linux suspend interval via CLOCK_BOOTTIME - MONOTONIC.

CLOCK_BOOTTIME advances through suspend, while CLOCK_MONOTONIC normally
doesn't. A no-op systemctl command must never be mistaken for an s2idle pass.
This checks elapsed suspend time independently of wall-clock/NTP changes.
"""
import argparse
import json
from pathlib import Path
import sys
import time


def snapshot():
    return {
        "monotonic": time.monotonic(),
        "boottime": time.clock_gettime(time.CLOCK_BOOTTIME),
        "wall_utc_epoch": time.time(),
    }


def sleep_seconds(before, after):
    elapsed_boot = after["boottime"] - before["boottime"]
    elapsed_mono = after["monotonic"] - before["monotonic"]
    if elapsed_mono < 0 or elapsed_boot < 0:
        raise ValueError("invalid clocks or host rebooted")
    return elapsed_boot - elapsed_mono


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--verify", nargs=2, type=Path,
                        metavar=("BEFORE", "AFTER"))
    parser.add_argument("--min-suspend-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if bool(args.snapshot) == bool(args.verify):
        parser.error("provide exactly one of --snapshot or --verify")
    if args.snapshot:
        args.snapshot.write_text(json.dumps(snapshot(), sort_keys=True) + "\n")
        return 0
    try:
        before, after = (json.loads(p.read_text()) for p in args.verify)
        secs = sleep_seconds(before, after)
    except (ValueError, KeyError, OSError, TypeError) as e:
        print(f"SUSPEND CLOCK CHECK: INCONCLUSIVE ({e})", file=sys.stderr)
        return 1
    print(f"SUSPEND CLOCK CHECK: {secs:.3f}s of boottime-not-monotonic elapsed")
    if secs < args.min_suspend_seconds:
        print("SUSPEND CLOCK CHECK: FAIL; actual sleep time unproven",
              file=sys.stderr)
        return 1
    print("SUSPEND CLOCK CHECK: PASS; real suspend interval detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
