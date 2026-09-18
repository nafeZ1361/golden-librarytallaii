import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from module.execution import ExecutionEngine
from module.recovery import TradeRecovery
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class Broker:
    def __init__(self, orders=(), positions=()):
        self.orders = list(orders)
        self.positions = list(positions)
        self.send_calls = 0

    def orders_get(self, symbol=None):
        return [x for x in self.orders if symbol is None or getattr(x, "symbol", symbol) == symbol]

    def positions_get(self, symbol=None):
        return [x for x in self.positions if symbol is None or getattr(x, "symbol", symbol) == symbol]

    def send(self, request):
        self.send_calls += 1
        return SimpleNamespace(retcode=10009, order=1, comment="accepted", simulated=True)


class RecoveryMatrixTests(unittest.TestCase):
    def record(self, state, age=0, ticket=0):
        old = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        machine = TradeStateMachine()
        machine.create(TradeRecord("t1", state=state, symbol="XAUUSD", strategy="strat", ticket=ticket, updated_at=old))
        return machine

    def item(self, *, ticket=10, magic=26080901, comment="strat", symbol="XAUUSD"):
        return SimpleNamespace(ticket=ticket, symbol=symbol, magic=magic, comment=comment)

    def test_sent_after_restart_with_broker_order(self):
        machine = self.record(TradeState.SENT)
        report = TradeRecovery(Broker(orders=[self.item(ticket=77)])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.ACCEPTED)
        self.assertEqual(machine.get("t1").ticket, 77)
        self.assertEqual(report.recovered, 1)

    def test_accepted_without_position_waits_before_timeout(self):
        machine = self.record(TradeState.ACCEPTED, age=10)
        report = TradeRecovery(Broker(), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.ACCEPTED)
        self.assertEqual(report.waiting, 1)

    def test_position_ticket_mismatch_is_recovered_by_magic_and_comment(self):
        machine = self.record(TradeState.ACCEPTED, ticket=12)
        report = TradeRecovery(Broker(positions=[self.item(ticket=99)])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.OPEN)
        self.assertEqual(machine.get("t1").ticket, 99)
        self.assertEqual(report.opened, 1)

    def test_accepted_timeout_is_rejected(self):
        machine = self.record(TradeState.ACCEPTED, age=300)
        report = TradeRecovery(Broker(), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)

    def test_recovery_never_resends_order(self):
        broker = Broker(orders=[self.item()])
        machine = self.record(TradeState.SENT)
        TradeRecovery(broker).recover(machine)
        TradeRecovery(broker).recover(machine)
        self.assertEqual(broker.send_calls, 0)

    def test_magic_and_comment_are_both_required(self):
        machine = self.record(TradeState.ACCEPTED, age=300)
        foreign = self.item(magic=999, comment="strat")
        wrong_comment = self.item(magic=26080901, comment="other")
        report = TradeRecovery(Broker(positions=[foreign, wrong_comment]), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)

    def test_paper_does_not_call_mt5_and_live_is_explicit(self):
        class Api:
            TRADE_RETCODE_DONE = 10009
            def __init__(self): self.calls = []
            def order_send(self, request):
                self.calls.append(request)
                return SimpleNamespace(retcode=10009, order=1, comment="live")
        api = Api()
        paper = ExecutionEngine(api, "PAPER")
        result = paper.send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
        self.assertTrue(result.simulated)
        self.assertEqual(api.calls, [])
        old = os.environ.get("ENABLE_LIVE_TRADING")
        os.environ["ENABLE_LIVE_TRADING"] = "YES"
        try:
            live = ExecutionEngine(api, "LIVE")
            result = live.send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
            self.assertFalse(result.simulated)
            self.assertEqual(len(api.calls), 1)
        finally:
            if old is None: os.environ.pop("ENABLE_LIVE_TRADING", None)
            else: os.environ["ENABLE_LIVE_TRADING"] = old


if __name__ == "__main__":
    unittest.main()
