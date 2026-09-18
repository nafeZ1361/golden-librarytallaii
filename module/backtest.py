"""Strategy-to-paper historical replay adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .market_data import Candle, candles_to_ticks
from .paper import PaperBroker
from .performance import calculate_performance


@dataclass(frozen=True)
class ReplaySignal:
    trade_id: str
    symbol: str
    volume: float
    order_type: Any
    price: float
    sl: float
    tp: float
    comment: str = "replay"
    magic: int | None = None

    def as_request(self) -> dict[str, Any]:
        payload = {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "volume": self.volume,
            "type": self.order_type,
            "price": self.price,
            "sl": self.sl,
            "tp": self.tp,
            "comment": self.comment,
            "action": "deal",
        }
        if self.magic is not None:
            payload["magic"] = self.magic
        return payload


class HistoricalReplay:
    """Run an existing strategy through a PaperBroker without importing MT5."""

    def __init__(self, broker: PaperBroker, *, initial_balance: float = 0.0, slippage: float = 0.0) -> None:
        self.broker = broker
        self.initial_balance = initial_balance
        self.slippage = slippage

    def run(
        self,
        candles: Iterable[Candle],
        strategy: Callable[[list[Candle], Candle], Iterable[ReplaySignal]],
    ) -> dict[str, Any]:
        history: list[Candle] = []
        seen_closed: set[str] = set()
        closed_profits: list[float] = []
        processed = 0
        for candle in sorted(candles, key=lambda item: item.timestamp):
            for signal in strategy(history.copy(), candle) or ():
                self.broker.send(signal.as_request())
            for tick in candles_to_ticks([candle]):
                result = self.broker.mark_price(tick.symbol, tick.price, slippage=self.slippage, bid=getattr(tick, "bid", None), ask=getattr(tick, "ask", None))
                self.broker.equity_history.append({"timestamp": tick.timestamp, "equity": float(result["equity"])})
                processed += 1
                for trade_id, position in self.broker.positions.items():
                    if position.status == "CLOSED" and trade_id not in seen_closed:
                        seen_closed.add(trade_id)
                        closed_profits.append(float(position.profit))
            history.append(candle)
        metrics = calculate_performance(closed_profits, initial_balance=self.initial_balance)
        return {"candles": len(history), "ticks": processed, "closed_profits": closed_profits, "metrics": metrics, "ledger": self.broker.reconcile()}
