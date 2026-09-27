from __future__ import annotations
from typing import Any
import pandas as pd
import feature_engineering
from ml_signal_adapter import positive_class_probability, signal_from_positive_probability

def build_backtest_signals(data: pd.DataFrame, artifact: dict[str, Any], *, holdout_start: str | pd.Timestamp, threshold: float = 0.55) -> tuple[list[str], dict[str, Any]]:
    """Convert a Phase 6 artifact into the existing backtester signal contract.

    Prediction uses row t-1 features and is applied to row t. This module does
    not import MT5 or execute orders; the existing backtester owns positions/PnL.
    """
    frame = data.copy(deep=True).reset_index(drop=True)
    if "timestamp" not in frame.columns:
        raise ValueError("timestamp column is required")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    if not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("data must be chronological")
    holdout = pd.Timestamp(holdout_start)
    if holdout <= frame["timestamp"].min() or holdout > frame["timestamp"].max():
        raise ValueError("holdout_start must lie inside the dataset")
    features = feature_engineering.build_features(frame, drop_warmup=True).frame
    model = artifact["model"]
    scaler = artifact["scaler"]
    columns = list(artifact["feature_columns"])
    missing = [c for c in columns if c not in features.columns]
    if missing:
        raise ValueError(f"artifact feature columns missing: {missing}")
    probabilities = positive_class_probability(model, scaler.transform(features[columns]))
    probability_by_index = dict(zip(features.index.to_numpy(), probabilities))
    signals = ["hold"] * len(frame)
    for t in range(1, len(frame)):
        if frame.loc[t, "timestamp"] < holdout:
            continue
        decision_index = t - 1
        if decision_index not in probability_by_index:
            continue
        signal = signal_from_positive_probability(probability_by_index[decision_index], threshold=threshold)
        signals[t] = {1: "buy", -1: "sell", 0: "hold"}[signal]
    return signals, {"holdout_start": holdout.isoformat(), "threshold": float(threshold), "decision_lag_bars": 1, "execution_contract": "existing_backtester_row_t"}
