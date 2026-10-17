#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Read-only coverage audit for a paired Windows V2 pointer and WPR tracerpt CSV.

Unlike an ETL provider enablement check, this confirms complete 4304-byte V0
0x0C SPB sensor bodies by decoding the 72x48 CapImg raster, or clearly returns
raw_heatmaps_verified=false. ETW "Clock-Time" is not assumed to be UTC.
This does not infer processed Windows ID equality or blame the classifier.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decode_v0_capimg import decode_body

HEX = re.compile(r"0[xX]([0-9a-fA-F]+)")
RAW_PREFIX = bytes.fromhex("ff" * 5)
BODY_LENGTH = 4304


def _bytes(field):
    m = HEX.search(field)
    if not m or len(m.group(1)) % 2:
        return None
    try:
        return bytes.fromhex(m.group(1))
    except ValueError:
        return None


def verify_wpr_csv(path: Path, output_dir: Path, save_frames: bool = True):
    """Keep SPB transaction boundaries; count only *decoded* sensor bodies."""
    providers = Counter()
    events = Counter()
    issues = Counter()
    processed = Counter()
    active = {}
    complete = 0
    frame_infos = []
    frames_file = output_dir / "capimg-frames.hex"
    writer = frames_file.open("w", encoding="ascii") if save_frames else None
    try:
        with path.open("r", encoding="latin-1", newline="") as stream:
            for lineno, row in enumerate(csv.reader(stream), 1):
                if len(row) < 19:
                    continue
                provider = row[0].strip()
                kind = row[1].strip()
                if not provider or provider == "Event Name":
                    continue
                providers[provider] += 1
                if "TouchAndPen" in provider or any("TouchBlobCoM" in x for x in row):
                    processed[provider + ":" + kind] += 1
                if "SPB-ClassExtension" not in provider:
                    continue
                events[kind] += 1
                activity = row[14].strip()
                if kind == "IoSpbPayloadStart":
                    if activity in active:
                        issues["overlapping_activity"] += 1
                    active[activity] = {"clock": row[16].strip(), "td": [],
                                        "last": None, "bad": False}
                elif kind == "IoSpbPayloadTdStart" and activity in active:
                    t = active[activity]
                    item = {"direction": row[20].strip().strip('" ') if len(row)>20 else "",
                            "parts": []}
                    t["td"].append(item)
                    t["last"] = item
                elif kind == "IoSpbPayloadTdBuffer" and activity in active:
                    t = active[activity]
                    raw = _bytes(row[21]) if len(row)>21 else None
                    if raw is None or t["last"] is None:
                        issues["bad_payload"] += 1
                        t["bad"] = True
                    else:
                        t["last"]["parts"].append(raw)
                elif kind == "IoSpbPayloadStop" and activity in active:
                    t = active.pop(activity)
                    complete += 1
                    if t["bad"]:
                        issues["transaction_bad_payload"] += 1
                        continue
                    rx = b"".join(b"".join(x["parts"]) for x in t["td"]
                                  if x["direction"].startswith("FromDevice"))
                    body = None
                    if len(rx) == BODY_LENGTH and rx[:3] == b"\xce\x10\x0c":
                        body = rx
                    elif (len(rx) == BODY_LENGTH + 5 and rx[:5] == RAW_PREFIX
                          and rx[5:8] == b"\xce\x10\x0c"):
                        body = rx[5:]
                    if body is None:
                        continue
                    try:
                        decoded = decode_body(body)
                    except (ValueError, IndexError):
                        issues["invalid_0c_capimg"] += 1
                        continue
                    info = {
                        "index": len(frame_infos),
                        "row": lineno,
                        "clock_100ns_raw": t["clock"],
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "raster_sha256": hashlib.sha256(decoded.raster).hexdigest(),
                    }
                    frame_infos.append(info)
                    if writer is not None:
                        writer.write(body.hex() + "\n")
    finally:
        if writer is not None:
            writer.close()
    report = {
        "source_file": path.name,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "spb_transactions_finished": complete,
        "spb_event_kinds": dict(events),
        "provider_counts": dict(providers),
        "touch_processing_event_kinds": dict(processed),
        "decoded_complete_0c_frames": len(frame_infos),
        "raw_heatmaps_verified": len(frame_infos) > 0,
        "errors": dict(issues),
        "unfinished_spb_transactions": len(active),
        "frames": frame_infos,
        "time_warning": ("Clock-Time in tracerpt CSV may be raw/QPC. "
                         "Do not join against UTC pointer events without a verified clock mapping."),
        "raw_warning": ("Sensor raster is not Windows classified contact count; "
                        "candidate peaks need matching times and classifier semantics."),
    }
    if writer is not None and not frame_infos:
        frames_file.unlink(missing_ok=True)
    return report


def verify_pointer_events(path: Path):
    kinds = Counter()
    markers = []
    downs, ups = Counter(), Counter()
    max_count = 0
    active = set()
    mismatches = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            kind = row.get("Event", "")
            kinds[kind] += 1
            contact = int(row.get("PointerId", "0") or 0)
            if kind == "DOWN":
                downs[contact] += 1
                active.add(contact)
            elif kind == "UP":
                ups[contact] += 1
                active.discard(contact)
            elif kind in ("CAPTURE_CHANGED", "CANCELLED", "UNEXPECTED_LEAVE_WHILE_DOWN"):
                active.discard(contact)
            elif kind == "PHYSICAL_TWO_MARK":
                n = int(row.get("MessageActive", "-1") or -1)
                marker = {"utc":row.get("Utc",""), "active_count":n,
                          "frame_count":row.get("FrameContacts",""),
                          "active_ids":row.get("ActiveIds",""),
                          "stage":row.get("Stage","")}
                markers.append(marker)
                if n == 1:
                    mismatches.append(marker)
            max_count = max(max_count,len(active))
    return {
        "source": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "event_counts": dict(kinds), "max_reconstructed_active": max_count,
        "unbalanced_contact_ids": sorted(
            [i for i in (downs.keys() | ups.keys()) if downs[i] != ups[i]]),
        "active_ids_at_end": sorted(active),
        "raw_m_presses": markers,
        "raw_one_pointer_m_presses": mismatches,
        "annotation_warning": ("M press is user-confirmed physical contact; "
                               "review accidental keypresses before assigning valid mismatch total."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pointer-events", required=True, type=Path)
    p.add_argument("--wpr-csv", type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    result = {"pointer": verify_pointer_events(args.pointer_events)}
    if args.wpr_csv:
        result["wpr"] = verify_wpr_csv(args.wpr_csv, args.out)
        if not result["wpr"]["raw_heatmaps_verified"]:
            result["status"] = "RAW_CAPTURE_MISSING_OR_NOT_DECODED"
        else:
            result["status"] = "RAW_CAPTURE_PRESENT_TIME_ALIGNMENT_PENDING"
    else:
        result["status"] = "POINTER_ONLY_NO_RAW_WPR_CSV"
    result["next_gate"] = ("Verify a shared UTC/QPC time anchor between SPB heatmaps and "
                           "Windows OS M markers, then inspect near-contact candidate peaks; "
                           "do not infer exact processed classifier path merely from OS UP.")
    target = args.out / "coverage-report.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"report":str(target),
          "raw_frames":result.get("wpr",{}).get("decoded_complete_0c_frames"),
          "M_markers":len(result["pointer"]["raw_m_presses"])},indent=2))
    return 0 if result["status"] != "RAW_CAPTURE_MISSING_OR_NOT_DECODED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
