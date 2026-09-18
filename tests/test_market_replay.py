import tempfile
import unittest
from pathlib import Path

from module.market_data import candle_to_ticks, load_candles_csv, load_ticks_csv
from module.paper import PaperBroker


class MarketReplayTests(unittest.TestCase):
    def test_candle_loader_and_deterministic_bullish_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candles.csv"
            path.write_text("timestamp,open,high,low,close,volume\n2026-01-01T00:00:00Z,100,112,98,110,10\n")
            candles = load_candles_csv(path)
            self.assertEqual([t.price for t in candle_to_ticks(candles[0])], [100, 112, 98, 110])

    def test_tick_loader_sorts_and_reads_ask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticks.csv"
            path.write_text("timestamp,bid,ask\n2026-01-01T00:00:01Z,101,102\n2026-01-01T00:00:00Z,100,101\n")
            ticks = load_ticks_csv(path)
            self.assertEqual(ticks[0].bid, 100)
            self.assertEqual(ticks[0].price, 100.5)

    def test_candle_replay_hits_tp(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send({"trade_id": "replay", "symbol": "XAUUSD", "volume": 1, "type": 0, "price": 100, "sl": 95, "tp": 110, "action": "deal"})
            result = broker.replay_candles(load_candles_csv_from_text("2026-01-01T00:00:00Z,100,112,98,110"))
            self.assertEqual(result["closed"], 1)
            self.assertEqual(broker.positions["replay"].close_reason, "TP")


def load_candles_csv_from_text(row):
    import tempfile
    from pathlib import Path
    from module.market_data import load_candles_csv
    directory = tempfile.mkdtemp()
    path = Path(directory) / "c.csv"
    path.write_text("timestamp,open,high,low,close\n" + row + "\n")
    return load_candles_csv(path)


if __name__ == "__main__":
    unittest.main()
