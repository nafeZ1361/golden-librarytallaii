import tempfile
import unittest
from pathlib import Path

from agent.manager import ExperimentManager, ExperimentSpec
from agent.skills import SkillCatalog
from module.market_data import Candle


class ExperimentManagerTests(unittest.TestCase):
    def candles(self):
        return [
            Candle(str(i), "XAUUSD", 100 + i, 102 + i, 98 + i, 101 + i)
            for i in range(30)
        ]

    def test_run_splits_data_and_persists_result(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExperimentManager(Path(directory) / "results.jsonl")
            result = manager.run(self.candles(), ExperimentSpec())
            self.assertEqual(result.train["candles"], 21)
            self.assertEqual(result.test["candles"], 9)
            self.assertEqual(len(manager.history()), 1)
            self.assertEqual(len(result.experiment_id), 16)

    def test_grid_and_best_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExperimentManager(Path(directory) / "results.jsonl")
            results = manager.grid(self.candles(), {"name": ["a", "b"], "min_votes": [2]})
            self.assertEqual(len(results), 2)
            self.assertIsNotNone(manager.best(results))

    def test_live_settings_are_not_part_of_manager(self):
        self.assertFalse(hasattr(ExperimentManager, "send"))

    def test_skill_catalog_discovers_trading_guidance(self):
        catalog = SkillCatalog()
        skill = catalog.get("gold")
        self.assertIsNotNone(skill)
        self.assertIn("kill switch", skill.content.lower())

    def test_skill_catalog_can_rank_relevant_guidance(self):
        skills = SkillCatalog().relevant("risk drawdown paper backtest")
        self.assertTrue(skills)
        self.assertTrue(any("golden-trading-engineer" == skill.name.casefold() for skill in skills))

    def test_h3_grid_cap_exactly_50(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExperimentManager(Path(directory) / "results.jsonl")
            big_grid = {
                "supertrend_atr_period": list(range(1, 11)),  # 10
                "supertrend_multiplier": [2.0, 3.0],           # 2
                "halftrend_amplitude": [2, 3, 4, 5, 6],        # 5
                "rsi_period": [9, 14]                          # 2
            }
            results = manager.grid(self.candles(), big_grid)
            self.assertEqual(len(results), 50, "H3 cap must enforce exactly 50 combinations")

    def test_h3_grid_cap_respects_smaller(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExperimentManager(Path(directory) / "results.jsonl")
            small_grid = {
                "name": ["a", "b"],  # 2
                "min_votes": [2, 3]   # 2
            }
            results = manager.grid(self.candles(), small_grid)
            self.assertEqual(len(results), 4, "H3 cap must allow all when < 50")

    def test_h3_grid_deterministic_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            manager1 = ExperimentManager(Path(directory) / "results1.jsonl")
            manager2 = ExperimentManager(Path(directory) / "results2.jsonl")
            big_grid = {
                "supertrend_atr_period": [5, 10, 15, 20, 25],  # 5
                "supertrend_multiplier": [2.0, 3.0, 4.0],        # 3
                "halftrend_amplitude": [2, 3, 4]                 # 3
            }
            r1 = manager1.grid(self.candles(), big_grid)
            r2 = manager2.grid(self.candles(), big_grid)
            self.assertEqual(len(r1), 45)
            self.assertEqual(len(r2), 45)
            ids1 = [r.experiment_id for r in r1]
            ids2 = [r.experiment_id for r in r2]
            self.assertEqual(ids1, ids2, "H3 selection must be deterministic")


if __name__ == "__main__":
    unittest.main()