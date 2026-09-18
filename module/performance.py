"""Trading performance metrics for deterministic backtest results."""

from __future__ import annotations

import math
import statistics
from typing import Iterable


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def max_drawdown(equity: Iterable[float]) -> dict[str, float]:
    values = list(float(x) for x in equity)
    if not values:
        return {"max_drawdown": 0.0, "max_drawdown_percent": 0.0, "peak": 0.0, "trough": 0.0}
    peak = values[0]
    peak_value = peak
    trough_value = peak
    largest = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = peak - value
        if drawdown > largest:
            largest = drawdown
            peak_value = peak
            trough_value = value
    pct = largest / peak_value * 100.0 if peak_value else 0.0
    return {"max_drawdown": largest, "max_drawdown_percent": pct, "peak": peak_value, "trough": trough_value}


def calculate_performance(profits: Iterable[float], *, initial_balance: float = 0.0, periods_per_year: int = 252) -> dict[str, float | int]:
    """Calculate risk/return metrics from closed-trade profits."""
    values = [float(x) for x in profits]
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = [float(initial_balance)]
    for value in values:
        equity.append(equity[-1] + value)
    returns = [value / initial_balance for value in values] if initial_balance else values
    mean_return = _mean(returns)
    deviation = _std(returns)
    downside = [min(0.0, value) for value in returns]
    downside_deviation = math.sqrt(sum(value * value for value in downside) / len(downside)) if downside else 0.0
    sharpe = mean_return / deviation * math.sqrt(periods_per_year) if deviation else 0.0
    sortino = mean_return / downside_deviation * math.sqrt(periods_per_year) if downside_deviation else 0.0
    drawdown = max_drawdown(equity)
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(values) * 100.0 if values else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0.0),
        "net_profit": sum(values),
        "average_trade": _mean(values),
        "expectancy": _mean(values),
        "average_win": _mean(wins),
        "average_loss": _mean(losses),
        "sharpe": sharpe,
        "sortino": sortino,
        **drawdown,
    }
