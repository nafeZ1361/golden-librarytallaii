"""Pure historical strategy adapters for Replay.

Indicators operate only on the candles supplied to `evaluate`; they never
import MT5. New indicators can be added through the IndicatorAdapter protocol
or CallableIndicator without changing HistoricalReplay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

import numpy as np
import pandas as pd

from .backtest import ReplaySignal
from .market_data import Candle


class IndicatorAdapter(Protocol):
    name: str

    def evaluate(self, candles: list[Candle]) -> dict[str, object]: ...


def _frame(candles: list[Candle]) -> pd.DataFrame:
    return pd.DataFrame([{"open": c.open, "high": c.high, "low": c.low, "close": c.close, "timestamp": c.timestamp} for c in candles])


@dataclass
class SupertrendAdapter:
    atr_period: int = 10
    multiplier: float = 3.0
    name: str = "supertrend"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        df = _frame(candles)
        if len(df) == 0:
            return {"name": self.name, "direction": [], "signals": [], "line": []}
        previous_close = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - previous_close).abs(), (df["low"] - previous_close).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / self.atr_period, adjust=False, min_periods=1).mean()
        hl2 = (df["high"] + df["low"]) / 2
        upper = (hl2 + self.multiplier * atr).to_numpy(copy=True)
        lower = (hl2 - self.multiplier * atr).to_numpy(copy=True)
        direction: list[str] = []
        line: list[float] = []
        for i in range(len(df)):
            if i and direction[-1] == "long":
                lower[i] = max(lower[i], lower[i - 1])
            if i and direction[-1] == "short":
                upper[i] = min(upper[i], upper[i - 1])
            if i == 0:
                current = "long"
            elif direction[-1] == "short" and df.close.iloc[i] > upper[i - 1]:
                current = "long"
            elif direction[-1] == "long" and df.close.iloc[i] < lower[i - 1]:
                current = "short"
            else:
                current = direction[-1]
            direction.append(current)
            line.append(float(lower[i] if current == "long" else upper[i]))
        signals = ["hold"] + ["buy" if direction[i] == "long" and direction[i - 1] == "short" else "sell" if direction[i] == "short" and direction[i - 1] == "long" else "hold" for i in range(1, len(direction))]
        return {"name": self.name, "direction": direction, "signals": signals, "line": line}


@dataclass
class HalfTrendAdapter:
    amplitude: int = 2
    name: str = "halftrend"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        df = _frame(candles)
        if len(df) == 0:
            return {"name": self.name, "direction": [], "signals": [], "line": []}
        high_roll = df.high.rolling(self.amplitude, min_periods=1).max()
        low_roll = df.low.rolling(self.amplitude, min_periods=1).min()
        high_ma = df.high.rolling(self.amplitude, min_periods=1).mean()
        low_ma = df.low.rolling(self.amplitude, min_periods=1).mean()
        direction: list[str] = []
        line: list[float] = []
        for i in range(len(df)):
            current = direction[-1] if direction else "long"
            prev_low = df.low.iloc[i - 1] if i else df.low.iloc[i]
            prev_high = df.high.iloc[i - 1] if i else df.high.iloc[i]
            if current == "short" and high_ma.iloc[i] < low_roll.iloc[i] and df.close.iloc[i] < prev_low:
                current = "long"
            elif current == "long" and low_ma.iloc[i] > high_roll.iloc[i] and df.close.iloc[i] > prev_high:
                current = "short"
            direction.append(current)
            line.append(float(low_roll.iloc[i] if current == "long" else high_roll.iloc[i]))
        signals = ["hold"] + ["buy" if direction[i] == "long" and direction[i - 1] == "short" else "sell" if direction[i] == "short" and direction[i - 1] == "long" else "hold" for i in range(1, len(direction))]
        return {"name": self.name, "direction": direction, "signals": signals, "line": line}


@dataclass
class RSIAdapter:
    """RSI reversal filter: buy out of oversold, sell out of overbought."""

    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    name: str = "rsi"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        close = _frame(candles)["close"]
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / self.period, adjust=False, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / self.period, adjust=False, min_periods=1).mean()
        rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
        rsi = rsi.fillna(50.0).to_numpy()
        signals = ["hold"]
        for i in range(1, len(rsi)):
            signals.append("buy" if rsi[i - 1] <= self.oversold < rsi[i] else "sell" if rsi[i - 1] >= self.overbought > rsi[i] else "hold")
        return {"name": self.name, "direction": ["long" if x >= 50 else "short" for x in rsi], "signals": signals, "line": rsi.tolist(), "rsi": rsi.tolist(), "supports_price_line": False}


@dataclass
class MACDAdapter:
    """MACD line/signal crossover adapter."""

    fast: int = 12
    slow: int = 26
    signal_period: int = 9
    name: str = "macd"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        close = _frame(candles)["close"]
        fast_line = close.ewm(span=self.fast, adjust=False, min_periods=1).mean()
        slow_line = close.ewm(span=self.slow, adjust=False, min_periods=1).mean()
        macd = fast_line - slow_line
        signal_line = macd.ewm(span=self.signal_period, adjust=False, min_periods=1).mean()
        signals = ["hold"]
        for i in range(1, len(macd)):
            signals.append("buy" if macd.iloc[i - 1] <= signal_line.iloc[i - 1] < macd.iloc[i] else "sell" if macd.iloc[i - 1] >= signal_line.iloc[i - 1] > macd.iloc[i] else "hold")
        direction = ["long" if value >= 0 else "short" for value in macd]
        return {"name": self.name, "direction": direction, "signals": signals, "line": macd.tolist(), "macd": macd.tolist(), "signal_line": signal_line.tolist(), "supports_price_line": False}


@dataclass
class CallableIndicator:
    name: str
    function: Callable[[list[Candle]], dict[str, object]]

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        result = dict(self.function(candles))
        result.setdefault("name", self.name)
        return result


@dataclass
class CombinedVotingStrategy:
    indicators: list[IndicatorAdapter]
    symbol: str = "XAUUSD"
    volume: float = 0.01
    rr: float = 2.0
    min_votes: int | None = None
    comment: str = "combined_replay"

    def __post_init__(self) -> None:
        if not self.indicators:
            raise ValueError("at least one indicator is required")
        if self.min_votes is None:
            self.min_votes = len(self.indicators)
        if not 1 <= self.min_votes <= len(self.indicators):
            raise ValueError("min_votes must be between 1 and indicator count")

    def __call__(self, history: list[Candle], candle: Candle) -> Iterable[ReplaySignal]:
        candles = history + [candle]
        results = [indicator.evaluate(candles) for indicator in self.indicators]
        latest = [str(result.get("signals", ["hold"])[-1]) for result in results]
        buy_votes = latest.count("buy")
        sell_votes = latest.count("sell")
        signal = "buy" if buy_votes >= self.min_votes else "sell" if sell_votes >= self.min_votes else "hold"
        if signal == "hold":
            return []
        lines = [float(result["line"][-1]) for result in results if result.get("line") and result.get("supports_price_line", True)]
        entry = float(candle.open)
        if signal == "buy":
            sl = min(lines) if lines else float(candle.low)
            tp = entry + (entry - sl) * self.rr
            order_type = 0
        else:
            sl = max(lines) if lines else float(candle.high)
            tp = entry - (sl - entry) * self.rr
            order_type = 1
        if (signal == "buy" and sl >= entry) or (signal == "sell" and sl <= entry):
            return []
        trade_id = f"{self.comment}:{self.symbol}:{candle.timestamp}:{signal}"
        return [ReplaySignal(trade_id, self.symbol, self.volume, order_type, entry, sl, tp, self.comment)]


def make_combined_strategy(*indicators: IndicatorAdapter, **kwargs: object) -> CombinedVotingStrategy:
    """Convenience factory; custom indicators can be passed alongside built-ins."""
    return CombinedVotingStrategy(list(indicators), **kwargs)
