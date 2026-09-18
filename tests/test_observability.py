import json
import logging
import tempfile
import unittest
from pathlib import Path

from module.observability import ErrorAlertingHandler, configure_logging


class ObservabilityTests(unittest.TestCase):
    def test_jsonl_logging_and_error_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            alerts = []
            logger = configure_logging(directory, notifier=alerts.append, alert_cooldown_seconds=3600)
            logger.error("connection failure", extra={"event": "mt5_error", "symbol": "XAUUSD"})
            logger.error("connection failure", extra={"event": "mt5_error", "symbol": "XAUUSD"})
            for handler in logger.handlers:
                handler.flush()
            lines = (Path(directory) / "trading.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["level"], "ERROR")
            self.assertEqual(len(alerts), 1)

    def test_alert_handler_without_notifier_is_safe(self):
        handler = ErrorAlertingHandler(None)
        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "boom", (), None)
        handler.emit(record)


if __name__ == "__main__":
    unittest.main()
