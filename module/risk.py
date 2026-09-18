"""Pure risk and order validation for the trading engine."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskLimits:
    max_volume: float = 1.0
    max_daily_loss: float = 0.0
    max_spread: float = 0.0
    max_open_positions: int = 0
    max_drawdown_pct: float = 0.0

    @classmethod
    def from_env(cls) -> "RiskLimits":
        """Load explicit risk caps; zero keeps a cap disabled for compatibility."""
        configured_max = float(os.getenv("RISK_MAX_VOLUME", "1.0"))
        hard_target = float(os.getenv("MAX_VOLUME_TARGET", "0"))
        return cls(
            max_volume=min(configured_max, hard_target) if hard_target > 0 else configured_max,
            max_daily_loss=float(os.getenv("RISK_MAX_DAILY_LOSS", "0.0")),
            max_spread=float(os.getenv("RISK_MAX_SPREAD", "0.0")),
            max_open_positions=int(os.getenv("RISK_MAX_OPEN_POSITIONS", "0")),
            max_drawdown_pct=float(os.getenv("RISK_MAX_DRAWDOWN_PCT", "20.0")),
        )


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...] = ()


class RiskValidator:
    """Validates a proposed order without calling MT5 or a network service."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def validate(
        self,
        request: dict[str, Any],
        *,
        daily_profit: float = 0.0,
        open_positions: int = 0,
        drawdown_pct: float = 0.0,
    ) -> RiskDecision:
        if request.get("risk_exempt") is True:
            action = str(request.get("action", "")).lower()
            is_non_opening = (
                "position" in request
                or "order" in request
                or action in {"sltp", "modify", "remove", "close"}
            )
            if is_non_opening:
                logger.warning("risk bypass allowed for non-opening action=%s", action)
                return RiskDecision(approved=True)
            logger.error("risk bypass rejected for opening action=%s", action)
            return RiskDecision(approved=False, reasons=("risk_exempt is only valid for non-opening actions",))
        reasons: list[str] = []
        if not request.get("symbol"):
            reasons.append("symbol is required")
        volume = float(request.get("volume", 0) or 0)
        if volume <= 0:
            reasons.append("volume must be positive")
        if self.limits.max_volume > 0 and volume > self.limits.max_volume:
            reasons.append("volume exceeds max_volume")
        if self.limits.max_open_positions > 0 and open_positions >= self.limits.max_open_positions:
            reasons.append("max_open_positions reached")
        if self.limits.max_daily_loss > 0 and daily_profit <= -abs(self.limits.max_daily_loss):
            reasons.append("daily loss limit reached")
        if self.limits.max_drawdown_pct > 0 and drawdown_pct >= self.limits.max_drawdown_pct:
            reasons.append("max drawdown limit reached")

        spread = request.get("spread")
        if self.limits.max_spread > 0 and spread is not None and float(spread) > self.limits.max_spread:
            reasons.append("spread exceeds max_spread")

        order_type = str(request.get("order_type", request.get("type", ""))).lower()
        price = request.get("price")
        sl = request.get("sl")
        tp = request.get("tp")
        if price is not None and sl is not None and tp is not None:
            price, sl, tp = float(price), float(sl), float(tp)
            if order_type in {"buy", "0"} and not (sl < price < tp):
                reasons.append("buy requires sl < price < tp")
            if order_type in {"sell", "1"} and not (tp < price < sl):
                reasons.append("sell requires tp < price < sl")

        return RiskDecision(approved=not reasons, reasons=tuple(reasons))


def bounded_risk_percent(base_risk: float, *, max_risk: float = 2.0) -> float:
    """Cap risk; never loss-chase through a martingale multiplier."""
    cap = min(float(max_risk), 2.0)
    return max(0.0, min(float(base_risk), cap))
