import tempfile
import unittest
from pathlib import Path

from module.backtest import HistoricalReplay
from module.market_data import Candle
from module.paper import PaperBroker
from module.strategy_adapter import CallableIndicator, CombinedVotingStrategy, HalfTrendAdapter, SupertrendAdapter


class StrategyAdapterTests(unittest.TestCase):
    def candles(self):
        return [
            Candle(str(i), "XAUUSD", 100 + i, 102 + i, 98 + i, 101 + i)
            for i in range(20)
        ]

    def test_builtin_indicators_are_pure_and_aligned(self):
        candles = self.candles()
        for adapter in (SupertrendAdapter(3, 1.5), HalfTrendAdapter(2)):
            result = adapter.evaluate(candles)
            self.assertEqual(len(result["direction"]), len(candles))
            self.assertEqual(len(result["signals"]), len(candles))
            self.assertEqual(len(result["line"]), len(candles))

    def test_combined_voting_requires_threshold(self):
        def buy(_):
            return {"signals": ["buy"], "line": [95]}

        def sell(_):
            return {"signals": ["sell"], "line": [105]}

        strategy = CombinedVotingStrategy([CallableIndicator("a", buy), CallableIndicator("b", buy)], volume=1, rr=2)
        signals = list(strategy([], Candle("1", "XAUUSD", 100, 102, 99, 101)))
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].order_type, 0)
        self.assertEqual(signals[0].sl, 95)
        self.assertEqual(signals[0].tp, 110)
        no_consensus = CombinedVotingStrategy([CallableIndicator("a", buy), CallableIndicator("b", sell)], min_votes=2)
        self.assertEqual(list(no_consensus([], Candle("1", "XAUUSD", 100, 102, 99, 101))), [])

    def test_custom_indicator_can_run_through_replay(self):
        def buy(_):
            return {"signals": ["buy"], "line": [90]}

        strategy = CombinedVotingStrategy([CallableIndicator("custom", buy)], volume=1, rr=1)
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            result = HistoricalReplay(broker, initial_balance=1000).run(self.candles()[:1], strategy)
            self.assertEqual(result["candles"], 1)
            self.assertEqual(len(broker.orders), 1)


if __name__ == "__main__":
    unittest.main()
