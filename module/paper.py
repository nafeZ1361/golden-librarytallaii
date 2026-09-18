"""Persistent paper-trading ledger with idempotent execution."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MAGIC_NUMBER


@dataclass
class PaperOrder:
    trade_id: str
    ticket: int
    symbol: str
    volume: float
    order_type: Any
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = MAGIC_NUMBER
    status: str = "ACCEPTED"
    created_at: str = ""


@dataclass
class PaperPosition:
    trade_id: str
    ticket: int
    symbol: str
    volume: float
    order_type: Any
    price: float
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = MAGIC_NUMBER
    profit: float = 0.0
    status: str = "OPEN"
    opened_at: str = ""
    current_price: float = 0.0
    exit_price: float = 0.0
    close_reason: str = ""
    closed_at: str = ""
    gross_profit: float = 0.0
    commission: float = 0.0
    spread_cost: float = 0.0
    entry_spread: float = 0.0
    exit_spread: float = 0.0


class PaperBroker:
    """A restart-safe broker simulation; it never calls MetaTrader 5."""

    def __init__(self, path: str | Path = "paper_state.json", magic_number: int = MAGIC_NUMBER, initial_balance: float = 0.0, commission_per_lot: float = 0.0, default_spread: float = 0.0) -> None:
        self.path = Path(path)
        self.magic_number = magic_number
        self.initial_balance = float(initial_balance)
        self.commission_per_lot = float(commission_per_lot)
        self.default_spread = float(default_spread)
        self.next_ticket = 1
        self.orders: dict[str, PaperOrder] = {}
        self.positions: dict[str, PaperPosition] = {}
        self.equity_history: list[dict[str, float | str]] = []
        self.load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def send(self, request: dict[str, Any]) -> Any:
        trade_id = str(request.get("trade_id") or "")
        if not trade_id:
            raise ValueError("PAPER requests require trade_id for idempotency")
        existing = self.orders.get(trade_id)
        if existing is not None:
            return self._result(existing.ticket, "PAPER duplicate: existing execution returned")

        ticket = self.next_ticket
        self.next_ticket += 1
        order = PaperOrder(
            trade_id=trade_id,
            ticket=ticket,
            symbol=str(request["symbol"]),
            volume=float(request["volume"]),
            order_type=request.get("type", request.get("order_type", "")),
            price=float(request.get("price", 0.0) or 0.0),
            sl=float(request.get("sl", 0.0) or 0.0),
            tp=float(request.get("tp", 0.0) or 0.0),
            comment=str(request.get("comment", "")),
            magic=int(request.get("magic", self.magic_number)),
            created_at=self._now(),
        )
        self.orders[trade_id] = order
        action = str(request.get("action", "")).lower()
        if action in {"deal", "market", "0", "1"}:
            entry_spread = float(request.get("spread", self.default_spread) or 0.0)
            self.positions[trade_id] = PaperPosition(
                trade_id=trade_id,
                ticket=ticket,
                symbol=order.symbol,
                volume=order.volume,
                order_type=order.order_type,
                price=order.price,
                sl=order.sl,
                tp=order.tp,
                comment=order.comment,
                magic=order.magic,
                opened_at=order.created_at,
                current_price=order.price,
                commission=abs(order.volume) * self.commission_per_lot,
                entry_spread=entry_spread,
            )
        self.save()
        return self._result(ticket, "PAPER accepted")

    def _result(self, ticket: int, comment: str) -> Any:
        from types import SimpleNamespace
        return SimpleNamespace(retcode=10009, comment=comment, order=ticket, deal=ticket, simulated=True)

    def orders_get(self, symbol: str | None = None) -> list[PaperOrder]:
        return [o for o in self.orders.values() if symbol is None or o.symbol == symbol]

    def positions_get(self, symbol: str | None = None) -> list[PaperPosition]:
        return [p for p in self.positions.values() if p.status == "OPEN" and (symbol is None or p.symbol == symbol)]

    def close(self, trade_id: str) -> bool:
        return self._close_position(trade_id, reason="MANUAL")

    def _close_position(self, trade_id: str, *, reason: str, exit_price: float | None = None, exit_spread: float = 0.0) -> bool:
        position = self.positions.get(trade_id)
        if position is None or position.status != "OPEN":
            return False
        final_price = position.current_price if exit_price is None else float(exit_price)
        position.exit_price = final_price
        position.current_price = final_price
        position.gross_profit = self._profit(position, final_price)
        position.exit_spread = abs(float(exit_spread))
        position.spread_cost = (abs(position.entry_spread) + position.exit_spread) * position.volume
        position.profit = position.gross_profit - position.commission - position.spread_cost
        position.status = "CLOSED"
        position.close_reason = reason
        position.closed_at = self._now()
        self.save()
        return True

    @staticmethod
    def _is_buy(order_type: Any) -> bool:
        return str(order_type).lower() in {"0", "buy", "buy_limit", "buy_stop"}

    @classmethod
    def _profit(cls, position: PaperPosition, price: float) -> float:
        direction = 1.0 if cls._is_buy(position.order_type) else -1.0
        return (float(price) - position.price) * position.volume * direction

    def mark_price(self, symbol: str, price: float, *, slippage: float = 0.0, bid: float | None = None, ask: float | None = None) -> dict[str, int | float]:
        """Advance a symbol price and trigger TP/SL using deterministic slippage.

        For a BUY, slippage worsens the exit by lowering the fill price; for a
        SELL it worsens the exit by raising the fill price.
        """
        price = float(price)
        closed = 0
        for trade_id, position in list(self.positions.items()):
            if position.status != "OPEN" or position.symbol != symbol:
                continue
            position.current_price = price
            position.profit = self._profit(position, price)
            buy = self._is_buy(position.order_type)
            execution_price = float(bid if buy and bid is not None else ask if not buy and ask is not None else price)
            current_spread = abs(float(ask) - float(bid)) if ask is not None and bid is not None else self.default_spread
            reason = ""
            if buy and position.tp and price >= position.tp:
                reason = "TP"
                exit_price = execution_price - abs(float(slippage))
            elif buy and position.sl and price <= position.sl:
                reason = "SL"
                exit_price = execution_price - abs(float(slippage))
            elif not buy and position.tp and price <= position.tp:
                reason = "TP"
                exit_price = execution_price + abs(float(slippage))
            elif not buy and position.sl and price >= position.sl:
                reason = "SL"
                exit_price = execution_price + abs(float(slippage))
            else:
                continue
            if self._close_position(trade_id, reason=reason, exit_price=exit_price, exit_spread=current_spread):
                closed += 1
        self.save()
        equity = self.equity()
        return {"symbol": symbol, "price": price, "closed": closed, "open_positions": len(self.positions_get(symbol=symbol)), "equity": equity}

    def equity(self, initial_balance: float | None = None) -> float:
        balance = self.initial_balance if initial_balance is None else float(initial_balance)
        return balance + sum(float(position.profit) for position in self.positions.values()) - sum(float(position.commission + position.entry_spread * position.volume) for position in self.positions.values() if position.status == "OPEN")

    def max_drawdown(self, initial_balance: float | None = None) -> dict[str, float]:
        """Return peak-to-trough drawdown from the recorded equity curve."""
        balance = self.initial_balance if initial_balance is None else float(initial_balance)
        values = [balance] + [float(item["equity"]) for item in self.equity_history]
        peak = values[0]
        max_dd = 0.0
        peak_value = peak
        trough_value = peak
        for value in values:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
                peak_value = peak
                trough_value = value
        percentage = (max_dd / peak_value * 100.0) if peak_value else 0.0
        return {"max_drawdown": max_dd, "max_drawdown_percent": percentage, "peak": peak_value, "trough": trough_value}

    def replay_ticks(self, ticks: Any, *, slippage: float = 0.0) -> dict[str, int | float]:
        """Apply chronological Tick objects and return replay statistics."""
        processed = 0
        closed = 0
        last_timestamp = ""
        for tick in ticks:
            result = self.mark_price(tick.symbol, tick.price, slippage=slippage, bid=getattr(tick, "bid", None), ask=getattr(tick, "ask", None))
            self.equity_history.append({"timestamp": str(tick.timestamp), "equity": float(result["equity"])})
            processed += 1
            closed += int(result["closed"])
            last_timestamp = str(tick.timestamp)
        return {"ticks": processed, "closed": closed, "last_timestamp": last_timestamp, "open_positions": len(self.positions_get())}

    def stress_replay(self, ticks: Any, *, slippage: float = 0.0, restart_every: int = 0) -> dict[str, Any]:
        """Replay under periodic persistence/restart checks and report resilience metrics."""
        processed = 0
        restarts = 0
        closed = 0
        for tick in ticks:
            result = self.mark_price(tick.symbol, tick.price, slippage=slippage, bid=getattr(tick, "bid", None), ask=getattr(tick, "ask", None))
            self.equity_history.append({"timestamp": str(tick.timestamp), "equity": float(result["equity"])})
            processed += 1
            closed += int(result["closed"])
            if restart_every and processed % restart_every == 0:
                self.save()
                restored = PaperBroker(self.path, magic_number=self.magic_number)
                self.__dict__.update(restored.__dict__)
                restarts += 1
        self.save()
        return {"ticks": processed, "restarts": restarts, "closed": closed, "open_positions": len(self.positions_get()), **self.max_drawdown()}

    def replay_candles(self, candles: Any, *, slippage: float = 0.0) -> dict[str, int | float]:
        """Convert historical candles to a deterministic OHLC path and replay it."""
        from .market_data import candles_to_ticks

        return self.replay_ticks(candles_to_ticks(candles), slippage=slippage)

    def reconcile(self) -> dict[str, int]:
        return {"orders": len(self.orders), "open_positions": len(self.positions_get()), "closed_positions": sum(p.status == "CLOSED" for p in self.positions.values())}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "next_ticket": self.next_ticket,
            "initial_balance": self.initial_balance,
            "commission_per_lot": self.commission_per_lot,
            "default_spread": self.default_spread,
            "orders": {k: asdict(v) for k, v in self.orders.items()},
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "equity_history": self.equity_history,
        }
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.next_ticket = int(data.get("next_ticket", 1))
        self.initial_balance = float(data.get("initial_balance", self.initial_balance))
        self.commission_per_lot = float(data.get("commission_per_lot", self.commission_per_lot))
        self.default_spread = float(data.get("default_spread", self.default_spread))
        self.orders = {k: PaperOrder(**v) for k, v in data.get("orders", {}).items()}
        self.positions = {k: PaperPosition(**v) for k, v in data.get("positions", {}).items()}
        self.equity_history = list(data.get("equity_history", []))
