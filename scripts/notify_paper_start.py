#!/usr/bin/env python3
from datetime import datetime, timezone
import os
from module.telegram_alerts import TelegramAlertNotifier

message = f"PAPER run started at {os.getenv('PAPER_RUN_STARTED_AT', datetime.now(timezone.utc).isoformat())}"
notifier = TelegramAlertNotifier()
print(message)
if notifier.enabled:
    print("telegram_start_alert_sent=" + str(notifier.send(message)))
