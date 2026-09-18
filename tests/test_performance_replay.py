import tempfile
import unittest
from pathlib import Path

from module.backtest import HistoricalReplay, ReplaySignal
from module.market_data import Candle
from module.paper import PaperBroker
from module.performance import calculate_performance, max_drawdown


class PerformanceReplayTests(unittest.TestCase):
    def test_metrics(self):
        result = calculate_performance([100, -50, 25, -25], initial_balance=1000)
        self.assertEqual(result["trades"], 4)
        self.assertAlmostEqual(result["profit_factor"], 1.6666666667)
        self.assertAlmostEqual(result["net_profit"], 50)
        self.assertGreater(result["sharpe"], 0)

    def test_drawdown(self):
        result = max_drawdown([1000, 1100, 1040, 1200, 1150])
        self.assertEqual(result["max_drawdown"], 60)
        self.assertEqual(result["peak"], 1100)
        self.assertEqual(result["trough"], 1040)

    def test_strategy_callback_runs_through_paper_replay(self):
        candles = [
            Candle("1", "XAUUSD", 100, 105, 99, 104),
            Candle("2", "XAUUSD", 104, 106, 95, 96),
        ]
        calls = []

        def strategy(history, candle):
            calls.append((len(history), candle.timestamp))
            if candle.timestamp == "1":
                return [ReplaySignal("r1", "XAUUSD", 1, 0, 100, 95, 104, "test")]
            return []

        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            result = HistoricalReplay(broker, initial_balance=1000).run(candles, strategy)
            self.assertEqual(calls, [(0, "1"), (1, "2")])
            self.assertEqual(result["closed_profits"], [5.0])
            self.assertEqual(result["metrics"]["profit_factor"], float("inf"))


if __name__ == "__main__":
    unittest.main()
