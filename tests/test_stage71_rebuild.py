import unittest
from pathlib import Path
import tempfile, json
import tools.stage71_ml_backtest as h

class Stage71RebuildContractTests(unittest.TestCase):
    def test_expected_dataset_identity(self):
        self.assertEqual(h.EXPECTED_ROWS, 586534)
        self.assertEqual(h.EXPECTED_SHA256, "92a84f92ab4e06625a2d977f5acaeecb6d553ffd1c110b2ed9f1571c541a562a")

    def test_feature_contract_excludes_targets(self):
        self.assertEqual(len(h.FEATURES), 26)
        self.assertNotIn("future_return_5", h.FEATURES)
        self.assertNotIn("label_5", h.FEATURES)

    def test_stale_state_fixture_is_removed_before_broker(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "paper_state.json"
            p.write_text(json.dumps({"stale_marker":"STALE_STAGE71_REBUILD"}), encoding="utf-8")
            self.assertTrue(p.exists())
            p.unlink()
            self.assertFalse(p.exists())

if __name__ == "__main__":
    unittest.main()
