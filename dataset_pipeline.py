"""Independent, deterministic preparation of canonical research datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

CANONICAL_VERSION = "phase2-v1"
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")
DuplicatePolicy = Literal["reject", "first", "last"]


class DatasetPipelineError(ValueError):
    """Base error for an invalid or unusable research dataset."""


class DatasetValidationError(DatasetPipelineError):
    """Raised when values or column types violate the dataset contract."""


class DuplicateTimestampError(DatasetPipelineError):
    """Raised when duplicate timestamps are present under the reject policy."""


class LeakageError(DatasetPipelineError):
    """Raised when passthrough inputs cannot be aligned without guessing."""


@dataclass(frozen=True)
class DatasetResult:
    frame: pd.DataFrame
    metadata: dict[str, Any]
    dataset_hash: str


def _normalise_timestamp(frame: pd.DataFrame) -> pd.DataFrame:
    has_timestamp = "timestamp" in frame.columns
    has_time = "time" in frame.columns
    if has_timestamp and has_time:
        raise DatasetValidationError("provide exactly one timestamp column: timestamp or time")
    if has_time:
        frame = frame.rename(columns={"time": "timestamp"})
    if "timestamp" not in frame.columns:
        raise DatasetValidationError("missing required column: timestamp/time")
    try:
        parsed = pd.to_datetime(frame["timestamp"], errors="coerce", format="mixed")
    except (TypeError, ValueError) as exc:
        raise DatasetValidationError("timestamp values are not parseable") from exc
    if parsed.isna().any():
        raise DatasetValidationError("timestamp contains missing or invalid values")
    awareness = [getattr(value, "tzinfo", None) is not None for value in parsed]
    if any(awareness) and not all(awareness):
        raise DatasetValidationError("timestamp cannot mix timezone-aware and naive values")
    frame = frame.copy()
    frame["timestamp"] = parsed
    return frame


def _canonical_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if "volume" in frame.columns and "tick_volume" in frame.columns:
        raise DatasetValidationError("provide exactly one volume column: volume or tick_volume")
    if "volume" not in frame.columns and "tick_volume" in frame.columns:
        frame = frame.rename(columns={"tick_volume": "volume"})
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise DatasetValidationError("missing required columns: " + ", ".join(missing))
    ordered = list(REQUIRED_COLUMNS)
    if "volume" in frame.columns:
        ordered.append("volume")
    ordered.extend(sorted(column for column in frame.columns if column not in ordered))
    return frame.loc[:, ordered].copy()


def _validate_values(frame: pd.DataFrame) -> None:
    numeric_columns = [column for column in ("open", "high", "low", "close", "volume")
                       if column in frame.columns]
    for column in numeric_columns:
        if not pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column]):
            raise DatasetValidationError("column must have a numeric type: " + column)
        if frame[column].isna().any():
            raise DatasetValidationError("column contains missing values: " + column)
        if not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise DatasetValidationError("column contains non-finite values: " + column)
    if frame["timestamp"].isna().any():
        raise DatasetValidationError("timestamp contains missing values")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise DatasetValidationError("OHLC prices must be positive")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise DatasetValidationError("high must be >= open, close, and low")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise DatasetValidationError("low must be <= open, close, and high")


def _timestamp_key(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def prepare_dataset(data: pd.DataFrame, *, symbol: str | None = None,
                    timeframe: str | None = None,
                    timezone_label: str = "broker-naive",
                    duplicate_policy: DuplicatePolicy = "reject",
                    source: str = "dataframe") -> DatasetResult:
    """Validate and deterministically canonicalize a DataFrame without MT5 access."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("data must be a pandas DataFrame")
    if duplicate_policy not in ("reject", "first", "last"):
        raise ValueError("duplicate_policy must be reject, first, or last")
    if not isinstance(timezone_label, str) or not timezone_label:
        raise ValueError("timezone_label must be a non-empty label; no conversion is performed")
    if data.empty:
        raise DatasetValidationError("dataset is empty")
    frame = _canonical_columns(_normalise_timestamp(data.copy()))
    _validate_values(frame)
    frame = frame.sort_values("timestamp", kind="mergesort")
    duplicate_mask = frame["timestamp"].duplicated(keep=False)
    if duplicate_mask.any():
        if duplicate_policy == "reject":
            raise DuplicateTimestampError("duplicate timestamps are not allowed")
        frame = frame.drop_duplicates("timestamp", keep=duplicate_policy)
    frame = frame.reset_index(drop=True)
    if len(frame) > 1 and not frame["timestamp"].is_monotonic_increasing:
        raise DatasetValidationError("output chronology is not increasing")
    volume_type = "tick_volume" if "tick_volume" in data.columns and "volume" not in data.columns else "volume"
    policy = {"sort": "timestamp ascending, stable mergesort", "duplicates": duplicate_policy,
              "invalid_values": "reject", "missing_values": "reject", "ohlc_fill": "never"}
    metadata = {"symbol": symbol, "timeframe": timeframe,
                "start": _timestamp_key(frame["timestamp"].iloc[0]),
                "end": _timestamp_key(frame["timestamp"].iloc[-1]),
                "row_count": int(len(frame)), "source": source, "timezone": timezone_label,
                "version": CANONICAL_VERSION,
                "volume_type": volume_type if "volume" in frame.columns else None,
                "creation_policy": policy}
    rows = [[_timestamp_key(value) if column == "timestamp" else value
             for column, value in row.items()] for row in frame.to_dict(orient="records")]
    hash_payload = {"metadata": metadata, "columns": list(frame.columns), "rows": rows}
    encoded = json.dumps(hash_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return DatasetResult(frame=frame, metadata=metadata,
                         dataset_hash=hashlib.sha256(encoded).hexdigest())


def load_csv(path: str | Path, **kwargs: Any) -> DatasetResult:
    """Load a CSV through pandas, then apply the exact DataFrame pipeline."""
    csv_path = Path(path)
    if not csv_path.is_file():
        raise FileNotFoundError(csv_path)
    result = prepare_dataset(pd.read_csv(csv_path), source=str(csv_path), **kwargs)
    return result


def passthrough_features_target(features: Any, target: Any = None) -> tuple[Any, Any]:
    """Return copies only; no feature engineering, split, or target shifting occurs."""
    if target is not None and hasattr(features, "__len__") and hasattr(target, "__len__"):
        if len(features) != len(target):
            raise LeakageError("features and target lengths differ; refusing implicit alignment")
    feature_copy = features.copy() if hasattr(features, "copy") else features
    target_copy = target.copy() if hasattr(target, "copy") else target
    return feature_copy, target_copy