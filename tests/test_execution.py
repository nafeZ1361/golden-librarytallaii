import os
import unittest
from types import SimpleNamespace

from module.execution import ExecutionEngine


class FakeMT5:
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.calls = []

    def order_send(self, request):
        self.calls.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="live")


class ExecutionEngineTests(unittest.TestCase):
    def test_paper_never_calls_mt5(self):
        api = FakeMT5()
        result = ExecutionEngine(api, "PAPER").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
        self.assertTrue(result.simulated)
        self.assertEqual(api.calls, [])

    def test_backtest_never_calls_mt5(self):
        api = FakeMT5()
        result = ExecutionEngine(api, "BACKTEST").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
        self.assertTrue(result.simulated)
        self.assertEqual(api.calls, [])

    def test_live_requires_explicit_flag(self):
        api = FakeMT5()
        old = os.environ.pop("ENABLE_LIVE_TRADING", None)
        try:
            with self.assertRaises(RuntimeError):
                ExecutionEngine(api, "LIVE").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
            self.assertEqual(api.calls, [])
        finally:
            if old is not None:
                os.environ["ENABLE_LIVE_TRADING"] = old

    def test_live_calls_mt5_only_when_explicitly_enabled(self):
        api = FakeMT5()
        old = os.environ.get("ENABLE_LIVE_TRADING")
        os.environ["ENABLE_LIVE_TRADING"] = "YES"
        try:
            result = ExecutionEngine(api, "LIVE").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
            self.assertFalse(result.simulated)
            self.assertEqual(len(api.calls), 1)
        finally:
            if old is None:
                os.environ.pop("ENABLE_LIVE_TRADING", None)
            else:
                os.environ["ENABLE_LIVE_TRADING"] = old


if __name__ == "__main__":
    unittest.main()
