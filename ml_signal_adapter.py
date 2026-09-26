"""Leakage-safe adapter from binary model probabilities to LONG/SHORT/FLAT signals."""
from __future__ import annotations

from typing import Any
import numpy as np

LONG, SHORT, FLAT = 1, -1, 0


def signal_from_positive_probability(probability: float, *, threshold: float = 0.55) -> int:
    """Map P(class=1) to LONG/SHORT/FLAT without using future information."""
    if not 0.5 < threshold < 1.0:
        raise ValueError("threshold must be > 0.5 and < 1.0")
    p = float(probability)
    if not np.isfinite(p) or not 0.0 <= p <= 1.0:
        raise ValueError("probability must be finite and within [0, 1]")
    if p >= threshold:
        return LONG
    if p <= (1.0 - threshold) + 1e-12:
        return SHORT
    return FLAT


def positive_class_probability(model: Any, X: Any) -> np.ndarray:
    """Return P(class=1) for a binary classifier with an explicit class contract."""
    if not hasattr(model, "predict_proba"):
        raise TypeError("model must expose predict_proba for probability-based signals")
    probabilities = np.asarray(model.predict_proba(X), dtype=float)
    classes = np.asarray(getattr(model, "classes_", []))
    if probabilities.ndim != 2 or probabilities.shape[1] != 2:
        raise ValueError("binary predict_proba output with exactly two classes is required")
    if classes.size != 2 or 1 not in classes:
        raise ValueError("model must expose binary classes_ containing positive class 1")
    positive_index = int(np.flatnonzero(classes == 1)[0])
    return probabilities[:, positive_index]


def probabilities_to_signals(probabilities: Any, *, threshold: float = 0.55) -> list[int]:
    return [signal_from_positive_probability(value, threshold=threshold) for value in np.asarray(probabilities).reshape(-1)]
