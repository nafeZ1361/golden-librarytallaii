"""Deterministic, local-only Phase 3 feature engineering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

import dataset_pipeline

FEATURE_VERSION = "phase3-v1"
_FEATURE_NAMES = (
    "return_1", "return_3", "return_5", "return_10", "log_return_1",
    "rolling_std_10", "true_range", "atr_14", "normalized_volatility",
    "sma_10", "ema_10", "price_vs_sma_10", "price_vs_ema_10", "ema_relationship",
    "rsi_14", "roc_10", "momentum_10", "range", "body", "upper_wick",
    "lower_wick", "body_range_ratio", "close_position", "volume_change_1",
    "volume_mean_10", "relative_volume_10",
)


class FeatureEngineeringError(ValueError):
    """Base error for invalid feature-engineering inputs or outputs."""


class FeatureInputError(FeatureEngineeringError):
    """Raised when the input is not a valid canonical dataset."""


class FeatureValidationError(FeatureEngineeringError):
    """Raised when generated features violate the Phase 3 contract."""


@dataclass(frozen=True)
class FeatureResult:
    frame: pd.DataFrame
    metadata: dict[str, Any]
    feature_hash: str


def _canonical_input(data: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    if isinstance(data, dataset_pipeline.DatasetResult):
        frame = data.frame.copy(deep=True)
        source_metadata = dict(data.metadata)
    elif isinstance(data, pd.DataFrame):
        try:
            prepared = dataset_pipeline.prepare_dataset(data)
        except dataset_pipeline.DuplicateTimestampError:
            raise
        except (TypeError, ValueError) as exc:
            raise FeatureInputError(str(exc)) from exc
        frame = prepared.frame.copy(deep=True)
        source_metadata = dict(prepared.metadata)
    else:
        raise TypeError("data must be a pandas DataFrame or DatasetResult")
    required = set(dataset_pipeline.REQUIRED_COLUMNS)
    if not required.issubset(frame.columns):
        raise FeatureInputError("input must contain canonical timestamp and OHLC columns")
    if frame["timestamp"].duplicated().any():
        raise dataset_pipeline.DuplicateTimestampError("duplicate timestamps are not allowed")
    if len(frame) > 1 and not frame["timestamp"].is_monotonic_increasing:
        raise FeatureInputError("input chronology must be increasing")
    return frame, source_metadata


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator / denominator.replace(0, np.nan)


def _build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)
    open_price = frame["open"].astype(float)
    result = frame.copy(deep=True)
    for periods in (1, 3, 5, 10):
        result[f"return_{periods}"] = close.pct_change(periods=periods)
    result["log_return_1"] = np.log(_safe_ratio(close, close.shift(1)))
    previous_close = close.shift(1)
    true_range = pd.concat(
        [(high - low), (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    ).max(axis=1, skipna=False)
    result["true_range"] = true_range
    result["atr_14"] = true_range.rolling(14, min_periods=14).mean()
    result["rolling_std_10"] = close.pct_change().rolling(10, min_periods=10).std()
    result["normalized_volatility"] = _safe_ratio(result["rolling_std_10"], close)
    result["sma_10"] = close.rolling(10, min_periods=10).mean()
    result["ema_10"] = close.ewm(span=10, adjust=False, min_periods=10).mean()
    result["price_vs_sma_10"] = _safe_ratio(close - result["sma_10"], result["sma_10"])
    result["price_vs_ema_10"] = _safe_ratio(close - result["ema_10"], result["ema_10"])
    result["ema_relationship"] = _safe_ratio(result["ema_10"], result["sma_10"]) - 1.0
    delta = close.diff()
    gains = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    losses = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    relative_strength = _safe_ratio(gains, losses)
    rsi = 100.0 - (100.0 / (1.0 + relative_strength))
    rsi = rsi.mask((losses == 0) & (gains > 0), 100.0)
    rsi = rsi.mask((losses == 0) & (gains == 0), 50.0)
    result["rsi_14"] = rsi
    result["roc_10"] = close.pct_change(10)
    result["momentum_10"] = close - close.shift(10)
    candle_range = high - low
    result["range"] = candle_range
    result["body"] = close - open_price
    result["upper_wick"] = high - pd.concat([open_price, close], axis=1).max(axis=1)
    result["lower_wick"] = pd.concat([open_price, close], axis=1).min(axis=1) - low
    result["body_range_ratio"] = _safe_ratio(result["body"].abs(), candle_range)
    result["close_position"] = _safe_ratio(close - low, candle_range)
    if "volume" in frame.columns:
        volume = frame["volume"].astype(float)
        result["volume_change_1"] = volume.pct_change()
        result["volume_mean_10"] = volume.rolling(10, min_periods=10).mean()
        result["relative_volume_10"] = _safe_ratio(volume, result["volume_mean_10"])
    return result


def _hash_payload(frame: pd.DataFrame, metadata: dict[str, Any]) -> str:
    rows = []
    for row in frame.to_dict(orient="records"):
        rows.append({key: (value.isoformat() if hasattr(value, "isoformat") else value)
                     for key, value in row.items()})
    payload = {"metadata": metadata, "columns": list(frame.columns), "rows": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_features(data: Any, *, drop_warmup: bool = True) -> FeatureResult:
    """Build trailing-only features without labels, splits, or MT5 access."""
    if not isinstance(drop_warmup, bool):
        raise TypeError("drop_warmup must be bool")
    frame, source_metadata = _canonical_input(data)
    output = _build_feature_frame(frame)
    available_features = [name for name in _FEATURE_NAMES if name in output.columns]
    usable = output[available_features].notna().all(axis=1)
    if drop_warmup:
        output = output.loc[usable].reset_index(drop=True)
    numeric_columns = [name for name in available_features if name in output.columns]
    if not all(pd.api.types.is_numeric_dtype(output[name]) for name in numeric_columns):
        raise FeatureValidationError("feature columns must be numeric")
    if any(np.isinf(output[name].to_numpy(dtype=float)).any() for name in numeric_columns):
        raise FeatureValidationError("features contain infinity")
    if len(output) > 1 and not output["timestamp"].is_monotonic_increasing:
        raise FeatureValidationError("output chronology is not increasing")
    metadata = {
        "feature_version": FEATURE_VERSION,
        "dataset_version": source_metadata.get("version"),
        "feature_names": available_features,
        "warmup_policy": {"drop_warmup": drop_warmup, "fill": "never", "min_periods": "window"},
        "input_row_count": int(len(frame)),
        "output_row_count": int(len(output)),
        "volume_type": source_metadata.get("volume_type") if "volume" in frame.columns else None,
        "timezone": source_metadata.get("timezone"),
    }
    return FeatureResult(output, metadata, _hash_payload(output, metadata))


class FeatureEngineer:
    """Small state-free facade for the Phase 3 feature contract."""

    def __init__(self, *, drop_warmup: bool = True) -> None:
        self.drop_warmup = drop_warmup

    def fit_transform(self, data: Any) -> FeatureResult:
        return build_features(data, drop_warmup=self.drop_warmup)