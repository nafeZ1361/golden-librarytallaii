import json
import os
import unittest
from unittest.mock import patch

from module.telegram_alerts import TelegramAlertConfig, TelegramAlertNotifier


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"ok": True}).encode()


class TelegramAlertTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            notifier = TelegramAlertNotifier()
            self.assertFalse(notifier.enabled)
            self.assertFalse(notifier.send("test"))

    def test_requires_both_credentials_and_explicit_enable(self):
        with patch.dict(os.environ, {"TELEGRAM_ALERTS_ENABLED": "YES", "TELEGRAM_BOT_TOKEN": "token"}, clear=True):
            self.assertFalse(TelegramAlertNotifier().enabled)

    def test_enabled_notifier_uses_environment_credentials(self):
        env = {
            "TELEGRAM_ALERTS_ENABLED": "YES",
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "TELEGRAM_CHAT_ID": "12345",
        }
        with patch.dict(os.environ, env, clear=True), patch("module.telegram_alerts.urlopen", return_value=FakeResponse()) as urlopen:
            notifier = TelegramAlertNotifier(TelegramAlertConfig.from_env())
            self.assertTrue(notifier.enabled)
            self.assertTrue(notifier.send("alert"))
            request = urlopen.call_args.args[0]
            self.assertIn("secret-token", request.full_url)
            self.assertIn("12345", request.data.decode())


if __name__ == "__main__":
    unittest.main()
