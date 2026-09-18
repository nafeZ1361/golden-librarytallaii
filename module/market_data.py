"""Deterministic historical candle and tick loading for Paper Trading."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class Tick:
    timestamp: str
    symbol: str
    bid: float
    ask: float | None = None

    @property
    def price(self) -> float:
        return (self.bid + self.ask) / 2 if self.ask is not None else self.bid


@dataclass(frozen=True)
class Candle:
    timestamp: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _number(row: dict[str, str], name: str, default: float = 0.0) -> float:
    value = row.get(name, row.get(name.lower(), ""))
    return default if value in (None, "") else float(value)


def load_candles_csv(path: str | Path, symbol: str = "XAUUSD") -> list[Candle]:
    """Load OHLCV CSV and reject invalid/non-monotonic rows."""
    rows: list[Candle] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close"}
        fields = {str(f).lower() for f in (reader.fieldnames or [])}
        if not required.issubset(fields):
            raise ValueError(f"CSV must contain {sorted(required)}")
        for row in reader:
            timestamp = row.get("timestamp") or row.get("Timestamp") or ""
            o, h, low, c = (_number(row, key) for key in ("open", "high", "low", "close"))
            if not timestamp or low > min(o, h, c) or h < max(o, h, c) or low > h:
                raise ValueError(f"invalid OHLC row: {row}")
            rows.append(Candle(timestamp, symbol, o, h, low, c, _number(row, "volume")))
    rows.sort(key=lambda candle: candle.timestamp)
    if any(a.timestamp == b.timestamp for a, b in zip(rows, rows[1:])):
        raise ValueError("duplicate candle timestamp")
    return rows


def candle_to_ticks(candle: Candle) -> tuple[Tick, ...]:
    """Create a deterministic OHLC path; no random prices are introduced."""
    if candle.close >= candle.open:
        prices = (candle.open, candle.high, candle.low, candle.close)
    else:
        prices = (candle.open, candle.low, candle.high, candle.close)
    return tuple(Tick(f"{candle.timestamp}#{i}", candle.symbol, price) for i, price in enumerate(prices))


def candles_to_ticks(candles: Iterable[Candle]) -> Iterator[Tick]:
    for candle in sorted(candles, key=lambda item: item.timestamp):
        yield from candle_to_ticks(candle)


def load_ticks_csv(path: str | Path, symbol: str = "XAUUSD") -> list[Tick]:
    """Load timestamp,bid[,ask] ticks in chronological order."""
    ticks: list[Tick] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = row.get("timestamp") or row.get("Timestamp") or ""
            bid = _number(row, "bid", _number(row, "price"))
            ask = row.get("ask") or row.get("Ask")
            ticks.append(Tick(timestamp, symbol, bid, float(ask) if ask else None))
    ticks.sort(key=lambda tick: tick.timestamp)
    if any(a.timestamp == b.timestamp for a, b in zip(ticks, ticks[1:])):
        raise ValueError("duplicate tick timestamp")
    return ticks


def _mt5_timestamp(date_value: str, time_value: str) -> str:
    date_part = date_value.strip().replace(".", "-")
    time_part = time_value.strip()
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in time_part else "%Y-%m-%d %H:%M:%S"
    parsed = datetime.strptime(f"{date_part} {time_part}", fmt)
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def load_mt5_candles_csv(
    path: str | Path,
    symbol: str = "XAUUSD",
    *,
    limit: int | None = None,
) -> list[Candle]:
    """Load MetaTrader 5 tab-separated OHLC exports.

    MT5 exports use ``<DATE>``/``<TIME>`` and angle-bracketed field names.
    Rows are read incrementally, so the caller can cap the retained history.
    """
    rows: list[Candle] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = {str(field).strip().lower() for field in (reader.fieldnames or [])}
        required = {"<date>", "<time>", "<open>", "<high>", "<low>", "<close>"}
        if not required.issubset(fields):
            raise ValueError(f"MT5 candle CSV must contain {sorted(required)}")
        for row in reader:
            normalized = {str(key).strip().lower(): value for key, value in row.items()}
            timestamp = _mt5_timestamp(normalized["<date>"], normalized["<time>"])
            o = float(normalized["<open>"])
            high = float(normalized["<high>"])
            low = float(normalized["<low>"])
            close = float(normalized["<close>"])
            if low > min(o, high, close) or high < max(o, low, close):
                raise ValueError(f"invalid MT5 OHLC row: {row}")
            volume = float(normalized.get("<tickvol>", normalized.get("<vol>", 0)) or 0)
            rows.append(Candle(timestamp, symbol, o, high, low, close, volume))
            if limit is not None and len(rows) >= limit:
                break
    rows.sort(key=lambda candle: candle.timestamp)
    return rows


def iter_mt5_ticks_csv(path: str | Path, symbol: str = "XAUUSD") -> Iterator[Tick]:
    """Stream MT5 tick exports without loading multi-gigabyte files."""
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = {str(field).strip().lower() for field in (reader.fieldnames or [])}
        required = {"<date>", "<time>", "<bid>", "<ask>"}
        if not required.issubset(fields):
            raise ValueError(f"MT5 tick CSV must contain {sorted(required)}")
        for row in reader:
            normalized = {str(key).strip().lower(): value for key, value in row.items()}
            bid = normalized["<bid>"]
            ask = normalized["<ask>"]
            if not bid or not ask:
                continue
            yield Tick(
                _mt5_timestamp(normalized["<date>"], normalized["<time>"]),
                symbol,
                float(bid),
                float(ask),
            )


def aggregate_ticks_to_candles(
    ticks: Iterable[Tick],
    symbol: str = "XAUUSD",
) -> list[Candle]:
    """Aggregate a tick stream into deterministic one-minute candles."""
    buckets: dict[str, list[float]] = {}
    for tick in ticks:
        minute = tick.timestamp[:16]
        buckets.setdefault(minute, []).append(tick.price)
    candles: list[Candle] = []
    for minute in sorted(buckets):
        prices = buckets[minute]
        candles.append(Candle(
            f"{minute}:00+00:00",
            symbol,
            prices[0],
            max(prices),
            min(prices),
            prices[-1],
            float(len(prices)),
        ))
    return candles
