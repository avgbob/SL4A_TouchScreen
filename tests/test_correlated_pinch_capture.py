#!/usr/bin/env python3
"""Offline regression for correlated Windows capture validation; synthetic only."""
import csv
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "windows_capture"))
from analyze_correlated_pinch import verify_pointer_events, verify_wpr_csv


def valid_0c():
    # Construct an actual valid 4304-byte V0 0x0C body with the documented
    # 72x48 one-run raster and root/vendor sections. No Microsoft bytes used.
    payload = bytearray(4297)
    struct.pack_into("<IHB", payload, 0, 4297, 0, 0)
    struct.pack_into("<IHB", payload, 7, 16 + 3456, 0x100, 1)
    payload[14] = 8
    struct.pack_into("<II", payload, 15, 0, 3456)
    payload[23:23+3456] = bytes([180]) * 3456
    at = 7 + 16 + 3456
    struct.pack_into("<IHB", payload, at, len(payload)-at, 0xff00, 0)
    return b"\xce\x10\x0c\x00\x00" + payload + b"\0\0"


def etl_row(event, *, hex_data="", direction="", activity="ACTIVITY", clock="123456"):
    r = [""] * 22
    r[0], r[1] = "Microsoft-Windows-SPB-ClassExtension", event
    r[14],r[16],r[20],r[21]=activity,clock,direction,hex_data
    return r


class CorrelatedCaptureTest(unittest.TestCase):
    def test_complete_raw_sensor_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            out=folder/"trace.csv"
            frame=valid_0c()
            rows=[
                etl_row("IoSpbPayloadStart"),
                etl_row("IoSpbPayloadTdStart",direction="FromDevice"),
                etl_row("IoSpbPayloadTdBuffer",hex_data="0x"+(b"\xff"*5+frame).hex()),
                etl_row("IoSpbPayloadStop")
            ]
            with out.open("w",newline="") as f: csv.writer(f).writerows(rows)
            result=verify_wpr_csv(out,folder)
            self.assertTrue(result["raw_heatmaps_verified"])
            self.assertEqual(result["decoded_complete_0c_frames"],1)
            self.assertEqual(len((folder/"capimg-frames.hex").read_text().strip()),4304*2)
            self.assertIn("not assumed to be UTC",__import__("analyze_correlated_pinch").__doc__)
    def test_missing_payload_is_not_silent_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            out=folder/"trace.csv"
            rows=[
                etl_row("IoSpbPayloadStart"),
                etl_row("IoSpbPayloadTdStart",direction="FromDevice"),
                etl_row("IoSpbPayloadTdBuffer",hex_data="0x1234"),
                etl_row("IoSpbPayloadStop"),
            ]
            with out.open("w",newline="") as f: csv.writer(f).writerows(rows)
            r=verify_wpr_csv(out,folder)
            self.assertEqual(r["decoded_complete_0c_frames"],0)
            self.assertFalse(r["raw_heatmaps_verified"])
            self.assertFalse((folder/"capimg-frames.hex").exists())
    def test_physical_marker_and_balanced_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"events.csv"
            fields=["Utc","Stage","Event","PointerId","MessageActive",
                    "FrameContacts","ActiveIds"]
            rows=[
                ["2026-10-17T19:00:00Z",2,"DOWN",11,1,1,"11"],
                ["2026-10-17T19:00:01Z",3,"DOWN",12,2,2,"11|12"],
                ["2026-10-17T19:00:02Z",3,"UP",12,1,1,"11"],
                ["2026-10-17T19:00:03Z",3,"PHYSICAL_TWO_MARK",0,1,1,"11"],
                ["2026-10-17T19:00:04Z",3,"DOWN",13,2,2,"11|13"],
                ["2026-10-17T19:00:05Z",4,"UP",13,1,1,"11"],
                ["2026-10-17T19:00:06Z",4,"UP",11,0,0,""],
            ]
            with p.open("w",newline="") as f:
                w=csv.writer(f);w.writerow(fields);w.writerows(rows)
            result=verify_pointer_events(p)
            self.assertEqual(len(result["raw_one_pointer_m_presses"]),1)
            self.assertEqual(result["unbalanced_contact_ids"],[])
            self.assertEqual(result["max_reconstructed_active"],2)
            self.assertEqual(result["active_ids_at_end"],[])


if __name__ == "__main__":
    unittest.main()
