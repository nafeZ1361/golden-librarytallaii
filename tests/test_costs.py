import tempfile
import unittest
from pathlib import Path

from module.market_data import Tick
from module.paper import PaperBroker


class TradingCostTests(unittest.TestCase):
    def request(self, trade_id):
        return {"trade_id": trade_id, "symbol": "XAUUSD", "volume": 1.0, "type": 0, "price": 100.0, "sl": 95.0, "tp": 110.0, "action": "deal"}

    def test_commission_and_bid_ask_spread_reduce_net_profit(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", commission_per_lot=2.0)
            broker.send(self.request("costed"))
            broker.mark_price("XAUUSD", 110, bid=109.0, ask=111.0)
            position = broker.positions["costed"]
            self.assertEqual(position.gross_profit, 9.0)
            self.assertEqual(position.commission, 2.0)
            self.assertEqual(position.exit_spread, 2.0)
            self.assertEqual(position.spread_cost, 2.0)
            self.assertEqual(position.profit, 5.0)

    def test_tick_replay_uses_bid_ask(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", commission_per_lot=1.0)
            broker.send(self.request("tick-cost"))
            report = broker.replay_ticks([Tick("1", "XAUUSD", 109.0, 111.0)])
            self.assertEqual(report["closed"], 1)
            self.assertEqual(broker.positions["tick-cost"].profit, 6.0)


if __name__ == "__main__":
    unittest.main()
