"""Deterministic Phase 4 target and label generation for research datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

import dataset_pipeline

TARGET_VERSION = "phase4-v1"
DEFAULT_HORIZONS: tuple[int, ...] = (1, 3, 5, 10)


class TargetGenerationError(ValueError):
    """Base error for invalid target-generation inputs or outputs."""


class TargetInputError(TargetGenerationError):
    """Raised when input data cannot be used as a canonical research dataset."""


@dataclass(frozen=True)
class TargetResult:
    frame: pd.DataFrame
    metadata: dict[str, Any]
    target_hash: str


def _canonical_input(data: Any) -> tuple[pd.DataFrame, dict[str, Any]]:
    if isinstance(data, dataset_pipeline.DatasetResult):
        frame = data.frame.copy(deep=True)
        source_metadata = dict(data.metadata)
    elif isinstance(data, pd.DataFrame):
        prepared = dataset_pipeline.prepare_dataset(data)
        frame = prepared.frame.copy(deep=True)
        source_metadata = dict(prepared.metadata)
    else:
        raise TypeError("data must be a pandas DataFrame or DatasetResult")

    required = set(dataset_pipeline.REQUIRED_COLUMNS)
    if not required.issubset(frame.columns):
        raise TargetInputError("input must contain canonical timestamp and OHLC columns")
    if frame["timestamp"].duplicated().any():
        raise dataset_pipeline.DuplicateTimestampError("duplicate timestamps are not allowed")
    if len(frame) > 1 and not frame["timestamp"].is_monotonic_increasing:
        raise TargetInputError("input chronology must be increasing")
    return frame, source_metadata


def _future_return(close: pd.Series, horizon: int) -> pd.Series:
    if not isinstance(horizon, int):
        raise TypeError("horizon must be an integer")
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    future_close = close.shift(-horizon)
    return (future_close - close) / close.replace(0, np.nan)


def _directional_label(future_return: pd.Series, threshold: float) -> pd.Series:
    if not isinstance(threshold, (int, float)):
        raise TypeError("threshold must be numeric")
    label = (future_return > float(threshold)).astype(float)
    label = label.where(future_return.notna(), np.nan)
    return label


def _hash_payload(frame: pd.DataFrame, metadata: dict[str, Any]) -> str:
    rows = []
    for row in frame.to_dict(orient="records"):
        rows.append({key: (value.isoformat() if hasattr(value, "isoformat") else value)
                     for key, value in row.items()})
    payload = {"metadata": metadata, "columns": list(frame.columns), "rows": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalise_horizons(horizons: Iterable[int] | None) -> tuple[int, ...]:
    if horizons is None:
        candidates = DEFAULT_HORIZONS
    else:
        candidates = tuple(int(value) for value in horizons)
    if not candidates:
        raise ValueError("at least one horizon is required")
    for value in candidates:
        if value <= 0:
            raise ValueError("horizons must be positive integers")
    unique = []
    seen = set()
    for value in candidates:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return tuple(sorted(unique))


def build_targets(data: Any, *, horizons: Iterable[int] | None = None,
                 threshold: float = 0.0) -> TargetResult:
    """Build future-return and directional-label targets without train/test splitting."""
    if not isinstance(threshold, (int, float)):
        raise TypeError("threshold must be numeric")
    ordered_horizons = _normalise_horizons(horizons)
    frame, source_metadata = _canonical_input(data)
    output = frame.copy(deep=True).sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    for horizon in ordered_horizons:
        future_return = _future_return(output["close"].astype(float), horizon)
        output[f"future_return_{horizon}"] = future_return
        output[f"label_{horizon}"] = _directional_label(future_return, threshold)

    metadata = {
        "target_version": TARGET_VERSION,
        "dataset_version": source_metadata.get("version"),
        "horizons": list(ordered_horizons),
        "threshold": float(threshold),
        "target_schema": {
            "future_return": "(future_close - current_close) / current_close",
            "label": "1 when future_return > threshold else 0, NaN when unavailable",
        },
        "input_row_count": int(len(frame)),
        "output_row_count": int(len(output)),
        "timezone": source_metadata.get("timezone"),
    }
    return TargetResult(output, metadata, _hash_payload(output, metadata))


class TargetGenerator:
    """Minimal state-free wrapper around the Phase 4 target contract."""

    def __init__(self, *, horizons: Iterable[int] | None = None, threshold: float = 0.0) -> None:
        self.horizons = _normalise_horizons(horizons)
        self.threshold = float(threshold)

    def fit_transform(self, data: Any) -> TargetResult:
        return build_targets(data, horizons=self.horizons, threshold=self.threshold)
