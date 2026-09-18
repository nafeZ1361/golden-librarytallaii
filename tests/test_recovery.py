import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from module.recovery import TradeRecovery
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class FakeBroker:
    def __init__(self, orders=(), positions=()):
        self.orders = list(orders)
        self.positions = list(positions)

    def orders_get(self, symbol=None):
        return self.orders

    def positions_get(self, symbol=None):
        return self.positions


class RecoveryTests(unittest.TestCase):
    def make_machine(self, state, age=0):
        machine = TradeStateMachine()
        old = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        machine.create(TradeRecord("t1", state=state, symbol="XAUUSD", strategy="strat", updated_at=old))
        return machine

    def item(self, ticket=10, comment="strat"):
        return SimpleNamespace(ticket=ticket, symbol="XAUUSD", magic=26080901, comment=comment)

    def test_sent_with_order_recovers_to_accepted(self):
        machine = self.make_machine(TradeState.SENT)
        report = TradeRecovery(FakeBroker(orders=[self.item()])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.ACCEPTED)
        self.assertEqual(report.recovered, 1)

    def test_sent_timeout_is_rejected_without_resend(self):
        machine = self.make_machine(TradeState.SENT, age=300)
        report = TradeRecovery(FakeBroker(), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)

    def test_accepted_with_position_recovers_to_open(self):
        machine = self.make_machine(TradeState.ACCEPTED)
        report = TradeRecovery(FakeBroker(positions=[self.item(ticket=11)])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.OPEN)
        self.assertEqual(machine.get("t1").ticket, 11)
        self.assertEqual(report.opened, 1)

    def test_wrong_magic_is_ignored(self):
        machine = self.make_machine(TradeState.ACCEPTED, age=300)
        foreign = SimpleNamespace(ticket=99, symbol="XAUUSD", magic=999, comment="strat")
        TradeRecovery(FakeBroker(positions=[foreign]), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)

    def test_persistence_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            machine = TradeStateMachine(path)
            machine.create(TradeRecord("t1", state=TradeState.ACCEPTED, symbol="XAUUSD", strategy="strat"))
            restored = TradeStateMachine(path)
            TradeRecovery(FakeBroker(positions=[self.item()])).recover(restored)
            self.assertEqual(restored.get("t1").state, TradeState.OPEN)


if __name__ == "__main__":
    unittest.main()
