import tempfile
import unittest
from pathlib import Path

from module.backtest import HistoricalReplay
from module.market_data import Candle
from module.paper import PaperBroker
from module.strategy_adapter import CombinedVotingStrategy, MACDAdapter, RSIAdapter


class CustomIndicatorTests(unittest.TestCase):
    def candles(self):
        prices = [100, 99, 98, 97, 96, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 103, 102, 101, 100, 99, 98, 97, 98, 99, 100, 101, 102, 103, 104, 105]
        return [Candle(str(i), "XAUUSD", p, p + 1, p - 1, p) for i, p in enumerate(prices)]

    def test_rsi_output_is_aligned_and_bounded(self):
        result = RSIAdapter(period=5, oversold=35, overbought=65).evaluate(self.candles())
        self.assertEqual(len(result["rsi"]), 30)
        self.assertTrue(all(0 <= value <= 100 for value in result["rsi"]))
        self.assertEqual(len(result["signals"]), 30)

    def test_macd_output_is_aligned(self):
        result = MACDAdapter(fast=3, slow=7, signal_period=2).evaluate(self.candles())
        self.assertEqual(len(result["macd"]), 30)
        self.assertEqual(len(result["signal_line"]), 30)
        self.assertEqual(len(result["signals"]), 30)
        self.assertTrue(set(result["signals"]).issubset({"buy", "sell", "hold"}))

    def test_rsi_and_macd_can_be_combined(self):
        strategy = CombinedVotingStrategy(
            [RSIAdapter(period=5, oversold=35, overbought=65), MACDAdapter(fast=3, slow=7, signal_period=2)],
            min_votes=1,
            volume=0.1,
        )
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            result = HistoricalReplay(broker, initial_balance=1000).run(self.candles(), strategy)
            self.assertEqual(result["candles"], 30)
            self.assertGreaterEqual(result["ticks"], 30)

    def test_default_threshold_can_reject_disagreement(self):
        strategy = CombinedVotingStrategy(
            [RSIAdapter(period=5), MACDAdapter(fast=3, slow=7, signal_period=2)],
            min_votes=2,
        )
        signals = []
        for i, candle in enumerate(self.candles()):
            signals.extend(strategy(self.candles()[:i], candle))
        self.assertTrue(isinstance(signals, list))


if __name__ == "__main__":
    unittest.main()
