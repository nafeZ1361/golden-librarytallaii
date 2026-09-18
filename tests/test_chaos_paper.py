import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import main
from module.recovery import TradeRecovery
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class ChaosPaperTests(unittest.TestCase):
    def test_kill_restart_recovery_to_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            machine = TradeStateMachine(path)
            machine.create(TradeRecord("t1", state=TradeState.SENT, symbol="XAUUSD", strategy="strat"))
            machine.transition("t1", TradeState.ACCEPTED, ticket=1)
            restored = TradeStateMachine(path)
            broker = SimpleNamespace(
                orders_get=lambda symbol=None: [],
                positions_get=lambda symbol=None: [SimpleNamespace(ticket=99, symbol="XAUUSD", magic=26080901, comment="strat")],
            )
            TradeRecovery(broker).recover(restored)
            self.assertEqual(restored.get("t1").state, TradeState.OPEN)
            self.assertEqual(restored.get("t1").ticket, 99)

    def test_transient_provider_exception_does_not_prevent_next_cycle(self):
        calls = {"n": 0}
        def provider(_):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("temporary MT5 outage")
            return None
        fake_runtime = SimpleNamespace(signal_provider=provider, symbol="XAUUSD")
        with patch.object(main, "reconcile_all_trade_states"), patch.object(main, "runtime", fake_runtime):
            with self.assertRaises(ConnectionError):
                main.run_once(fake_runtime)
            self.assertIsNone(main.run_once(fake_runtime))
            self.assertEqual(calls["n"], 2)

    def test_duplicate_signal_does_not_create_second_state(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_api = SimpleNamespace(
                initialize=lambda: True,
                symbol_info_tick=lambda symbol: SimpleNamespace(time=1, bid=100, ask=100.1),
                TRADE_RETCODE_DONE=10009,
            )
            with patch.dict("os.environ", {"TRADING_MODE": "PAPER", "PAPER_STATE_PATH": str(Path(directory) / "paper.json"), "TRADE_STATE_PATH": str(Path(directory) / "state.json"), "MEMORY_PATH": str(Path(directory) / "memory.jsonl"), "LOG_DIR": str(Path(directory) / "logs")}, clear=False):
                rt = main.setup(api=fake_api)
                signal = SimpleNamespace(symbol="XAUUSD", volume=0.01, order_type=0, sl=95, tp=110, comment="same")
                main.managed_create_order(signal.symbol, signal.volume, signal.order_type, signal.sl, signal.tp, signal.comment, "1m")
                main.managed_create_order(signal.symbol, signal.volume, signal.order_type, signal.sl, signal.tp, signal.comment, "1m")
                self.assertEqual(len(rt.trade_states.records), 1)
                self.assertEqual(len(rt.paper_broker.orders), 1)

    def test_accepted_timeout_rejects_without_position(self):
        machine = TradeStateMachine()
        old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        machine.create(TradeRecord("t1", state=TradeState.ACCEPTED, symbol="XAUUSD", strategy="strat", updated_at=old))
        broker = SimpleNamespace(orders_get=lambda symbol=None: [], positions_get=lambda symbol=None: [])
        report = TradeRecovery(broker, timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)


if __name__ == "__main__":
    unittest.main()
