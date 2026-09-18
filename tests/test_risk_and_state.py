import tempfile
import unittest
from pathlib import Path

from module.risk import RiskLimits, RiskValidator
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class RiskAndStateTests(unittest.TestCase):
    def test_risk_rejects_daily_loss_and_excess_volume(self):
        validator = RiskValidator(RiskLimits(max_volume=0.1, max_daily_loss=100))
        decision = validator.validate(
            {"symbol": "XAUUSD", "volume": 0.2},
            daily_profit=-100,
        )
        self.assertFalse(decision.approved)
        self.assertIn("volume exceeds max_volume", decision.reasons)
        self.assertIn("daily loss limit reached", decision.reasons)

    def test_risk_accepts_valid_order(self):
        decision = RiskValidator(RiskLimits(max_volume=1)).validate(
            {"symbol": "XAUUSD", "volume": 0.1}
        )
        self.assertTrue(decision.approved)

    def test_risk_bypass_is_rejected_for_opening_order(self):
        decision = RiskValidator(RiskLimits(max_volume=0.1)).validate(
            {"action": "deal", "symbol": "XAUUSD", "volume": 10.0, "risk_exempt": True}
        )
        self.assertFalse(decision.approved)
        self.assertIn("risk_exempt is only valid for non-opening actions", decision.reasons)

    def test_risk_bypass_is_allowed_for_position_modification(self):
        decision = RiskValidator(RiskLimits(max_volume=0.1)).validate(
            {"action": 6, "position": 42, "symbol": "XAUUSD", "volume": 10.0, "risk_exempt": True}
        )
        self.assertTrue(decision.approved)

    def test_state_machine_rejects_invalid_transition(self):
        machine = TradeStateMachine()
        machine.create(TradeRecord("t1", symbol="XAUUSD"))
        machine.transition("t1", TradeState.VALIDATED)
        with self.assertRaises(ValueError):
            machine.transition("t1", TradeState.OPEN)

    def test_state_machine_persists_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            machine = TradeStateMachine(path)
            machine.create(TradeRecord("t1", symbol="XAUUSD"))
            machine.transition("t1", TradeState.VALIDATED)
            machine.transition("t1", TradeState.APPROVED)
            restored = TradeStateMachine(path)
            self.assertEqual(restored.get("t1").state, TradeState.APPROVED)
            self.assertTrue(restored.get("t1").created_at.endswith("+00:00"))
            self.assertTrue(restored.get("t1").updated_at.endswith("+00:00"))

    def test_transition_updates_timestamp(self):
        machine = TradeStateMachine()
        record = machine.create(TradeRecord("t1"))
        created = record.created_at
        machine.transition("t1", TradeState.VALIDATED)
        self.assertEqual(machine.get("t1").created_at, created)
        self.assertGreaterEqual(machine.get("t1").updated_at, created)


if __name__ == "__main__":
    unittest.main()
