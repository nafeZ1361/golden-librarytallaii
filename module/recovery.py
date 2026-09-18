"""Restart recovery for SENT and ACCEPTED trades.

The broker adapter is intentionally small and mockable. It must expose:
orders_get(symbol=...), positions_get(symbol=...), and optionally
history_deals_get(start, end).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from .config import MAGIC_NUMBER
from .state_machine import TradeRecord, TradeState, TradeStateMachine

logger = logging.getLogger("golden_library.recovery")


@dataclass(frozen=True)
class RecoveryReport:
    recovered: int = 0
    opened: int = 0
    rejected: int = 0
    waiting: int = 0
    errors: int = 0


def _age_seconds(record: TradeRecord, now: datetime) -> float:
    try:
        created = datetime.fromisoformat(record.updated_at or record.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0.0, (now - created).total_seconds())
    except (TypeError, ValueError):
        return 0.0


def _comment_matches(item: Any, record: TradeRecord) -> bool:
    comment = str(getattr(item, "comment", "") or "")
    return record.trade_id in comment or comment == record.strategy or comment.startswith(record.strategy + ":")


def _belongs_to_bot(item: Any, record: TradeRecord) -> bool:
    return (
        getattr(item, "magic", MAGIC_NUMBER) == MAGIC_NUMBER
        and getattr(item, "symbol", record.symbol) == record.symbol
        and _comment_matches(item, record)
    )


class TradeRecovery:
    """Recover broker-side order/position state after restart or disconnection."""

    def __init__(self, broker: Any, magic_number: int = MAGIC_NUMBER, timeout_seconds: int = 120) -> None:
        self.broker = broker
        self.magic_number = magic_number
        self.timeout_seconds = timeout_seconds

    def _orders(self, record: TradeRecord) -> list[Any]:
        return [
            item for item in (self.broker.orders_get(symbol=record.symbol) or ())
            if getattr(item, "magic", self.magic_number) == self.magic_number
            and _comment_matches(item, record)
        ]

    def _positions(self, record: TradeRecord) -> list[Any]:
        return [
            item for item in (self.broker.positions_get(symbol=record.symbol) or ())
            if getattr(item, "magic", self.magic_number) == self.magic_number
            and _comment_matches(item, record)
        ]

    def recover(self, states: TradeStateMachine, *, now: datetime | None = None) -> RecoveryReport:
        now = now or datetime.now(timezone.utc)
        report = RecoveryReport()
        for trade_id, record in list(states.records.items()):
            if record.state not in {TradeState.SENT, TradeState.ACCEPTED}:
                continue
            try:
                positions = self._positions(record)
                orders = self._orders(record)
                age = _age_seconds(record, now)

                if record.state == TradeState.SENT:
                    if positions or orders:
                        ticket = getattr((positions or orders)[0], "ticket", 0)
                        states.transition(trade_id, TradeState.ACCEPTED, ticket=ticket, reason="recovered from broker")
                        logger.info("recovered SENT trade", extra={"event": "sent_recovered", "trade_id": trade_id, "ticket": ticket})
                        report = RecoveryReport(report.recovered + 1, report.opened, report.rejected, report.waiting, report.errors)
                    elif age >= self.timeout_seconds:
                        states.transition(trade_id, TradeState.REJECTED, reason="SENT recovery timeout")
                        logger.error("SENT recovery timeout", extra={"event": "recovery_timeout", "trade_id": trade_id})
                        report = RecoveryReport(report.recovered, report.opened, report.rejected + 1, report.waiting, report.errors)
                    else:
                        report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting + 1, report.errors)

                elif record.state == TradeState.ACCEPTED:
                    if positions:
                        ticket = getattr(positions[0], "ticket", record.ticket)
                        states.transition(trade_id, TradeState.OPEN, ticket=ticket, reason="position recovered")
                        logger.info("recovered ACCEPTED trade", extra={"event": "accepted_recovered", "trade_id": trade_id, "ticket": ticket})
                        report = RecoveryReport(report.recovered, report.opened + 1, report.rejected, report.waiting, report.errors)
                    elif orders:
                        report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting + 1, report.errors)
                    elif age >= self.timeout_seconds:
                        states.transition(trade_id, TradeState.REJECTED, reason="ACCEPTED recovery timeout")
                        logger.error("ACCEPTED recovery timeout", extra={"event": "recovery_timeout", "trade_id": trade_id})
                        report = RecoveryReport(report.recovered, report.opened, report.rejected + 1, report.waiting, report.errors)
                    else:
                        report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting + 1, report.errors)
            except (AttributeError, OSError, TypeError, ValueError):
                logger.exception("trade recovery failed", extra={"event": "recovery_error", "trade_id": trade_id})
                report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting, report.errors + 1)
        return report
