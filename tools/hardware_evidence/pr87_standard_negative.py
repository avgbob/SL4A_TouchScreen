#!/usr/bin/env python3
"""Read-only PR #87 standard-mode opt-out checker.

This is a *negative* control: ordinary HID discovery must initialize,
but the additional heatmap-based input device must NOT be registered.
Passive raw_observed may increase without any multitouch publication.
This does not prove Report 0x0c dispatch/absence from runtime silence.
"""
import argparse
import json
from pathlib import Path
import sys


def checked_read(path, errors):
    try:
        return path.read_text().strip()
    except OSError as exc:
        errors.append(f"unreadable {path.name}: {exc.__class__.__name__}")
        return None


def examine(root, expected_srcversion):
    root = Path(root)
    errors = []
    module = root / "module/sl4a_spi_hid"
    spi = root / "bus/spi/devices/spi-MSHW0231:00"
    params = module / "parameters"
    expected = {"raw_mode": {"N", "0"},
                "raw_input_beta": {"N", "0"},
                "std_raw_transition": {"0"}}
    observed = {}
    for key, valid in expected.items():
        value = checked_read(params / key, errors)
        observed[key] = value
        if value is not None and value not in valid:
            errors.append(f"{key}={value!r}, expected opt-out {sorted(valid)}")
    actual_source = checked_read(module / "srcversion", errors)
    if actual_source is not None and actual_source != expected_srcversion:
        errors.append("loaded module srcversion does not match signed PR87 binary")
    ready = checked_read(spi / "ready", errors)
    if ready is not None and ready != "1":
        errors.append(f"standard HID discovery not ready: ready={ready!r}")
    seq_state = checked_read(spi / "seq_state", errors)
    stats_raw = checked_read(spi / "protocol_stats", errors)
    stats = {}
    if stats_raw is not None:
        for row in stats_raw.splitlines():
            if "=" not in row:
                errors.append("malformed protocol_stats entry")
                continue
            key, value = row.split("=", 1)
            try:
                stats[key] = int(value)
            except ValueError:
                errors.append(f"non-numeric protocol_stats entry: {key}")
        for key in ("device_desc", "rpt_desc"):
            if stats.get(key, 0) < 1:
                errors.append(f"standard HID {key} not observed")
        for key in ("raw_observed", "data", "frames_dropped", "irq_count"):
            if key not in stats:
                errors.append(f"missing protocol_stats {key}")
    inventory = root / "class/input"
    bridge_entries = []
    if not inventory.is_dir():
        errors.append("sysfs input-device inventory unavailable")
    else:
        for entry in sorted(inventory.glob("input[0-9]*")):
            try:
                if (entry / "name").read_text().strip() == "MSHW0231 Touchscreen":
                    bridge_entries.append(entry.name)
            except OSError:
                # Unrelated devices can disappear during enumeration.
                continue
        if bridge_entries:
            errors.append("experimental MSHW0231 heatmap MT input registered in opt-out")
    return {
        "verdict": "PASS_NEGATIVE_CONTROL" if not errors else "INCONCLUSIVE",
        "expected_pr87_srcversion": expected_srcversion,
        "loaded_srcversion": actual_source,
        "module_parameters": observed,
        "standard_hid_ready": ready,
        "standard_seq_state": seq_state,
        "standard_hid_descriptor_responses": {
            "device_desc": stats.get("device_desc"),
            "rpt_desc": stats.get("rpt_desc"),
        },
        "observed_passive_capimg_frames": stats.get("raw_observed"),
        "bridge_input_instances": bridge_entries,
        "report_0x0c_dispatch_policy": "NOT_PROVEN_BY_THIS_FIELD_CHECK; compiled production-handler test required",
        "limitations": "Does not require actual touch input or infer CapImg publishing from raw_observed or silence.",
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sysfs-root", type=Path, default=Path("/sys"))
    parser.add_argument("--expected-srcversion", required=True)
    args = parser.parse_args(argv)
    verdict = examine(args.sysfs_root, args.expected_srcversion)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["verdict"] == "PASS_NEGATIVE_CONTROL" else 1


if __name__ == "__main__":
    sys.exit(main())
