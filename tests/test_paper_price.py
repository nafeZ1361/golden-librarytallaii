import tempfile
import unittest
from pathlib import Path

from module.paper import PaperBroker


class PaperPriceTests(unittest.TestCase):
    def request(self, trade_id, order_type, sl, tp):
        return {
            "trade_id": trade_id,
            "symbol": "XAUUSD",
            "volume": 1.0,
            "type": order_type,
            "price": 100.0,
            "sl": sl,
            "tp": tp,
            "comment": trade_id,
            "magic": 26080901,
            "action": "deal",
        }

    def test_buy_tp_closes_with_positive_pnl_and_slippage(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("buy-tp", 0, 95, 110))
            result = broker.mark_price("XAUUSD", 110, slippage=1.5)
            position = broker.positions["buy-tp"]
            self.assertEqual(result["closed"], 1)
            self.assertEqual(position.close_reason, "TP")
            self.assertEqual(position.exit_price, 108.5)
            self.assertAlmostEqual(position.profit, 8.5)

    def test_buy_sl_closes_with_negative_pnl(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("buy-sl", 0, 95, 110))
            broker.mark_price("XAUUSD", 95, slippage=0.5)
            position = broker.positions["buy-sl"]
            self.assertEqual(position.close_reason, "SL")
            self.assertAlmostEqual(position.profit, -5.5)

    def test_sell_tp_closes_with_positive_pnl(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("sell-tp", 1, 105, 90))
            broker.mark_price("XAUUSD", 90, slippage=1.0)
            position = broker.positions["sell-tp"]
            self.assertEqual(position.close_reason, "TP")
            self.assertAlmostEqual(position.exit_price, 91.0)
            self.assertAlmostEqual(position.profit, 9.0)

    def test_price_between_barriers_keeps_position_open(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("open", 0, 95, 110))
            result = broker.mark_price("XAUUSD", 105)
            self.assertEqual(result["closed"], 0)
            self.assertEqual(broker.positions["open"].status, "OPEN")
            self.assertAlmostEqual(broker.positions["open"].profit, 5.0)


if __name__ == "__main__":
    unittest.main()
