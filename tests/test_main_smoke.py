import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from types import SimpleNamespace

from module.backtest import ReplaySignal


class FakeMT5:
    TRADE_RETCODE_DONE = 10009
    ORDER_TYPE_BUY = 0

    def __init__(self):
        self.initialized = 0
        self.orders = []

    def initialize(self):
        self.initialized += 1
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=123, bid=100.0, ask=100.2)

    def positions_get(self, symbol=None):
        return []

    def copy_rates_from_pos(self, symbol, tf, start, count):
        return None


class MainSmokeTest(unittest.TestCase):
    def test_setup_and_run_once_with_mock_mt5(self):
        fake = FakeMT5()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "TRADING_MODE": "PAPER",
            "PAPER_STATE_PATH": str(Path(directory) / "paper.json"),
            "TRADE_STATE_PATH": str(Path(directory) / "trade.json"),
            "MEMORY_PATH": str(Path(directory) / "memory.jsonl"),
            "LOG_DIR": str(Path(directory) / "logs"),
            "INITIAL_BALANCE": "1000",
            "LOOP_INTERVAL_SECONDS": "0.05",
        }, clear=False):
            import main
            def provider(rt):
                return ReplaySignal("smoke", "XAUUSD", 0.01, 0, 100.0, 95.0, 110.0, "smoke")
            rt = main.setup(api=fake, signal_provider=provider)
            result = main.run_once(rt)
            self.assertEqual(fake.initialized, 1)
            self.assertIsNotNone(result)
            self.assertEqual(result.retcode, fake.TRADE_RETCODE_DONE)
            main.reconcile_all_trade_states()


if __name__ == "__main__":
    unittest.main()
