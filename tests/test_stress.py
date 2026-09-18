import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from module.paper import PaperBroker
from module.market_data import Tick


class StressTests(unittest.TestCase):
    def test_max_drawdown_from_equity_curve(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            broker.equity_history = [
                {"timestamp": "1", "equity": 1050},
                {"timestamp": "2", "equity": 980},
                {"timestamp": "3", "equity": 1010},
            ]
            result = broker.max_drawdown()
            self.assertEqual(result["max_drawdown"], 70)
            self.assertAlmostEqual(result["max_drawdown_percent"], 6.6666666667, places=5)
            self.assertEqual(result["peak"], 1050)
            self.assertEqual(result["trough"], 980)

    def test_stress_replay_persists_through_restarts_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.json"
            broker = PaperBroker(path, initial_balance=1000)
            request = {"trade_id": "stress", "symbol": "XAUUSD", "volume": 1, "type": 0, "price": 100, "sl": 95, "tp": 110, "action": "deal"}
            first = broker.send(request)
            ticks = [Tick(str(i), "XAUUSD", price) for i, price in enumerate([101, 102, 99, 104, 98, 103])]
            report = broker.stress_replay(ticks, slippage=0.1, restart_every=2)
            duplicate = broker.send(request)
            self.assertEqual(first.order, duplicate.order)
            self.assertEqual(report["restarts"], 3)
            self.assertEqual(report["ticks"], 6)
            self.assertEqual(report["open_positions"], 1)
            self.assertGreaterEqual(report["max_drawdown"], 0)

    def test_stress_replay_closes_on_tp(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            broker.send({"trade_id": "tp", "symbol": "XAUUSD", "volume": 1, "type": 0, "price": 100, "sl": 95, "tp": 105, "action": "deal"})
            report = broker.stress_replay([Tick("1", "XAUUSD", 102), Tick("2", "XAUUSD", 105)], restart_every=1)
            self.assertEqual(report["closed"], 1)
            self.assertEqual(broker.positions["tp"].close_reason, "TP")


if __name__ == "__main__":
    unittest.main()
