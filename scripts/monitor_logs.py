#!/usr/bin/env python3
"""Tail trading JSONL logs and send deduplicated Telegram alerts.

Credentials are read only from environment variables. The script never prints
the bot token or chat ID. It is intentionally read-only with respect to logs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Telegram:
    def __init__(self) -> None:
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = os.getenv("TELEGRAM_ALERTS_ENABLED", "NO").upper() == "YES" and bool(self.token and self.chat_id)
        self.timeout = float(os.getenv("TELEGRAM_ALERT_TIMEOUT", "10"))

    def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = urlencode({"chat_id": self.chat_id, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
        request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return 200 <= response.status < 300
        except Exception as exc:
            print(f"telegram_send_failed: {type(exc).__name__}", file=sys.stderr)
            return False


def is_alert(row: dict) -> bool:
    level = str(row.get("level", "")).upper()
    event = str(row.get("event", "")).lower()
    return level in {"ERROR", "CRITICAL"} or event in {"recovery_timeout", "recovery_error", "run_once_error", "trade_rejected"}


def format_alert(row: dict) -> str:
    return "Trading bot alert\n" + "\n".join(f"{key}: {value}" for key, value in row.items() if key not in {"exception"})


def monitor(path: Path, *, once: bool = False) -> int:
    telegram = Telegram()
    cooldown = max(0.0, float(os.getenv("TELEGRAM_ALERT_COOLDOWN_SECONDS", "300")))
    poll = max(0.1, float(os.getenv("LOG_POLL_INTERVAL_SECONDS", "1")))
    last_alert: dict[str, float] = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                if once:
                    return 0
                time.sleep(poll)
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print("ignored_non_json_log_line", file=sys.stderr)
                continue
            if not is_alert(row):
                continue
            key = f"{row.get('level')}:{row.get('event')}:{row.get('message')}"
            now = time.monotonic()
            if now - last_alert.get(key, 0.0) < cooldown:
                continue
            last_alert[key] = now
            print(format_alert(row), flush=True)
            telegram.send(format_alert(row))


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else os.getenv("LOG_FILE", "logs/trading.jsonl"))
    monitor(path)


if __name__ == "__main__":
    main()
