"""Pure historical ML replay using Phase 6 artifacts; no MT5 and no live execution."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

import feature_engineering
from ml_signal_adapter import positive_class_probability, signal_from_positive_probability


@dataclass(frozen=True)
class ReplayResult:
    trades: pd.DataFrame
    equity: pd.DataFrame
    metrics: dict[str, float]
    evidence: dict[str, Any]


def _artifact_predict_proba(artifact: dict[str, Any], feature_frame: pd.DataFrame) -> np.ndarray:
    model = artifact["model"]
    scaler = artifact["scaler"]
    columns = list(artifact["feature_columns"])
    missing = [c for c in columns if c not in feature_frame.columns]
    if missing:
        raise ValueError(f"artifact feature columns missing: {missing}")
    X = feature_frame[columns]
    X_scaled = scaler.transform(X)
    return positive_class_probability(model, X_scaled)


def replay_model(
    data: pd.DataFrame,
    artifact: dict[str, Any],
    *,
    holdout_start: str | pd.Timestamp,
    threshold: float = 0.55,
    initial_balance: float = 5000.0,
    transaction_cost: float = 0.0,
) -> ReplayResult:
    """Replay signals generated at close[t] and execute at open[t+1].

    The holdout is the only execution window. The supplied model artifact must
    already be trained; this function never fits a model or accesses MT5.
    """
    if initial_balance <= 0 or transaction_cost < 0:
        raise ValueError("initial_balance must be positive and transaction_cost non-negative")
    frame = data.copy(deep=True)
    required = {"timestamp", "open", "close"}
    if not required.issubset(frame.columns):
        raise ValueError(f"missing required columns: {sorted(required - set(frame.columns))}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    holdout = pd.Timestamp(holdout_start)
    if not holdout.tzinfo and getattr(frame["timestamp"].dt, "tz", None) is not None:
        holdout = holdout.tz_localize(frame["timestamp"].dt.tz)
    if holdout <= frame["timestamp"].min() or holdout > frame["timestamp"].max():
        raise ValueError("holdout_start must lie inside the dataset")

    features = feature_engineering.build_features(frame, drop_warmup=True).frame
    probs = _artifact_predict_proba(artifact, features)
    feature_index = features.index.to_numpy()
    probability_by_row = dict(zip(feature_index, probs))

    balance = float(initial_balance)
    position = 0
    entry_price = None
    trades: list[dict[str, Any]] = []
    equity_rows = [{"timestamp": frame.iloc[0]["timestamp"], "equity": balance}]

    for i in range(len(frame) - 1):
        decision_ts = frame.iloc[i]["timestamp"]
        execution = frame.iloc[i + 1]
        if decision_ts < holdout or i not in probability_by_row:
            continue
        signal = signal_from_positive_probability(probability_by_row[i], threshold=threshold)
        desired = signal
        if desired == 0 or desired == position:
            equity_rows.append({"timestamp": execution["timestamp"], "equity": balance})
            continue
        execution_price = float(execution["open"])
        if position != 0 and entry_price is not None:
            pnl = (execution_price - entry_price) * position - transaction_cost
            balance += pnl
            trades.append({"entry_price": entry_price, "exit_price": execution_price,
                           "side": position, "pnl": pnl,
                           "exit_time": execution["timestamp"]})
            entry_price = None
        if desired != 0:
            position = desired
            entry_price = execution_price
        else:
            position = 0
        equity_rows.append({"timestamp": execution["timestamp"], "equity": balance})

    if position != 0 and entry_price is not None:
        execution = frame.iloc[-1]
        pnl = (float(execution["close"]) - entry_price) * position - transaction_cost
        balance += pnl
        trades.append({"entry_price": entry_price, "exit_price": float(execution["close"]),
                       "side": position, "pnl": pnl, "exit_time": execution["timestamp"]})
        equity_rows.append({"timestamp": execution["timestamp"], "equity": balance})

    trades_df = pd.DataFrame(trades)
    equity = pd.DataFrame(equity_rows).drop_duplicates(subset=["timestamp"], keep="last")
    running_peak = equity["equity"].cummax()
    drawdown = (running_peak - equity["equity"]).max()
    total = len(trades_df)
    wins = int((trades_df["pnl"] > 0).sum()) if total else 0
    losses = int((trades_df["pnl"] < 0).sum()) if total else 0
    gross_win = float(trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()) if total else 0.0
    gross_loss = float(-trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum()) if total else 0.0
    metrics = {"initial_balance": initial_balance, "final_balance": balance,
               "total_pnl": balance - initial_balance, "total_trades": float(total),
               "win_rate": (wins / total) if total else 0.0,
               "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf"),
               "max_drawdown": float(drawdown)}
    payload = {"metrics": metrics, "holdout_start": holdout.isoformat(),
               "threshold": threshold, "transaction_cost": transaction_cost}
    evidence = {**payload, "evidence_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()}
    return ReplayResult(trades_df, equity, metrics, evidence)
