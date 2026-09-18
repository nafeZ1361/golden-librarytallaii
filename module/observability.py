"""Logging and error alerting for the trading runtime.

Alerts are dependency-free and injected as a callable, so credentials never
belong in this module. A Telegram adapter can be supplied by the application.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("trade_id", "symbol", "ticket", "mode", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


class ErrorAlertingHandler(logging.Handler):
    """Forward ERROR+ records to an injected notifier with cooldown."""

    def __init__(self, notifier: Callable[[str], None] | None = None, cooldown_seconds: int = 300) -> None:
        super().__init__(level=logging.ERROR)
        self.notifier = notifier
        self.cooldown_seconds = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if self.notifier is None:
            return
        try:
            key = f"{record.name}:{record.getMessage()}"
            now = time.monotonic()
            last_sent = self._last_sent.get(key)
            if last_sent is not None and now - last_sent < self.cooldown_seconds:
                return
            # First occurrence must always alert; only subsequent duplicates cool down.
            self._last_sent[key] = now
            self.notifier(self.format(record))
        except Exception:
            self.handleError(record)


class CloseAfterEmitRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotate JSONL logs while releasing the file after every record.

    Releasing the handle is important on Windows, where temporary test and
    deployment directories cannot be removed while a log file is open.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if not Path(self.baseFilename).parent.exists():
            return
        try:
            super().emit(record)
        finally:
            self.close()


def configure_logging(
    log_dir: str | os.PathLike[str] = "logs",
    *,
    level: int = logging.INFO,
    notifier: Callable[[str], None] | None = None,
    alert_cooldown_seconds: int = 300,
) -> logging.Logger:
    """Configure console, rotating-file, and error-alert handlers once."""
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("golden_library")
    logger.setLevel(level)
    logger.propagate = False
    existing_files = {
        Path(getattr(handler, "baseFilename", "")).resolve()
        for handler in logger.handlers
        if getattr(handler, "baseFilename", None)
    }
    target_file = (directory / "trading.jsonl").resolve()
    if logger.handlers and existing_files == {target_file} and directory.exists():
        return logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = JsonFormatter()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = CloseAfterEmitRotatingFileHandler(
        directory / "trading.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    alert_handler = ErrorAlertingHandler(notifier, alert_cooldown_seconds)
    alert_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.addHandler(alert_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"golden_library.{name}")
