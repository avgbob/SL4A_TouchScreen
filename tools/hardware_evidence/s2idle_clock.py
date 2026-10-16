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



def wait_for_resume(before, output, minimum=2.0, timeout=75.0,
                    reader=None, clock=None, sleeper=None):
    """Wait after systemctl returns until a genuine sleep interval appears.

    systemctl can hand back control before the requested sleep is complete.
    A single immediate post-command snapshot would then misreport 0.000s
    and incorrectly skip all of the post-resume operator instructions.
    """
    reader = reader or snapshot
    clock = clock or time.monotonic
    sleeper = sleeper or time.sleep
    start = clock()
    last_log = -1
    while clock() - start < timeout:
        after = reader()
        output.write_text(json.dumps(after, sort_keys=True) + "\n")
        seconds = sleep_seconds(before, after)
        if seconds >= minimum:
            print(f"SUSPEND CLOCK CHECK: {seconds:.3f}s of confirmed sleep",
                  flush=True)
            print("SUSPEND CLOCK CHECK: PASS; resumed after real sleep",
                  flush=True)
            return True
        elapsed = int(clock() - start)
        if elapsed // 10 > last_log:
            print("Waiting for actual suspend/resume completion "
                  f"({elapsed}s since request; measured sleep "
                  f"{seconds:.3f}s).", flush=True)
            last_log = elapsed // 10
        sleeper(.25)
    print("SUSPEND CLOCK CHECK: INCONCLUSIVE; requested sleep did not "
          f"produce >= {minimum:.1f}s measured suspension within "
          f"{timeout:.0f}s. Do not begin touch tests.", file=sys.stderr,
          flush=True)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--verify", nargs=2, type=Path,
                        metavar=("BEFORE", "AFTER"))
    parser.add_argument("--wait-after", nargs=2, type=Path,
                        metavar=("BEFORE", "AFTER"),
                        help="poll until a real suspend gap appears, even if systemctl returned early")
    parser.add_argument("--timeout-seconds", type=float, default=75.0)
    parser.add_argument("--min-suspend-seconds", type=float, default=2.0)
    args = parser.parse_args()
    if sum(bool(x) for x in (args.snapshot, args.verify, args.wait_after)) != 1:
        parser.error("provide one of --snapshot, --verify, or --wait-after")
    if args.snapshot:
        args.snapshot.write_text(json.dumps(snapshot(), sort_keys=True) + "\n")
        return 0
    if args.wait_after:
        try:
            before = json.loads(args.wait_after[0].read_text())
            return 0 if wait_for_resume(
                before, args.wait_after[1],
                minimum=args.min_suspend_seconds,
                timeout=args.timeout_seconds) else 1
        except (ValueError, KeyError, OSError, TypeError) as exc:
            print(f"SUSPEND CLOCK CHECK: INCONCLUSIVE ({exc})", file=sys.stderr)
            return 1
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
