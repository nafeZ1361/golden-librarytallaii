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

    def swing_candles(self):
        # Deterministic oscillating fixture: unlike a pure linear ramp, this
        # produces at least one profitable test-split experiment so that the
        # passed gate and best() selection can be exercised.
        import math

        rows = []
        price = 100.0
        for i in range(120):
            open_ = price
            close = 100 + 8 * math.sin(i / 6.0)
            high = max(open_, close) + 0.5
            low = min(open_, close) - 0.5
            rows.append(
                Candle(
                    f"2024-01-{i:03d}",
                    "XAUUSD",
                    round(open_, 2),
                    round(high, 2),
                    round(low, 2),
                    round(close, 2),
                )
            )
            price = close
        return rows

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
            # Grid values verified empirically against the swing fixture:
            # every combination passes the gate (test trades >= 1,
            # drawdown <= 20%, net profit > 0), so best() must be non-None.
            grid = {
                "name": ["a", "b"],
                "min_votes": [2],
                "supertrend_atr_period": [5],
                "supertrend_multiplier": [2.0, 3.0],
                "halftrend_amplitude": [2, 3],
                "rsi_period": [9],
            }
            results = manager.grid(self.swing_candles(), grid)
            self.assertEqual(len(results), 8)
            self.assertTrue(all(result.passed for result in results))
            best = manager.best(results)
            self.assertIsNotNone(best)
            self.assertTrue(best.passed)

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
            # 5 x 3 x 3 = 45 unique combinations; below MAX_TRIALS (50) the
            # grid runs every combination exactly once without padding.
            self.assertEqual(len(r1), 45)
            self.assertEqual(len(r2), 45)
            ids1 = [r.experiment_id for r in r1]
            ids2 = [r.experiment_id for r in r2]
            self.assertEqual(ids1, ids2, "H3 selection must be deterministic")


if __name__ == "__main__":
    unittest.main()