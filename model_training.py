"""Phase 6 lightweight training layer for classical ML with split-safe preprocessing."""

from __future__ import annotations

import json
import os
import pickle
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

import feature_engineering
import target_generation

MODEL_VERSION = "phase6-v1"


class ModelTrainingError(ValueError):
    """Raised when training inputs or configuration are invalid."""


@dataclass(frozen=True)
class TrainingResult:
    model: Any
    training_frame: pd.DataFrame
    validation_frame: pd.DataFrame
    test_frame: pd.DataFrame
    metrics: dict[str, float]
    metadata: dict[str, Any]
    registry_entry: dict[str, Any]


def _validate_training_inputs(
    train_features: pd.DataFrame,
    train_targets: pd.DataFrame,
    validation_features: pd.DataFrame | None = None,
    validation_targets: pd.DataFrame | None = None,
    test_features: pd.DataFrame | None = None,
    test_targets: pd.DataFrame | None = None,
) -> None:
    if train_features.empty or train_targets.empty:
        raise ValueError("train_features and train_targets must be non-empty")
    if not isinstance(train_features, pd.DataFrame):
        raise ValueError("train_features must be a DataFrame")
    if not isinstance(train_targets, pd.DataFrame):
        raise ValueError("train_targets must be a DataFrame")
    if len(train_features) != len(train_targets):
        raise ValueError("train_features and train_targets lengths do not match")
    if train_targets.shape[1] == 0:
        raise ValueError("train_targets must include at least one target column")

    required_columns = {"timestamp"} if "timestamp" in train_features.columns else set()
    if required_columns and "timestamp" in train_features.columns:
        if train_features["timestamp"].duplicated().any():
            raise ValueError("duplicate timestamps in training data are not allowed")

    for name, features, targets in [
        ("validation", validation_features, validation_targets),
        ("test", test_features, test_targets),
    ]:
        if features is None and targets is None:
            continue
        if features is None or targets is None:
            raise ValueError(f"{name}_features and {name}_targets must both be provided or both be absent")
        if len(features) != len(targets):
            raise ValueError(f"{name}_features and {name}_targets lengths do not match")


class _StandardScaler:
    def __init__(self):
        self.mean_ = None
        self.std_ = None

    def fit(self, X: pd.DataFrame) -> "_StandardScaler":
        self.mean_ = X.mean(axis=0)
        self.std_ = X.std(axis=0).replace(0, 1.0)
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        if self.mean_ is None or self.std_ is None:
            raise ValueError("scaler has not been fit")
        return (X - self.mean_) / self.std_

    def fit_transform(self, X: pd.DataFrame) -> pd.DataFrame:
        return self.fit(X).transform(X)


def _prepare_feature_matrix(frame: pd.DataFrame, expected_columns: list[str] | None = None) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("frame is empty")
    if expected_columns is not None:
        missing = [col for col in expected_columns if col not in frame.columns]
        if missing:
            raise ValueError(f"missing required feature columns: {missing}")
    feature_matrix = frame.select_dtypes(include=[np.number]).copy()
    if feature_matrix.empty:
        raise ValueError("no numeric feature columns found")
    return feature_matrix


def _safe_accuracy(y_true: pd.Series, y_pred: pd.Series) -> float:
    if len(y_true) == 0:
        return 0.0
    return float((y_true.to_numpy() == y_pred.to_numpy()).mean())


def _build_model(model_name: str):
    model_name = (model_name or "").strip().lower()
    if model_name == "logistic_regression":
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=1000, random_state=42, solver="lbfgs")
    if model_name == "ridge_regression":
        from sklearn.linear_model import Ridge

        return Ridge(alpha=1.0, random_state=42)
    raise ValueError(f"unsupported model_name: {model_name}")


def _default_registry_record(
    *,
    model_name: str,
    target_name: str,
    horizon: int,
    feature_version: str,
    dataset_identity: str,
    split_identity: str,
    artifact_path: str,
    training_period: tuple[str, str],
    validation_period: tuple[str, str],
    model_status: str = "trained",
) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "target_name": target_name,
        "horizon": int(horizon),
        "feature_version": feature_version,
        "dataset_identity": dataset_identity,
        "split_identity": split_identity,
        "model_artifact_path": artifact_path,
        "training_period": {"start": training_period[0], "end": training_period[1]},
        "validation_period": {"start": validation_period[0], "end": validation_period[1]},
        "model_status": model_status,
    }


