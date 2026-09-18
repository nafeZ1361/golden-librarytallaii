"""Deterministic trade lifecycle state machine with atomic JSON persistence."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .memory import SecondBrain

logger = logging.getLogger("golden_library.state_machine")


class TradeState(str, Enum):
    SIGNAL = "SIGNAL"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    OPEN = "OPEN"
    MANAGED = "MANAGED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


_ALLOWED: dict[TradeState, set[TradeState]] = {
    TradeState.SIGNAL: {TradeState.VALIDATED, TradeState.REJECTED},
    TradeState.VALIDATED: {TradeState.APPROVED, TradeState.REJECTED},
    TradeState.APPROVED: {TradeState.SENT, TradeState.REJECTED},
    TradeState.SENT: {TradeState.ACCEPTED, TradeState.REJECTED},
    TradeState.ACCEPTED: {TradeState.OPEN, TradeState.REJECTED},
    TradeState.OPEN: {TradeState.MANAGED, TradeState.CLOSED},
    TradeState.MANAGED: {TradeState.MANAGED, TradeState.CLOSED},
    TradeState.CLOSED: set(),
    TradeState.REJECTED: set(),
}


@dataclass
class TradeRecord:
    trade_id: str
    state: TradeState = TradeState.SIGNAL
    symbol: str = ""
    strategy: str = ""
    candle_time: str = ""
    ticket: int = 0
    reason: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = self.created_at


class TradeStateMachine:
    def __init__(self, path: str | Path | None = None, memory: SecondBrain | None = None) -> None:
        self.path = Path(path) if path else None
        self.memory = memory
        self.records: dict[str, TradeRecord] = {}
        if self.path and self.path.exists():
            self.load()

    def create(self, record: TradeRecord) -> TradeRecord:
        if record.trade_id in self.records:
            raise ValueError(f"duplicate trade_id: {record.trade_id}")
        self.records[record.trade_id] = record
        self.save()
        if self.memory:
            self.memory.record("trade_created", "Trade record created", trade_id=record.trade_id, state=record.state.value, symbol=record.symbol)
        return record

    def transition(self, trade_id: str, new_state: TradeState, *, reason: str = "", ticket: int | None = None) -> TradeRecord:
        if trade_id not in self.records:
            raise KeyError(trade_id)
        record = self.records[trade_id]
        if new_state not in _ALLOWED[record.state]:
            raise ValueError(f"invalid transition {record.state.value} -> {new_state.value}")
        previous_state = record.state
        record.state = new_state
        if reason:
            record.reason = reason
        if ticket is not None:
            record.ticket = int(ticket)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.save()
        logger.info(
            "trade state transition",
            extra={"event": "state_transition", "trade_id": trade_id, "state_from": previous_state.value, "state_to": new_state.value},
        )
        if self.memory:
            self.memory.record("state_transition", "Trade state changed", trade_id=trade_id, state_from=previous_state.value, state_to=new_state.value, reason=reason)
        return record

    def get(self, trade_id: str) -> TradeRecord | None:
        return self.records.get(trade_id)

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: {**asdict(v), "state": v.state.value} for k, v in self.records.items()}
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def load(self) -> None:
        data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        self.records = {
            key: TradeRecord(**{**value, "state": TradeState(value["state"])})
            for key, value in data.items()
        }
