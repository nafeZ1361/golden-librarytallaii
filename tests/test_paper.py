import tempfile
import unittest
from pathlib import Path

from module.paper import PaperBroker


class PaperTradingTests(unittest.TestCase):
    def request(self, trade_id="t1"):
        return {
            "trade_id": trade_id,
            "symbol": "XAUUSD",
            "volume": 0.1,
            "type": 0,
            "price": 2000.0,
            "sl": 1990.0,
            "tp": 2020.0,
            "comment": "strategy:t1",
            "magic": 26080901,
            "action": "deal",
        }

    def test_paper_order_creates_one_virtual_position(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            result = broker.send(self.request())
            self.assertEqual(result.retcode, 10009)
            self.assertEqual(len(broker.positions_get()), 1)
            self.assertEqual(broker.reconcile()["open_positions"], 1)

    def test_duplicate_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            first = broker.send(self.request())
            second = broker.send(self.request())
            self.assertEqual(first.order, second.order)
            self.assertEqual(len(broker.orders_get()), 1)
            self.assertEqual(len(broker.positions_get()), 1)

    def test_restart_recovers_ledger_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.json"
            first = PaperBroker(path)
            result = first.send(self.request("restart-id"))
            restored = PaperBroker(path)
            duplicate = restored.send(self.request("restart-id"))
            self.assertEqual(result.order, duplicate.order)
            self.assertEqual(len(restored.positions_get()), 1)

    def test_close_persists_virtual_position(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.json"
            broker = PaperBroker(path)
            broker.send(self.request("close-id"))
            self.assertTrue(broker.close("close-id"))
            restored = PaperBroker(path)
            self.assertEqual(len(restored.positions_get()), 0)
            self.assertEqual(restored.reconcile()["closed_positions"], 1)

    def test_manual_close_records_current_price_and_profit(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("manual-pnl"))
            position = broker.positions["manual-pnl"]
            position.current_price = 2010.0
            self.assertTrue(broker.close("manual-pnl"))
            closed = broker.positions["manual-pnl"]
            self.assertEqual(closed.exit_price, 2010.0)
            self.assertEqual(closed.gross_profit, 1.0)
            self.assertEqual(closed.profit, 1.0)


if __name__ == "__main__":
    unittest.main()
