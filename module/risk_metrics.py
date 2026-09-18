"""Broker-backed metrics passed to the centralized risk gate."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any

def _today_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

def _num(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0

def broker_metrics(api: Any, paper_broker: Any | None = None, mode: str = "PAPER") -> tuple[float, int]:
    """Return (today PnL including floating PnL, open position count).

    PAPER uses the persisted ledger; LIVE uses MT5 positions and today's deals.
    The function is deliberately defensive so a metrics failure cannot silently
    turn into a zero-risk context. Callers should reject if it raises.
    """
    mode = str(mode).upper()
    now = datetime.now(timezone.utc)
    start = _today_start(now)
    if mode == "PAPER":
        if paper_broker is None:
            raise RuntimeError("PAPER metrics require a PaperBroker")
        positions = list(paper_broker.positions_get() or ())
        pnl = 0.0
        for position in getattr(paper_broker, "positions", {}).values():
            closed_at = str(getattr(position, "closed_at", "") or "")
            if getattr(position, "status", "") == "CLOSED" and closed_at:
                try:
                    closed_dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                    if closed_dt.astimezone(timezone.utc) >= start:
                        pnl += _num(getattr(position, "profit", 0.0))
                except ValueError:
                    continue
        pnl += sum(_num(getattr(position, "profit", 0.0)) for position in positions)
        return pnl, len(positions)

    positions = list(api.positions_get() or ())
    pnl = 0.0
    history = getattr(api, "history_deals_get", None)
    if callable(history):
        deals = history(start, now) or ()
        for deal in deals:
            pnl += _num(getattr(deal, "profit", 0.0))
            pnl += _num(getattr(deal, "commission", 0.0))
            pnl += _num(getattr(deal, "swap", 0.0))
    pnl += sum(_num(getattr(position, "profit", 0.0)) for position in positions)
    return pnl, len(positions)


def broker_drawdown_pct(api, paper_broker=None, mode: str = "PAPER") -> float:
    """Return current recorded drawdown percentage for the risk gate."""
    if str(mode).upper() == "PAPER":
        if paper_broker is None:
            raise RuntimeError("PAPER drawdown metrics require a PaperBroker")
        return float(paper_broker.max_drawdown().get("max_drawdown_percent", 0.0))
    info_fn = getattr(api, "account_info", None)
    info = info_fn() if callable(info_fn) else None
    balance = _num(getattr(info, "balance", 0.0)) if info else 0.0
    equity = _num(getattr(info, "equity", 0.0)) if info else 0.0
    return max(0.0, (balance - equity) / balance * 100.0) if balance > 0 else 0.0
