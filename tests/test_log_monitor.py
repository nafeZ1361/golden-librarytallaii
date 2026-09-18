import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.monitor_logs import Telegram, is_alert, monitor


class LogMonitorTests(unittest.TestCase):
    def test_alert_filter(self):
        self.assertTrue(is_alert({"level": "ERROR", "message": "x"}))
        self.assertTrue(is_alert({"level": "INFO", "event": "recovery_timeout"}))
        self.assertFalse(is_alert({"level": "INFO", "event": "state_transition"}))

    def test_disabled_telegram_does_not_send(self):
        with patch.dict(os.environ, {"TELEGRAM_ALERTS_ENABLED": "NO", "TELEGRAM_BOT_TOKEN": "secret", "TELEGRAM_CHAT_ID": "1"}, clear=False):
            self.assertFalse(Telegram().enabled)

    def test_once_reads_error_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trading.jsonl"
            path.write_text(json.dumps({"level": "ERROR", "event": "run_once_error", "message": "boom"}) + "\n")
            with patch.dict(os.environ, {"TELEGRAM_ALERTS_ENABLED": "NO"}, clear=False):
                self.assertEqual(monitor(path, once=True), 0)


if __name__ == "__main__":
    unittest.main()
