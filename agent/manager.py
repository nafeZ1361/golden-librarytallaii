"""Safe MVP manager for backtest experiments.

This module deliberately manages historical experiments only. It does not
import MetaTrader5, change risk settings, or send live orders.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from module.backtest import HistoricalReplay
from module.market_data import Candle
from module.paper import PaperBroker
from module.performance import calculate_performance
from module.strategy_adapter import (
    CombinedVotingStrategy,
    HalfTrendAdapter,
    MACDAdapter,
    RSIAdapter,
    SupertrendAdapter,
)


@dataclass(frozen=True)
class ExperimentSpec:
    """Versioned configuration for one historical experiment."""

    name: str = "current-combined"
    symbol: str = "XAUUSD"
    volume: float = 0.01
    rr: float = 2.0
    min_votes: int = 2
    supertrend_atr_period: int = 10
    supertrend_multiplier: float = 3.0
    halftrend_amplitude: int = 2
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal_period: int = 9

    def validate(self) -> None:
        if self.volume <= 0 or self.rr <= 0:
            raise ValueError("volume and rr must be positive")
        if self.min_votes < 1 or self.min_votes > 4:
            raise ValueError("min_votes must be between 1 and 4")
        if self.macd_fast >= self.macd_slow:
            raise ValueError("macd_fast must be lower than macd_slow")


@dataclass
class ExperimentResult:
    experiment_id: str
    spec: dict[str, Any]
    train: dict[str, Any]
    test: dict[str, Any]
    passed: bool
    score: float
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _strategy(spec: ExperimentSpec) -> CombinedVotingStrategy:
    spec.validate()
    return CombinedVotingStrategy(
        [
            SupertrendAdapter(spec.supertrend_atr_period, spec.supertrend_multiplier),
            HalfTrendAdapter(spec.halftrend_amplitude),
            RSIAdapter(spec.rsi_period),
            MACDAdapter(spec.macd_fast, spec.macd_slow, spec.macd_signal_period),
        ],
        symbol=spec.symbol,
        volume=spec.volume,
        rr=spec.rr,
        min_votes=spec.min_votes,
        comment=spec.name,
    )


def _run(candles: list[Candle], spec: ExperimentSpec, initial_balance: float) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="experiment-") as directory:
        broker = PaperBroker(Path(directory) / "paper.json", initial_balance=initial_balance)
        replay = HistoricalReplay(broker, initial_balance=initial_balance)
        result = replay.run(candles, _strategy(spec))
        metrics = dict(result["metrics"])
        metrics["candles"] = len(candles)
        metrics["closed"] = len(result["closed_profits"])
        metrics["max_drawdown_percent"] = broker.max_drawdown()["max_drawdown_percent"]
        return metrics


class ExperimentManager:
    """Run, persist, rank, and gate historical strategy experiments."""

    def __init__(
        self,
        store_path: str | Path = "experiments/results.jsonl",
        *,
        initial_balance: float = 5000.0,
        min_test_trades: int = 1,
        max_test_drawdown_percent: float = 20.0,
    ) -> None:
        self.store_path = Path(store_path)
        self.initial_balance = float(initial_balance)
        self.min_test_trades = int(min_test_trades)
        self.max_test_drawdown_percent = float(max_test_drawdown_percent)

    def run(self, candles: Iterable[Candle], spec: ExperimentSpec) -> ExperimentResult:
        rows = sorted(candles, key=lambda item: item.timestamp)
        if len(rows) < 4:
            raise ValueError("at least four candles are required for train/test")
        split = max(1, int(len(rows) * 0.7))
        train_rows, test_rows = rows[:split], rows[split:]
        train = _run(train_rows, spec, self.initial_balance)
        test = _run(test_rows, spec, self.initial_balance)
        passed = (
            test["trades"] >= self.min_test_trades
            and test["max_drawdown_percent"] <= self.max_test_drawdown_percent
            and test["net_profit"] > 0
        )
        score = float(test["net_profit"]) - float(test["max_drawdown"]) * 0.5
        payload = json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))
        experiment_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        result = ExperimentResult(experiment_id, asdict(spec), train, test, passed, score)
        self._append(result)
        return result

    def grid(self, candles: Iterable[Candle], parameter_grid: dict[str, Iterable[Any]]) -> list[ExperimentResult]:
        """Run a bounded Cartesian grid of ExperimentSpec values."""
        import random
        keys = list(parameter_grid)
        values = [list(parameter_grid[key]) for key in keys]
        
        # H3: Effective optimization cap - max 50 combinations
        MAX_TRIALS = 50
        
        # Calculate total combinations without building full list
        total_combinations = 1
        for vlist in values:
            total_combinations *= len(vlist)
        
        # Apply deterministic cap using hash-based selection
        if total_combinations > MAX_TRIALS:
            study_seed = f"experiment_manager_grid"
            # Generate selected combinations deterministically without full list
            selected_indices = set()
            rng = random.Random(study_seed)
            while len(selected_indices) < MAX_TRIALS:
                idx = rng.randint(0, total_combinations - 1)
                selected_indices.add(idx)
            
            def index_to_combination(idx, shape, values_list):
                """Convert linear index to combination tuple."""
                combo = []
                remaining = idx
                for i in range(len(shape) - 1, -1, -1):
                    combo.append(values_list[i][remaining % shape[i]])
                    remaining //= shape[i]
                return tuple(reversed(combo))
            
            shape = [len(v) for v in values]
            all_combinations = [index_to_combination(idx, shape, values) for idx in sorted(selected_indices)]
            print(f"[H3] Cap enforced in grid: selected {MAX_TRIALS} of {total_combinations} combinations")
        else:
            all_combinations = list(itertools.product(*values))
        
        results = []
        for combination in all_combinations:
            values_for_spec = dict(zip(keys, combination))
            results.append(self.run(candles, ExperimentSpec(**values_for_spec)))
        return results

    def best(self, results: Iterable[ExperimentResult]) -> ExperimentResult | None:
        candidates = [result for result in results if result.passed]
        return max(candidates, key=lambda result: result.score, default=None)

    def _append(self, result: ExperimentResult) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")

    def history(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []
        rows = []
        for line in self.store_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
