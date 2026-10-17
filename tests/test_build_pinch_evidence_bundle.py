#!/usr/bin/env python3
"""Integration test: tiny synthetic Windows WPR+pointer bundle and strict hashes."""
import csv
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"/"windows_capture"))
from build_pinch_evidence_bundle import collect
from test_correlated_pinch_capture import valid_0c, etl_row


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


class OfflineBundle(unittest.TestCase):
    def prep(self, folder, raw):
        (folder/"pointer").mkdir()
        p=folder/"pointer"/"events.csv"
        header=["Utc","Stage","Event","PointerId","MessageActive","FrameContacts","ActiveIds"]
        rows=[
            ["2026-10-17T22:31:13Z",3,"DOWN",11,1,1,"11"],
            ["2026-10-17T22:31:14Z",3,"PHYSICAL_TWO_MARK",0,1,1,"11"],
            ["2026-10-17T22:31:15Z",3,"UP",11,0,0,""],
        ]
        with p.open("w",newline="",encoding="utf-8") as f:
            w=csv.writer(f);w.writerow(header);w.writerows(rows)
        wpr=folder/"pinch-runtime.csv"
        payload=(b"\xff"*5+valid_0c()).hex() if raw else b"\0".hex()
        with wpr.open("w",newline="",encoding="latin-1") as f:
            w=csv.writer(f)
            w.writerows([
                etl_row("IoSpbPayloadStart"),
                etl_row("IoSpbPayloadTdStart",direction="FromDevice"),
                etl_row("IoSpbPayloadTdBuffer",hex_data="0x"+payload),
                etl_row("IoSpbPayloadStop"),
            ])
        (folder/"pointer"/"SUMMARY.txt").write_text("demo\n",encoding="utf-8")
        (folder/"pointer"/"samples.csv").write_text("Utc,MessageActive\n",encoding="utf-8")
        files=["pointer/events.csv","pointer/SUMMARY.txt","pointer/samples.csv","pinch-runtime.csv"]
        meta={"generated_utc":"2026-10-17T22:33:00Z","files":[
            {"file":name.replace("/","\\"),"bytes":(folder/name).stat().st_size,
             "sha256":sha(folder/name)} for name in files]}
        (folder/"manifest.json").write_text(json.dumps(meta),encoding="utf-8")
        return p

    def test_verified_raw_frames_in_zip(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);self.prep(path,True)
            result=collect(path)
            self.assertEqual(result["decoded_0c_frames"],1)
            self.assertEqual(result["physical_two_with_one_os_pointer"],1)
            self.assertEqual(result["status"],"RAW_FRAMES_VERIFIED_UNALIGNED")
            with zipfile.ZipFile(result["bundle"]) as z:
                self.assertIn("offline-analysis/capimg-frames.hex",z.namelist())
                self.assertNotIn("pinch-runtime.csv",z.namelist())
                self.assertNotIn("pinch-runtime.etl",z.namelist())
                self.assertIn("pointer/events.csv",z.namelist())
                rep=json.loads(z.read("offline-analysis/coverage-report.json"))
                self.assertTrue(rep["wpr"]["raw_heatmaps_verified"])

    def test_missing_raw_is_reported_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);self.prep(path,False)
            r=collect(path)
            self.assertEqual(r["status"],"RAW_FRAMES_NOT_RECOVERED")
            self.assertFalse(r["raw_heatmaps_verified"])
            with zipfile.ZipFile(r["bundle"]) as z:
                self.assertNotIn("offline-analysis/capimg-frames.hex",z.namelist())
                self.assertIn("offline-analysis/coverage-report.json",z.namelist())

    def test_modified_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            path=Path(t);p=self.prep(path,True)
            with p.open("a") as f:f.write("tamper\n")
            with self.assertRaisesRegex(ValueError,"differs from original manifest"):
                collect(path)


if __name__=="__main__":
    unittest.main()
