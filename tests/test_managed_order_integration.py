import os
import tempfile
import unittest
from types import SimpleNamespace

import main


class FakeAPI:
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.order_send_calls = 0

    def initialize(self):
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=123, ask=100.0, bid=99.9)

    def order_send(self, request):
        self.order_send_calls += 1
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=1, comment="unexpected")


class ManagedOrderIntegrationTests(unittest.TestCase):
    def test_daily_loss_rejects_through_managed_create_order(self):
        with tempfile.TemporaryDirectory() as directory:
            old = {key: os.environ.get(key) for key in (
                "TRADING_MODE", "RISK_MAX_DAILY_LOSS", "TRADE_STATE_PATH",
                "PAPER_STATE_PATH", "MEMORY_PATH", "LOG_DIR"
            )}
            os.environ.update({
                "TRADING_MODE": "PAPER",
                "RISK_MAX_DAILY_LOSS": "10",
                "TRADE_STATE_PATH": os.path.join(directory, "trade_state.json"),
                "PAPER_STATE_PATH": os.path.join(directory, "paper_state.json"),
                "MEMORY_PATH": os.path.join(directory, "memory.jsonl"),
                "LOG_DIR": directory,
            })
            try:
                api = FakeAPI()
                runtime = main.setup(api=api)
                runtime.paper_broker.send({
                    "action": "deal", "symbol": "XAUUSD", "volume": 0.1, "type": "buy",
                    "price": 100.0, "sl": 95.0, "tp": 110.0, "comment": "existing",
                    "trade_id": "existing-1",
                })
                existing = next(iter(runtime.paper_broker.positions.values()))
                existing.profit = -25.0
                result = main.managed_create_order(
                    "XAUUSD", 0.1, "buy", 95.0, 110.0, "integration", "1m"
                )
                self.assertIsNone(result)
                self.assertEqual(api.order_send_calls, 0)
                trade_id = next(iter(main.trade_states.records))
                self.assertEqual(main.trade_states.get(trade_id).state.value, "REJECTED")
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
