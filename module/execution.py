"""Centralized, guarded execution layer for MetaTrader 5 requests.

The default mode is PAPER. LIVE requires explicit opt-in through environment
variables and is intentionally not enabled by this project.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace
from typing import Any

from .risk import RiskLimits, RiskValidator

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class ExecutionResult:
    """Normalized result returned by the execution boundary."""

    retcode: int
    comment: str
    order: int = 0
    deal: int = 0
    simulated: bool = False


class ExecutionEngine:
    """Single boundary through which all MT5 trade requests must pass."""

    def __init__(self, mt5_api: Any, mode: str | None = None, risk_validator: RiskValidator | None = None, paper_broker: Any | None = None) -> None:
        self.mt5 = mt5_api
        self.paper_broker = paper_broker
        configured = (mode or os.getenv("TRADING_MODE", "PAPER")).upper()
        try:
            self.mode = ExecutionMode(configured)
        except ValueError as exc:
            raise ValueError(
                f"TRADING_MODE must be BACKTEST, PAPER, or LIVE; got {configured!r}"
            ) from exc

        self.live_enabled = os.getenv("ENABLE_LIVE_TRADING", "NO").upper() == "YES"
        self.risk_validator = risk_validator or RiskValidator(RiskLimits(max_volume=1.0))
        self._submitted_trade_ids: set[str] = set()
        self._emergency_locked = False

    @property
    def is_simulated(self) -> bool:
        return self.mode != ExecutionMode.LIVE

    def send(self, request: dict[str, Any], *, daily_profit: float = 0.0, open_positions: int = 0, drawdown_pct: float = 0.0) -> Any:
        """Validate the boundary and send or simulate one request.

        LIVE is blocked unless ENABLE_LIVE_TRADING=YES is explicitly set.
        BACKTEST and PAPER never call mt5.order_send().
        """
        if self._emergency_locked:
            raise RuntimeError("execution engine is emergency-locked; manual reset required")
        if not isinstance(request, dict) or not request.get("action"):
            raise ValueError("MT5 request must be a non-empty dict with an action")

        decision = self.risk_validator.validate(
            request, daily_profit=daily_profit, open_positions=open_positions, drawdown_pct=drawdown_pct
        )
        if not decision.approved:
            raise ValueError("risk validation failed: " + "; ".join(decision.reasons))

        if self.mode == ExecutionMode.LIVE:
            if not self.live_enabled:
                raise RuntimeError(
                    "LIVE mode is blocked: set ENABLE_LIVE_TRADING=YES explicitly"
                )
            trade_id = request.get("trade_id")
            if trade_id:
                if trade_id in self._submitted_trade_ids:
                    raise ValueError(f"duplicate trade_id: {trade_id}")
                self._submitted_trade_ids.add(str(trade_id))
            logger.warning("LIVE MT5 request: action=%s symbol=%s", request.get("action"), request.get("symbol"))
            result = self.mt5.order_send(request)
            if result is None:
                return None
            return ExecutionResult(
                retcode=getattr(result, "retcode", -1),
                comment=str(getattr(result, "comment", "")),
                order=int(getattr(result, "order", 0) or 0),
                deal=int(getattr(result, "deal", 0) or 0),
                simulated=False,
            )

        trade_id = request.get("trade_id")
        if trade_id:
            if trade_id in self._submitted_trade_ids:
                raise ValueError(f"duplicate trade_id: {trade_id}")
            self._submitted_trade_ids.add(str(trade_id))

        logger.info(
            "SIMULATED %s request: action=%s symbol=%s volume=%s",
            self.mode.value,
            request.get("action"),
            request.get("symbol"),
            request.get("volume"),
        )
        if self.mode == ExecutionMode.PAPER and self.paper_broker is not None:
            return self.paper_broker.send(request)
        done_code = getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)
        return SimpleNamespace(
            retcode=done_code,
            comment=f"{self.mode.value} simulation",
            order=0,
            deal=0,
            simulated=True,
        )


    @property
    def emergency_locked(self) -> bool:
        return self._emergency_locked

    def reset_emergency_stop(self) -> None:
        self._emergency_locked = False
        logger.warning("EMERGENCY STOP RESET: manual operator action")

    def emergency_stop(self) -> dict[str, int]:
        """Flatten managed exposure, cancel pending orders, then lock execution."""
        broker = self.paper_broker if self.mode == ExecutionMode.PAPER and self.paper_broker is not None else None
        if self.mode == ExecutionMode.PAPER and self.paper_broker is not None:
            closed = cancelled = 0
            for trade_id in list(getattr(broker, "positions", {}).keys()):
                closed += int(bool(broker.close(trade_id)))
            for order in getattr(broker, "orders", {}).values():
                if getattr(order, "status", "") not in {"CLOSED", "CANCELLED"}:
                    order.status = "CANCELLED"
                    cancelled += 1
            broker.save()
        elif self.mode == ExecutionMode.LIVE and self.live_enabled:
            closed = cancelled = 0
            done_code = getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)
            for position in list(getattr(self.mt5, "positions_get", lambda: ())() or ()):
                close_fn = getattr(self.mt5, "close_position", None)
                if callable(close_fn):
                    closed += int(bool(close_fn(position)))
                    continue
                tick_fn = getattr(self.mt5, "symbol_info_tick", None)
                tick = tick_fn(position.symbol) if callable(tick_fn) else None
                is_buy = int(getattr(position, "type", 0)) == int(getattr(self.mt5, "POSITION_TYPE_BUY", 0))
                request = {
                    "action": getattr(self.mt5, "TRADE_ACTION_DEAL", 1),
                    "symbol": position.symbol,
                    "volume": float(position.volume),
                    "type": getattr(self.mt5, "ORDER_TYPE_SELL", 1) if is_buy else getattr(self.mt5, "ORDER_TYPE_BUY", 0),
                    "position": int(position.ticket),
                    "price": float(getattr(tick, "bid" if is_buy else "ask", 0.0)) if tick else 0.0,
                    "deviation": 20,
                    "magic": int(getattr(position, "magic", 0) or 0),
                    "comment": "EMERGENCY_STOP",
                }
                result = self.mt5.order_send(request)
                closed += int(result is not None and getattr(result, "retcode", -1) == done_code)
            for order in list(getattr(self.mt5, "orders_get", lambda: ())() or ()):
                remove_fn = getattr(self.mt5, "cancel_order", None)
                if callable(remove_fn):
                    cancelled += int(bool(remove_fn(order)))
                    continue
                result = self.mt5.order_send({
                    "action": getattr(self.mt5, "TRADE_ACTION_REMOVE", 8),
                    "order": int(order.ticket),
                    "comment": "EMERGENCY_STOP",
                })
                cancelled += int(result is not None and getattr(result, "retcode", -1) == done_code)
        else:
            closed = cancelled = 0
        self._emergency_locked = True
        logger.critical("EMERGENCY STOP ACTIVATED: closed=%s cancelled=%s", closed, cancelled)
        return {"closed": closed, "cancelled": cancelled}

    def describe(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "simulated": self.is_simulated,
            "emergency_locked": self._emergency_locked,
            "live_enabled": self.live_enabled,
        }