def train_baseline_model(
    train_features: pd.DataFrame,
    train_targets: pd.DataFrame,
    *,
    validation_features: pd.DataFrame | None = None,
    validation_targets: pd.DataFrame | None = None,
    test_features: pd.DataFrame | None = None,
    test_targets: pd.DataFrame | None = None,
    model_name: str = "logistic_regression",
    feature_version: str = "phase3-v1",
    target_name: str = "label_5",
    horizon: int = 5,
    dataset_identity: str = "unknown",
    split_identity: str = "unknown",
    artifact_dir: str | None = None,
    random_seed: int = 42,
) -> TrainingResult:
    """Train a small classical model with split-safe preprocessing and artifact metadata."""
    if train_features.empty or train_targets.empty:
        raise ValueError("train_features and train_targets must be non-empty")
    _validate_training_inputs(
        train_features,
        train_targets,
        validation_features=validation_features,
        validation_targets=validation_targets,
        test_features=test_features,
        test_targets=test_targets,
    )

    if target_name not in train_targets.columns:
        raise ValueError(f"target column missing from train_targets: {target_name}")

    if train_targets[target_name].nunique(dropna=True) < 2:
        from sklearn.dummy import DummyClassifier

        model = DummyClassifier(strategy="most_frequent")
    else:
        model = _build_model(model_name)
        if hasattr(model, "random_state"):
            model.random_state = random_seed

    feature_columns = [col for col in train_features.columns if col != "timestamp"]
    if not feature_columns:
        raise ValueError("no feature columns available after removing timestamp")

    expected_columns = list(getattr(feature_engineering, "_FEATURE_NAMES", ()))
    missing_required = [column for column in expected_columns if column not in train_features.columns]
    if missing_required:
        raise ValueError(f"missing required feature columns: {missing_required}")

    train_X = _prepare_feature_matrix(train_features[feature_columns], feature_columns)
    validation_X = _prepare_feature_matrix(validation_features[feature_columns], feature_columns) if validation_features is not None else None
    test_X = _prepare_feature_matrix(test_features[feature_columns], feature_columns) if test_features is not None else None

    y_train = train_targets[target_name].astype(float)
    y_val = validation_targets[target_name].astype(float) if validation_targets is not None else None
    y_test = test_targets[target_name].astype(float) if test_targets is not None else None

    scaler = _StandardScaler()
    train_X_scaled = scaler.fit_transform(train_X)
    validation_X_scaled = scaler.transform(validation_X) if validation_X is not None else None
    test_X_scaled = scaler.transform(test_X) if test_X is not None else None

    model.fit(train_X_scaled, y_train)
    train_pred = model.predict(train_X_scaled)
    validation_pred = model.predict(validation_X_scaled) if validation_X_scaled is not None else None
    test_pred = model.predict(test_X_scaled) if test_X_scaled is not None else None

    metrics = {
        "train_accuracy": _safe_accuracy(y_train, pd.Series(train_pred, index=y_train.index)),
        "validation_accuracy": _safe_accuracy(y_val, pd.Series(validation_pred, index=y_val.index)) if y_val is not None and validation_pred is not None else 0.0,
        "test_accuracy": _safe_accuracy(y_test, pd.Series(test_pred, index=y_test.index)) if y_test is not None and test_pred is not None else 0.0,
    }

    if artifact_dir is None:
        artifact_dir = tempfile.mkdtemp(prefix="phase6_model_")
    os.makedirs(artifact_dir, exist_ok=True)

    artifact_path = os.path.join(artifact_dir, f"{model_name}_{target_name}_{horizon}.pkl")
    with open(artifact_path, "wb") as file_obj:
        pickle.dump({"model": model, "scaler": scaler, "feature_columns": feature_columns}, file_obj)

    training_start = str(train_features["timestamp"].min()) if "timestamp" in train_features.columns else "unknown"
    training_end = str(train_features["timestamp"].max()) if "timestamp" in train_features.columns else "unknown"
    validation_start = str(validation_features["timestamp"].min()) if validation_features is not None and "timestamp" in validation_features.columns else "unknown"
    validation_end = str(validation_features["timestamp"].max()) if validation_features is not None and "timestamp" in validation_features.columns else "unknown"

    training_metadata = {
        "model_name": model_name,
        "model_version": MODEL_VERSION,
        "target_name": target_name,
        "horizon": int(horizon),
        "feature_version": feature_version,
        "dataset_identity": dataset_identity,
        "split_identity": split_identity,
        "preprocessing": {
            "kind": "standard_scaler",
            "train_mean": scaler.mean_.to_numpy(dtype=float),
            "train_std": scaler.std_.to_numpy(dtype=float),
        },
        "random_seed": int(random_seed),
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "python_version": __import__("sys").version.split()[0],
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
    }

    registry_entry = _default_registry_record(
        model_name=model_name,
        target_name=target_name,
        horizon=horizon,
        feature_version=feature_version,
        dataset_identity=dataset_identity,
        split_identity=split_identity,
        artifact_path=artifact_path,
        training_period=(training_start, training_end),
        validation_period=(validation_start, validation_end),
    )

    preprocessing_metadata = {
        "kind": "standard_scaler",
        "train_mean": scaler.mean_.to_numpy(dtype=float),
        "train_std": scaler.std_.to_numpy(dtype=float),
    }
    metadata = {
        "model": model_name,
        "training_metadata": training_metadata,
        "preprocessing": preprocessing_metadata,
        "metrics": metrics,
        "registry": registry_entry,
    }

    return TrainingResult(
        model=model,
        training_frame=train_features,
        validation_frame=validation_features.copy() if validation_features is not None else pd.DataFrame(),
        test_frame=test_features.copy() if test_features is not None else pd.DataFrame(),
        metrics=metrics,
        metadata=metadata,
        registry_entry=registry_entry,
    )
