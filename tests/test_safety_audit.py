import logging
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from module.execution import ExecutionEngine
from module.observability import ErrorAlertingHandler
from module.risk import RiskLimits, RiskValidator, bounded_risk_percent

class FakeAPI:
    TRADE_RETCODE_DONE = 10009
    def initialize(self): return True
    def symbol_info_tick(self, symbol): return SimpleNamespace(time=1, ask=100.0, bid=99.9)

class SafetyAuditTests(unittest.TestCase):
    def test_alert_first_send_with_monotonic_clock(self):
        alerts=[]; handler=ErrorAlertingHandler(alerts.append, cooldown_seconds=10)
        rec=logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", (), None)
        with patch("module.observability.time.monotonic", side_effect=[0.1, 0.2, 11.0]):
            handler.emit(rec); handler.emit(rec); handler.emit(rec)
        self.assertEqual(len(alerts), 2)

    def test_legacy_risk_correction_is_hard_capped(self):
        self.assertEqual(bounded_risk_percent(100.0, max_risk=100.0), 2.0)

    def test_drawdown_gate_rejects(self):
        decision=RiskValidator(RiskLimits(max_volume=1, max_drawdown_pct=10)).validate({"symbol":"XAUUSD","volume":.1}, drawdown_pct=10)
        self.assertFalse(decision.approved)
        self.assertIn("max drawdown limit reached", decision.reasons)

    def test_emergency_stop_closes_paper_positions_and_locks(self):
        from module.paper import PaperBroker
        with tempfile.TemporaryDirectory() as d:
            broker=PaperBroker(os.path.join(d,"paper.json"))
            broker.send({"action":"deal","symbol":"XAUUSD","volume":.1,"type":"buy","price":100.0,"sl":95,"tp":110,"comment":"t","trade_id":"emergency-1"})
            with patch.dict(os.environ, {"TRADING_MODE": "PAPER", "ENABLE_LIVE_TRADING": "NO"}):
                engine=ExecutionEngine(FakeAPI(), mode="PAPER", paper_broker=broker)
                result=engine.emergency_stop()
                self.assertEqual(result["closed"], 1); self.assertTrue(engine.emergency_locked)
                with self.assertRaises(RuntimeError): engine.send({"action":"deal","symbol":"XAUUSD","volume":.1})
            engine.reset_emergency_stop(); self.assertFalse(engine.emergency_locked)

    def test_emergency_stop_paper_with_broker_safety(self):
        from module.paper import PaperBroker
        with tempfile.TemporaryDirectory() as d:
            broker=PaperBroker(os.path.join(d,"paper.json"))
            broker.send({"action":"deal","symbol":"XAUUSD","volume":.1,"type":"buy","price":100.0,"sl":95,"tp":110,"comment":"t","trade_id":"t1"})
            with patch.dict(os.environ, {"TRADING_MODE": "PAPER", "ENABLE_LIVE_TRADING": "YES"}):
                engine=ExecutionEngine(FakeAPI(), mode="PAPER", paper_broker=broker)
                result=engine.emergency_stop()
                self.assertEqual(result["closed"], 1)
                self.assertTrue(engine.emergency_locked)
                engine.reset_emergency_stop()
        with tempfile.TemporaryDirectory() as d:
            from module.paper import PaperBroker
            broker=PaperBroker(os.path.join(d,"paper.json"))
            with patch.dict(os.environ, {"TRADING_MODE": "PAPER", "ENABLE_LIVE_TRADING": "YES"}):
                engine=ExecutionEngine(FakeAPI(), mode="PAPER", paper_broker=broker)
                result=engine.emergency_stop()
                self.assertEqual(result["closed"], 0); self.assertEqual(result["cancelled"], 0)
                self.assertTrue(engine.emergency_locked)

    def test_emergency_stop_paper_no_broker_live_enabled(self):
        with patch.dict(os.environ, {"TRADING_MODE": "PAPER", "ENABLE_LIVE_TRADING": "YES"}):
            engine=ExecutionEngine(FakeAPI(), mode="PAPER", paper_broker=None)
            result=engine.emergency_stop()
            self.assertEqual(result["closed"], 0); self.assertEqual(result["cancelled"], 0)
            self.assertTrue(engine.emergency_locked)

    def test_emergency_stop_backtest_live_enabled(self):
        with patch.dict(os.environ, {"TRADING_MODE": "BACKTEST", "ENABLE_LIVE_TRADING": "YES"}):
            engine=ExecutionEngine(FakeAPI(), mode="BACKTEST", paper_broker=None)
            result=engine.emergency_stop()
            self.assertEqual(result["closed"], 0); self.assertEqual(result["cancelled"], 0)
            self.assertTrue(engine.emergency_locked)

    def test_emergency_stop_live_disabled(self):
        with patch.dict(os.environ, {"TRADING_MODE": "LIVE", "ENABLE_LIVE_TRADING": "NO"}):
            engine=ExecutionEngine(FakeAPI())
            result=engine.emergency_stop()
            self.assertEqual(result["closed"], 0); self.assertEqual(result["cancelled"], 0)
            self.assertTrue(engine.emergency_locked)
            self.assertFalse(engine.live_enabled)
            self.assertEqual(engine.mode.value, "LIVE")

    def test_emergency_stop_live_enabled_guard(self):
        with patch.dict(os.environ, {"TRADING_MODE": "LIVE", "ENABLE_LIVE_TRADING": "YES"}):
            engine=ExecutionEngine(FakeAPI())
            result=engine.emergency_stop()
            self.assertEqual(result["closed"], 0); self.assertEqual(result["cancelled"], 0)
            self.assertTrue(engine.emergency_locked)
            self.assertTrue(engine.live_enabled)

if __name__ == "__main__": unittest.main()
