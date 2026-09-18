"""Secure Telegram alert notifier.

No credentials are stored in source code. Alerts are disabled unless
TELEGRAM_ALERTS_ENABLED=YES and both TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are present in the environment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TelegramAlertConfig:
    enabled: bool
    token: str | None
    chat_id: str | None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "TelegramAlertConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        enabled = os.getenv("TELEGRAM_ALERTS_ENABLED", "NO").upper() == "YES"
        return cls(
            enabled=enabled and bool(token and chat_id),
            token=token,
            chat_id=chat_id,
            timeout_seconds=float(os.getenv("TELEGRAM_ALERT_TIMEOUT", "10")),
        )


class TelegramAlertNotifier:
    def __init__(self, config: TelegramAlertConfig | None = None) -> None:
        self.config = config or TelegramAlertConfig.from_env()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def send(self, message: str) -> bool:
        """Send one alert; return False when disabled or Telegram rejects it."""
        if not self.enabled:
            return False
        if not message:
            return False
        payload = urlencode({"chat_id": self.config.chat_id, "text": message[:4096]}).encode()
        request = Request(
            f"https://api.telegram.org/bot{self.config.token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                return bool(body.get("ok"))
        except Exception:
            # The trading loop must not crash because Telegram is unavailable.
            return False

    def __call__(self, message: str) -> None:
        self.send(message)
