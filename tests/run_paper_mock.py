import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class MockMT5:
    TRADE_RETCODE_DONE = 10009
    TIMEFRAME_M1 = 1

    def __init__(self):
        self.initialize_calls = 0
        self.order_send_calls = 0
        self.copy_calls = 0

    def initialize(self):
        self.initialize_calls += 1
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=1700000000, bid=100.0, ask=100.2)

    def positions_get(self, symbol=None):
        return []

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.copy_calls += 1
        return None

    def order_send(self, request):
        self.order_send_calls += 1
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=999, deal=999, comment="mock")


class StopAfterSleeps(Exception):
    pass


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ.update({
            "TRADING_MODE": "PAPER",
            "ENABLE_LIVE_TRADING": "NO",
            "SYMBOL": "XAUUSD",
            "TIMEFRAME": "1m",
            "LOOP_INTERVAL_SECONDS": "0.01",
            "INITIAL_BALANCE": "1000",
            "COMMISSION_PER_LOT": "2",
            "DEFAULT_SPREAD": "0.2",
            "RISK_MAX_VOLUME": "1.0",
            "PAPER_STATE_PATH": str(root / "paper_state.json"),
            "TRADE_STATE_PATH": str(root / "trade_state.json"),
            "MEMORY_PATH": str(root / "memory" / "events.jsonl"),
            "LOG_DIR": str(root / "logs"),
        })
        api = MockMT5()
        main.mt5 = api
        emitted = {"count": 0}

        def provider(rt):
            if emitted["count"] == 0:
                emitted["count"] += 1
                return SimpleNamespace(symbol="XAUUSD", volume=0.01, order_type=0, sl=95.0, tp=110.0, comment="paper-mock")
            return None

        original_sleep = main.time.sleep

        def limited_sleep(seconds):
            emitted["count"] += 1
            if emitted["count"] >= 4:
                raise StopAfterSleeps
            original_sleep(0.001)

        original_provider_setup = main.setup
        def setup_with_provider(**kwargs):
            kwargs["api"] = api
            kwargs["signal_provider"] = provider
            return original_provider_setup(**kwargs)

        main.setup = setup_with_provider
        main.time.sleep = limited_sleep
        try:
            try:
                main.main()
            except StopAfterSleeps:
                pass
        finally:
            main.time.sleep = original_sleep
            main.setup = original_provider_setup

        log_path = root / "logs" / "trading.jsonl"
        state_path = root / "trade_state.json"
        paper_path = root / "paper_state.json"
        log_lines = log_path.read_text().splitlines() if log_path.exists() else []
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        paper = json.loads(paper_path.read_text()) if paper_path.exists() else {}
        print(json.dumps({
            "initialize_calls": api.initialize_calls,
            "mt5_order_send_calls": api.order_send_calls,
            "copy_rates_calls": api.copy_calls,
            "paper_log_exists": log_path.exists(),
            "log_lines": len(log_lines),
            "state_records": len(state),
            "state_values": [item["state"] for item in state.values()],
            "paper_orders": len(paper.get("orders", {})),
            "paper_positions": len(paper.get("positions", {})),
            "live_mt5_called": api.order_send_calls > 0,
        }, indent=2))
        assert api.initialize_calls == 1
        assert api.order_send_calls == 0
        assert log_path.exists()
        assert len(state) == 1
        assert len(paper.get("orders", {})) == 1
        assert len(paper.get("positions", {})) == 1


if __name__ == "__main__":
    run()
