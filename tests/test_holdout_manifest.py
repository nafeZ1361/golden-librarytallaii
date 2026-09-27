import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from holdout_manifest import build_manifest, dataset_sha256

class HoldoutManifestTests(unittest.TestCase):
    def test_manifest_hash_and_chronological_tail_policy(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"x.csv"
            rows=["<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>"]
            for i in range(20):
                ts=pd.Timestamp("2026-01-01")+pd.Timedelta(minutes=i)
                rows.append(f"{ts:%Y.%m.%d} {ts:%H:%M}:00 100 101 99 100 1 0 1")
            p.write_text("\n".join(rows)+"\n",encoding="utf-8")
            m=build_manifest(p)
            self.assertEqual(m["policy"]["selection"],"chronological_tail")
            self.assertEqual(m["row_count"],20)
            self.assertEqual(m["dataset_sha256"],dataset_sha256(p))
            self.assertTrue(pd.Timestamp(m["holdout_start"])>pd.Timestamp(m["dataset_start"]))
            self.assertEqual(m["holdout_end"],m["dataset_end"])

if __name__=="__main__": unittest.main()
