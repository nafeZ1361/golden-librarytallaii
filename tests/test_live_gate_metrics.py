import unittest
from types import SimpleNamespace
from module.risk import RiskLimits, RiskValidator
from module.risk_metrics import broker_metrics
from module.experiments.grid_hedge import GridHedgeConfig, pending_levels

class LiveGateMetricTests(unittest.TestCase):
    def test_numeric_mt5_type_is_understood_by_sl_tp_validation(self):
        validator = RiskValidator(RiskLimits(max_volume=1.0))
        decision = validator.validate({"symbol": "XAUUSD", "volume": 0.1, "price": 100.0, "type": 0, "sl": 95.0, "tp": 110.0})
        self.assertTrue(decision.approved, decision.reasons)

    def test_grid_planning_is_pure_and_symmetric(self):
        levels = pending_levels(100.0, GridHedgeConfig(step_price=0.5, levels=2))
        self.assertEqual(levels, {"buy": [100.5, 101.0], "sell": [99.5, 99.0]})

    def test_paper_metrics_include_open_positions(self):
        class Broker:
            positions = {"x": SimpleNamespace(status="OPEN", profit=3.5)}
            def positions_get(self): return list(self.positions.values())
        profit, count = broker_metrics(None, Broker(), "PAPER")
        self.assertEqual((profit, count), (3.5, 1))

if __name__ == "__main__":
    unittest.main()
