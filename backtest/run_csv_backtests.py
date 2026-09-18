"""Run the current and legacy strategies against MT5 M1 CSV exports."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.indicators import backtest_supertrend, backtest_trend_ali
from module.backtest import HistoricalReplay, ReplaySignal
from module.market_data import (
    aggregate_ticks_to_candles,
    iter_mt5_ticks_csv,
    load_mt5_candles_csv,
)
from module.paper import PaperBroker
from module.strategy_adapter import (
    CombinedVotingStrategy,
    HalfTrendAdapter,
    MACDAdapter,
    RSIAdapter,
    SupertrendAdapter,
)


def _run(candles, strategy, label: str, initial_balance: float) -> dict:
    with tempfile.TemporaryDirectory(prefix="csv-backtest-") as directory:
        broker = PaperBroker(Path(directory) / f"{label}.json", initial_balance=initial_balance)
        result = HistoricalReplay(broker, initial_balance=initial_balance).run(candles, strategy)
        drawdown = broker.max_drawdown()["max_drawdown"]
    metrics = result["metrics"]
    return {
        "strategy": label,
        "candles": result["candles"],
        "closed": len(result["closed_profits"]),
        "net_profit": metrics["net_profit"],
        "profit_factor": metrics["profit_factor"],
        "max_drawdown": drawdown,
    }


def run_file(path: Path, limit: int, initial_balance: float, tick_limit: int) -> list[dict]:
    if "_M1_" in path.name:
        candles = load_mt5_candles_csv(path, limit=limit)
    else:
        ticks = _read_tick_sample(path, tick_limit)
        candles = aggregate_ticks_to_candles(ticks)[:limit]
    if not candles:
        raise ValueError(f"no candles loaded from {path}")
    current = CombinedVotingStrategy(
        [SupertrendAdapter(), HalfTrendAdapter(), RSIAdapter(), MACDAdapter()],
        symbol="XAUUSD",
        volume=0.01,
        rr=2.0,
        min_votes=2,
    )
    results = [_run(candles, current, "current", initial_balance)]

    frame = pd.DataFrame(
        [
            {
                "time": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "tick_volume": candle.volume,
            }
            for candle in candles
        ]
    )
    trigger = backtest_supertrend(
        "XAUUSD", "1m", len(frame), atr_period=10, multiplier=3.0, data=frame
    )["signal"]
    confirmation = backtest_trend_ali(
        "XAUUSD", "1m", len(frame), length=60, length_mult=6.0, mode="Hma", data=frame
    )["trend"]

    def legacy(history, candle):
        index = len(history)
        if index >= len(trigger) or trigger[index] not in {"buy", "sell"}:
            return []
        direction = trigger[index]
        if direction != confirmation[index]:
            return []
        entry = candle.open
        sl = entry - 1.0 if direction == "buy" else entry + 1.0
        tp = entry + 2.0 if direction == "buy" else entry - 2.0
        return [
            ReplaySignal(
                f"legacy-{index}",
                "XAUUSD",
                0.01,
                0 if direction == "buy" else 1,
                entry,
                sl,
                tp,
                "legacy",
            )
        ]

    results.append(_run(candles, legacy, "legacy", initial_balance))
    return results


def _read_tick_sample(path: Path, tick_limit: int):
    ticks = []
    for tick in iter_mt5_ticks_csv(path):
        ticks.append(tick)
        if len(ticks) >= tick_limit:
            break
    return ticks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--initial-balance", type=float, default=5000.0)
    parser.add_argument("--tick-limit", type=int, default=100000)
    args = parser.parse_args()
    for path in args.files:
        if "_M1_" in path.name:
            candles = load_mt5_candles_csv(path, limit=args.limit)
        else:
            candles = aggregate_ticks_to_candles(
                _read_tick_sample(path, args.tick_limit)
            )[: args.limit]
        print(
            f"DATA {path.name}: {len(candles)} candles "
            f"{candles[0].timestamp} -> {candles[-1].timestamp}"
        )
        for result in run_file(path, args.limit, args.initial_balance, args.tick_limit):
            print(result)


if __name__ == "__main__":
    main()
