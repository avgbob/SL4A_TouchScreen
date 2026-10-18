#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Synthetic V3 physical-state bundle integration, no Surface hardware needed."""
import csv
import hashlib
import json
import tempfile
import unittest
import zipfile
from datetime import datetime,timedelta,timezone
from pathlib import Path

from test_build_pinch_evidence_bundle import OfflineBundle
from build_pinch_evidence_bundle import collect

BASE=datetime(2026,10,17,22,31,13,tzinfo=timezone.utc)

def utc(offset):
    return (BASE+timedelta(seconds=offset)).isoformat()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

class PhysicalTruthBundleTest(unittest.TestCase):
    def test_v3_labels_and_lift_control_included_in_zip(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            OfflineBundle().prep(folder,True)
            e=folder/"pointer/events.csv"
            header=["Utc","Stage","Event","PointerId","MessageActive","FrameContacts",
                    "ActiveIds","OperatorPhysical"]
            with e.open("w",encoding="utf-8",newline="") as f:
                w=csv.writer(f);w.writerow(header)
                w.writerows([
                    [utc(0),3,"DOWN",11,1,1,"11",-1],
                    [utc(.2),3,"OPERATOR_BOTH_DOWN",0,1,1,"11",2],
                    [utc(1.5),4,"OPERATOR_SECOND_INTENTIONALLY_LIFTED",0,1,1,"11",1],
                    [utc(2.5),5,"UP",11,0,0,"",-1],
                    [utc(2.6),7,"OPERATOR_BOTH_LIFTED",0,0,0,"",0],
                ])
            s=folder/"pointer/samples.csv"
            with s.open("w",encoding="utf-8",newline="") as f:
                w=csv.writer(f);w.writerow(["Utc","Stage","MessageActive"])
                for i in range(40):
                    t=i*.1
                    w.writerow([utc(t),4,1 if t<2.5 else 0])
            m=folder/"manifest.json"
            meta=json.loads(m.read_text())
            for item in meta["files"]:
                file=folder/item["file"].replace("\\","/")
                item["sha256"]=digest(file)
                item["bytes"]=file.stat().st_size
            m.write_text(json.dumps(meta),encoding="utf-8")
            result=collect(folder)
            self.assertEqual(result["decoded_0c_frames"],1)
            self.assertGreater(result["v3_physical_truth_intervals"],0)
            self.assertGreater(result["v3_truth_summary"]["two_physical_one_windows_samples"],0)
            with zipfile.ZipFile(result["bundle"]) as z:
                self.assertIn("offline-analysis/physical-truth-report.json",z.namelist())
                self.assertIn("pointer/events.csv",z.namelist())
                self.assertNotIn("pinch-runtime.csv",z.namelist())
                data=json.loads(z.read("offline-analysis/physical-truth-report.json"))
                self.assertEqual(data["operator_markers"],3)
                self.assertEqual(data["os_event_lifetimes"]["DOWN"],1)
                self.assertEqual(data["os_event_lifetimes"]["UP"],1)

if __name__=="__main__":
    unittest.main()
