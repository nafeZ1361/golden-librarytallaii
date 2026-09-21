"""Phase 5 time-series validation layer for deterministic split and walk-forward logic."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd

import dataset_pipeline
import feature_engineering

VALIDATION_VERSION = "phase5-v1"
DEFAULT_TRAIN_RATIO = 0.7
DEFAULT_VALIDATION_RATIO = 0.15
DEFAULT_TEST_RATIO = 0.15


class TimeSeriesValidationError(ValueError):
    """Raised for invalid split parameters or impossible validation layouts."""


@dataclass(frozen=True)
class SplitResult:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    metadata: dict[str, Any]
    split_hash: str


@dataclass(frozen=True)
class FoldResult:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    metadata: dict[str, Any]
    fold_hash: str


def _coerce_frame(data: Any) -> pd.DataFrame:
    if isinstance(data, dataset_pipeline.DatasetResult):
        frame = data.frame.copy(deep=True)
    elif isinstance(data, pd.DataFrame):
        frame = data.copy(deep=True)
    else:
        raise TypeError("data must be a pandas DataFrame or DatasetResult")
    if frame.empty:
        raise TimeSeriesValidationError("dataset is empty")
    if "timestamp" not in frame.columns:
        raise TimeSeriesValidationError("timestamp column is required")
    frame = frame.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    return frame


def _resolve_split_sizes(
    total_rows: int,
    *,
    train_ratio: float | None = None,
    validation_ratio: float | None = None,
    test_ratio: float | None = None,
    train_size: int | None = None,
    validation_size: int | None = None,
    test_size: int | None = None,
) -> tuple[int, int, int]:
    if train_size is not None and train_ratio is not None:
        raise ValueError("provide either train_size or train_ratio, not both")
    if validation_size is not None and validation_ratio is not None:
        raise ValueError("provide either validation_size or validation_ratio, not both")
    if test_size is not None and test_ratio is not None:
        raise ValueError("provide either test_size or test_ratio, not both")

    if train_ratio is not None:
        if train_ratio <= 0:
            raise TimeSeriesValidationError("train_ratio must be positive")
    if validation_ratio is not None:
        if validation_ratio <= 0:
            raise TimeSeriesValidationError("validation_ratio must be positive")
    if test_ratio is not None:
        if test_ratio <= 0:
            raise TimeSeriesValidationError("test_ratio must be positive")

    if train_size is None:
        train_ratio_value = train_ratio if train_ratio is not None else DEFAULT_TRAIN_RATIO
        validation_ratio_value = validation_ratio if validation_ratio is not None else DEFAULT_VALIDATION_RATIO
        test_ratio_value = test_ratio if test_ratio is not None else DEFAULT_TEST_RATIO
        ratio_total = train_ratio_value + validation_ratio_value + test_ratio_value
        if ratio_total > 1.0 + 1e-9:
            raise TimeSeriesValidationError("requested ratio split exceeds 100% of the dataset")

        raw_counts = [
            total_rows * train_ratio_value,
            total_rows * validation_ratio_value,
            total_rows * test_ratio_value,
        ]
        counts = [int(v // 1) for v in raw_counts]
        remaining = total_rows - sum(counts)
        order = sorted(range(3), key=lambda i: (raw_counts[i] - counts[i], i), reverse=True)
        for idx in order[:remaining]:
            counts[idx] += 1
        train_size, validation_size, test_size = counts
    else:
        if train_size <= 0 or validation_size <= 0 or test_size <= 0:
            raise TimeSeriesValidationError("train, validation, and test sizes must all be positive")
        if train_size + validation_size + test_size > total_rows:
            raise TimeSeriesValidationError("requested split sizes exceed the available dataset")

    if train_size <= 0 or validation_size <= 0 or test_size <= 0:
        raise TimeSeriesValidationError("train, validation, and test sizes must all be positive")
    return train_size, validation_size, test_size


def _hash_payload(frame: pd.DataFrame, metadata: dict[str, Any]) -> str:
    rows = []
    for row in frame.to_dict(orient="records"):
        rows.append({key: (value.isoformat() if hasattr(value, "isoformat") else value)
                     for key, value in row.items()})
    payload = {"metadata": metadata, "columns": list(frame.columns), "rows": rows}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def split_time_series(
    data: Any,
    *,
    train_ratio: float | None = None,
    validation_ratio: float | None = None,
    test_ratio: float | None = None,
    train_size: int | None = None,
    validation_size: int | None = None,
    test_size: int | None = None,
    horizon: int = 1,
    purge: int = 0,
    embargo: int = 0,
) -> SplitResult:
    """Create a deterministic train/validation/test split with purge and embargo protection."""
    if not isinstance(horizon, int) or horizon <= 0:
        raise TimeSeriesValidationError("horizon must be a positive integer")
    if not isinstance(purge, int) or purge < 0:
        raise TimeSeriesValidationError("purge must be a non-negative integer")
    if not isinstance(embargo, int) or embargo < 0:
        raise TimeSeriesValidationError("embargo must be a non-negative integer")

    frame = _coerce_frame(data)
    feature_frame = feature_engineering.build_features(frame, drop_warmup=True).frame
    frame = feature_frame.copy().reset_index(drop=True)
    train_size, validation_size, test_size = _resolve_split_sizes(
        len(frame),
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
    )

    guard = max(horizon, purge)
    if train_size <= 0 or validation_size <= 0 or test_size <= 0:
        raise TimeSeriesValidationError("train, validation, and test sizes must all be positive")
    if train_size <= guard:
        raise TimeSeriesValidationError("insufficient training rows after horizon purge protection")

    train_end = train_size - guard
    validation_start = train_end + embargo
    validation_end = validation_start + validation_size
    test_start = validation_end + embargo
    test_end = test_start + test_size

    if validation_start < train_end or test_start < validation_end:
        raise TimeSeriesValidationError("split boundaries are invalid after purge and embargo")
    if test_end > len(frame):
        raise TimeSeriesValidationError("insufficient rows remain after purge and embargo protection")

    train = frame.iloc[:train_end].copy()
    validation = frame.iloc[validation_start:validation_end].copy()
    test = frame.iloc[test_start:test_end].copy()

    if not train["timestamp"].is_monotonic_increasing:
        raise TimeSeriesValidationError("training timestamps are not in order")
    if not validation["timestamp"].is_monotonic_increasing:
        raise TimeSeriesValidationError("validation timestamps are not in order")
    if not test["timestamp"].is_monotonic_increasing:
        raise TimeSeriesValidationError("test timestamps are not in order")
    if not validation["timestamp"].iloc[0] > train["timestamp"].iloc[-1]:
        raise TimeSeriesValidationError("validation data overlaps or precedes training data")
    if not test["timestamp"].iloc[0] > validation["timestamp"].iloc[-1]:
        raise TimeSeriesValidationError("test data overlaps or precedes validation data")

    metadata = {
        "validation_version": VALIDATION_VERSION,
        "horizon": horizon,
        "purge": purge,
        "embargo": embargo,
        "train_size": int(len(train)),
        "validation_size": int(len(validation)),
        "test_size": int(len(test)),
        "train_end": int(train_end),
        "validation_start": int(validation_start),
        "validation_end": int(validation_end),
        "test_start": int(test_start),
        "test_end": int(test_end),
        "timestamp_key": "timestamp",
        "chronological": True,
        "uses_purge_for_horizon": guard == horizon,
    }
    return SplitResult(train=train, validation=validation, test=test, metadata=metadata,
                       split_hash=_hash_payload(pd.concat([train, validation, test], ignore_index=True), metadata))


def walk_forward_validation(
    data: Any,
    *,
    train_size: int,
    validation_size: int,
    test_size: int,
    horizon: int = 1,
    purge: int = 0,
    embargo: int = 0,
    step: int | None = None,
) -> list[FoldResult]:
    """Create deterministic walk-forward folds while preserving chronology and purge guarantees."""
    if not isinstance(train_size, int) or train_size <= 0:
        raise TimeSeriesValidationError("train_size must be a positive integer")
    if not isinstance(validation_size, int) or validation_size <= 0:
        raise TimeSeriesValidationError("validation_size must be a positive integer")
    if not isinstance(test_size, int) or test_size <= 0:
        raise TimeSeriesValidationError("test_size must be a positive integer")
    if step is None:
        step = validation_size
    if not isinstance(step, int) or step <= 0:
        raise TimeSeriesValidationError("step must be a positive integer")

    frame = _coerce_frame(data)
    guard = max(horizon, purge)
    total_required = train_size + validation_size + test_size + guard + embargo
    if len(frame) < total_required:
        raise TimeSeriesValidationError("insufficient data for walk-forward validation")

    folds: list[FoldResult] = []
    start = 0
    max_start = len(frame) - total_required
    while start <= max_start:
        train_end = start + train_size
        train_cut = train_end - guard
        validation_start = train_cut + embargo
        validation_end = validation_start + validation_size
        test_start = validation_end + embargo
        test_end = test_start + test_size
        if test_end > len(frame):
            break
        train = frame.iloc[start:train_cut].copy()
        validation = frame.iloc[validation_start:validation_end].copy()
        test = frame.iloc[test_start:test_end].copy()

        if not validation.empty and not test.empty:
            if validation["timestamp"].iloc[0] <= train["timestamp"].iloc[-1]:
                raise TimeSeriesValidationError("fold validation overlaps with training data")
            if test["timestamp"].iloc[0] <= validation["timestamp"].iloc[-1]:
                raise TimeSeriesValidationError("fold test overlaps with validation data")

        metadata = {
            "fold_index": len(folds),
            "train_start": int(start),
            "train_end": int(train_end),
            "validation_start": int(validation_start),
            "validation_end": int(validation_end),
            "test_start": int(test_start),
            "test_end": int(test_end),
            "horizon": horizon,
            "purge": purge,
            "embargo": embargo,
        }
        folds.append(FoldResult(train=train, validation=validation, test=test, metadata=metadata,
                                fold_hash=_hash_payload(pd.concat([train, validation, test], ignore_index=True), metadata)))
        start += step
    if not folds:
        raise TimeSeriesValidationError("no valid walk-forward folds were created")
    return folds


class TimeSeriesValidator:
    """Small facade for the deterministic Phase 5 split contract."""

    def __init__(
        self,
        *,
        train_ratio: float | None = None,
        validation_ratio: float | None = None,
        test_ratio: float | None = None,
        train_size: int | None = None,
        validation_size: int | None = None,
        test_size: int | None = None,
        horizon: int = 1,
        purge: int = 0,
        embargo: int = 0,
    ) -> None:
        self.train_ratio = train_ratio
        self.validation_ratio = validation_ratio
        self.test_ratio = test_ratio
        self.train_size = train_size
        self.validation_size = validation_size
        self.test_size = test_size
        self.horizon = horizon
        self.purge = purge
        self.embargo = embargo

    def split(self, data: Any) -> SplitResult:
        return split_time_series(
            data,
            train_ratio=self.train_ratio,
            validation_ratio=self.validation_ratio,
            test_ratio=self.test_ratio,
            train_size=self.train_size,
            validation_size=self.validation_size,
            test_size=self.test_size,
            horizon=self.horizon,
            purge=self.purge,
            embargo=self.embargo,
        )
