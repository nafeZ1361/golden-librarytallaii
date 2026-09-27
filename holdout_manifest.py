"""Immutable holdout contract helpers for the canonical XAUUSD M1 dataset."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
import pandas as pd

HOLDOUT_POLICY_VERSION = "final-15-percent-v1"
HOLDOUT_FRACTION = 0.15


def dataset_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_mt5_m1_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep=r"\s+", engine="python")
    rename = {"<DATE>": "date", "<TIME>": "time", "<OPEN>": "open", "<HIGH>": "high",
              "<LOW>": "low", "<CLOSE>": "close", "<TICKVOL>": "tick_volume",
              "<VOL>": "volume", "<SPREAD>": "spread"}
    frame = frame.rename(columns=rename)
    required = {"date", "time", "open", "high", "low", "close", "tick_volume"}
    if not required.issubset(frame.columns):
        raise ValueError(f"unexpected MT5 M1 schema; missing={sorted(required-set(frame.columns))}")
    frame["timestamp"] = pd.to_datetime(frame.pop("date") + " " + frame.pop("time"))
    return frame


def build_manifest(path: str | Path, *, symbol: str = "XAUUSD.", timeframe: str = "M1",
                   timezone: str = "broker-naive", feature_version: str = "phase3-v1",
                   target_version: str = "phase4-v1", validation_version: str = "phase5-v1") -> dict[str, Any]:
    frame = load_mt5_m1_csv(path).sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    n = len(frame)
    holdout_index = n - max(1, int(n * HOLDOUT_FRACTION))
    manifest = {
        "manifest_version": HOLDOUT_POLICY_VERSION,
        "immutable": True,
        "policy": {"name": "final_fraction", "fraction": HOLDOUT_FRACTION, "selection": "chronological_tail"},
        "symbol": symbol, "timeframe": timeframe, "timezone": timezone,
        "dataset_path": str(path), "dataset_sha256": dataset_sha256(path), "row_count": n,
        "dataset_start": frame["timestamp"].iloc[0].isoformat(),
        "dataset_end": frame["timestamp"].iloc[-1].isoformat(),
        "holdout_start": frame["timestamp"].iloc[holdout_index].isoformat(),
        "holdout_end": frame["timestamp"].iloc[-1].isoformat(),
        "feature_version": feature_version, "target_version": target_version,
        "validation_version": validation_version,
        "leakage_policy": "model is trained only on rows strictly before holdout_start",
    }
    return manifest


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
