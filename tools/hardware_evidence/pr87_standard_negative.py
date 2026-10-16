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
    # Exact production driver: ready_show emits "ready" / "not ready",
    # never numeric 1/0. The hardware negative-control capture exposed
    # this incorrect original verifier assumption.
    if ready is not None and ready != "ready":
        errors.append(f"standard HID discovery not ready: ready={ready!r}")
    seq_state = checked_read(spi / "seq_state", errors)
    # Exact spi-hid-core.h enum: SPI_HID_SEQ_DONE=4.
    # Descriptor counters alone do not prove the state reached DONE.
    if seq_state is not None and seq_state != "4":
        errors.append(f"standard HID sequencer not DONE: seq_state={seq_state!r}")
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



# One narrowly scoped legacy mistake is recognized for offline review.
# Never rewrite the original JSON or conflate this with 0x0c dispatch proof.
LEGACY_READY_ERROR = "standard HID discovery not ready: ready='ready'"


def recheck_saved(snapshot, expected_srcversion):
    """Re-adjudicate the exact saved sysfs observations, with no new I/O.

    The October 16 physical trial was mistakenly labelled INCONCLUSIVE
    solely because its verifier expected ready=1 instead of ready='ready'.
    Reject all other errors, missing fields and altered driver identity.
    """
    errors = []
    if not isinstance(snapshot, dict):
        return {"verdict": "INCONCLUSIVE", "errors": ["snapshot must be an object"]}
    original_errors = snapshot.get("errors")
    if original_errors not in ([], [LEGACY_READY_ERROR]):
        errors.append("saved capture has additional or unknown errors")
    original_verdict = snapshot.get("verdict")
    if original_verdict not in ("INCONCLUSIVE", "PASS_NEGATIVE_CONTROL"):
        errors.append("saved capture verdict invalid")
    # Accept only coherent original verdict/error pairs. A historical
    # INCONCLUSIVE with *no* logged error is not safely adjudicable.
    if ((original_errors == [LEGACY_READY_ERROR] and
         original_verdict != "INCONCLUSIVE") or
        (original_errors == [] and
         original_verdict != "PASS_NEGATIVE_CONTROL")):
        errors.append("saved original verdict and error list disagree")
    if snapshot.get("expected_pr87_srcversion") != expected_srcversion or (
        snapshot.get("loaded_srcversion") != expected_srcversion
    ):
        errors.append("saved PR87 module source identity differs from pin")
    parameters = snapshot.get("module_parameters")
    if not isinstance(parameters, dict):
        errors.append("saved module parameter object missing")
    else:
        for key, values in (("raw_mode", {"N", "0"}),
                            ("raw_input_beta", {"N", "0"}),
                            ("std_raw_transition", {"0"})):
            if parameters.get(key) not in values:
                errors.append("saved opt-out parameter mismatch: " + key)
    if snapshot.get("standard_hid_ready") != "ready":
        errors.append("saved standard HID ready string is not 'ready'")
    if snapshot.get("standard_seq_state") != "4":
        errors.append("saved sequencer state is not DONE=4")
    d = snapshot.get("standard_hid_descriptor_responses")
    if not isinstance(d, dict) or any(
        not isinstance(d.get(k), int) or isinstance(d.get(k), bool)
        or d[k] < 1 for k in ("device_desc", "rpt_desc")
    ):
        errors.append("saved standard HID descriptor replies missing or zero")
    if snapshot.get("bridge_input_instances") != []:
        errors.append("saved MT bridge inventory not explicitly empty")
    raw_observed = snapshot.get("observed_passive_capimg_frames")
    if (not isinstance(raw_observed, int) or isinstance(raw_observed, bool)
            or raw_observed < 0):
        errors.append("saved passive CapImg counter missing/malformed")
    if not str(snapshot.get("report_0x0c_dispatch_policy", "")).startswith(
        "NOT_PROVEN_BY_THIS_FIELD_CHECK"
    ):
        errors.append("saved 0x0c policy limitation not preserved")
    return {
        "verdict": "PASS_REVIEWED_SAVED_CAPTURE" if not errors else "INCONCLUSIVE",
        "original_verdict": original_verdict,
        "original_errors": original_errors,
        "expected_pr87_srcversion": expected_srcversion,
        "observed": {
            "standard_hid_ready": snapshot.get("standard_hid_ready"),
            "standard_seq_state": snapshot.get("standard_seq_state"),
            "module_parameters": parameters,
            "standard_hid_descriptor_responses": d,
            "bridge_input_instances": snapshot.get("bridge_input_instances"),
            "observed_passive_capimg_frames": raw_observed,
        },
        "report_0x0c_dispatch_policy": "NOT_PROVEN_BY_THIS_FIELD_CHECK",
        "original_file_unchanged": True,
        "limitations": ("Offline review only; matches saved sysfs observations "
                        "but does not measure live touch or report 0x0c dispatch."),
        "errors": errors,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sysfs-root", type=Path, default=Path("/sys"))
    parser.add_argument("--review-saved-json", type=Path,
                        help="Read-only recheck of a historical verdict; never re-run hardware")
    parser.add_argument("--expected-srcversion", required=True)
    args = parser.parse_args(argv)
    if args.review_saved_json is None:
        verdict = examine(args.sysfs_root, args.expected_srcversion)
        success = verdict["verdict"] == "PASS_NEGATIVE_CONTROL"
    else:
        try:
            snapshot = json.loads(args.review_saved_json.read_text())
            verdict = recheck_saved(snapshot, args.expected_srcversion)
        except (OSError, ValueError) as exc:
            verdict = {"verdict": "INCONCLUSIVE",
                       "errors": [f"saved JSON unreadable or invalid: {type(exc).__name__}"]}
        success = verdict["verdict"] == "PASS_REVIEWED_SAVED_CAPTURE"
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
