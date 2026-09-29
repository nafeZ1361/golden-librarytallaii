"""Stage 7.1 real-data ML replay harness.

Research/backtest/paper only. No MetaTrader 5 or live execution.
"""
from __future__ import annotations

import argparse, hashlib, json, pickle, sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

import dataset_pipeline
import feature_engineering
import target_generation
import model_training
from ml_backtest_adapter import build_backtest_signals
from module.backtest import HistoricalReplay, ReplaySignal
from module.market_data import Candle
from module.paper import PaperBroker


DATASET_REL = Path("بک تست") / "XAUUSD._M1_202501140101_202609091933.csv"
EXPECTED_SHA256 = "92a84f92ab4e06625a2d977f5acaeecb6d553ffd1c110b2ed9f1571c541a562a"
EXPECTED_ROWS = 586534
EXPECTED_START = "2025-01-14 01:01:00"
EXPECTED_END = "2026-09-09 19:33:00"
HORIZON = 5
THRESHOLD = 0.0
SIGNAL_THRESHOLD = 0.55
FEATURES = list(feature_engineering._FEATURE_NAMES)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_dataset(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    prepared = dataset_pipeline.prepare_dataset(raw)
    frame = prepared.frame.copy()
    if "volume" not in frame.columns and "tick_volume" in raw.columns:
        frame["volume"] = pd.to_numeric(raw["tick_volume"], errors="raise").to_numpy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="raise")
    if frame["timestamp"].duplicated().any() or not frame["timestamp"].is_monotonic_increasing:
        raise ValueError("Dataset A chronology/duplicate check failed")
    return frame


def source_provenance(root: Path) -> dict[str, str]:
    paths = [
        "tools/stage71_ml_backtest.py", "dataset_pipeline.py", "feature_engineering.py",
        "target_generation.py", "model_training.py", "ml_signal_adapter.py",
        "ml_backtest_adapter.py", "module/backtest.py", "module/paper.py",
        "module/performance.py",
    ]
    return {p: sha256_file(root / p) for p in paths}


def make_candles(frame: pd.DataFrame, symbol: str = "XAUUSD") -> list[Candle]:
    return [
        Candle(str(r.timestamp), symbol, float(r.open), float(r.high), float(r.low),
               float(r.close), float(getattr(r, "volume", 0.0)))
        for r in frame.itertuples(index=False)
    ]


def run(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    dataset_path = (root / args.dataset).resolve()
    evidence = (root / args.evidence).resolve()
    evidence.mkdir(parents=True, exist_ok=True)

    dataset_sha = sha256_file(dataset_path)
    if dataset_sha != EXPECTED_SHA256:
        raise ValueError(f"Dataset SHA mismatch: expected {EXPECTED_SHA256}, got {dataset_sha}")

    frame = load_dataset(dataset_path)
    if len(frame) != EXPECTED_ROWS:
        raise ValueError(f"Dataset row mismatch: expected {EXPECTED_ROWS}, got {len(frame)}")
    if str(frame["timestamp"].iloc[0]) != EXPECTED_START or str(frame["timestamp"].iloc[-1]) != EXPECTED_END:
        raise ValueError("Dataset timestamp boundary mismatch")

    targets = target_generation.build_targets(frame, horizons=[HORIZON], threshold=THRESHOLD).frame
    features = feature_engineering.build_features(frame, drop_warmup=True).frame
    target_cols = {"future_return_5", "label_5"}
    if target_cols.intersection(features.columns):
        raise AssertionError("Target leakage: target columns entered feature frame")
    if list(c for c in features.columns if c != "timestamp") != FEATURES:
        raise AssertionError("Feature schema/order mismatch")
    if len(FEATURES) != 26:
        raise AssertionError(f"Unexpected feature count: {len(FEATURES)}")

    holdout_start = pd.Timestamp(args.holdout_start)
    train_mask = targets["timestamp"] < holdout_start
    # Purge horizon rows whose target would look into the holdout.
    train_targets = targets.loc[train_mask].copy()
    train_targets = train_targets.iloc[:-HORIZON].copy()
    train_feature = features.merge(
        train_targets[["timestamp", "label_5"]], on="timestamp", how="inner", validate="one_to_one"
    )
    train_feature = train_feature.drop(columns=["label_5"])
    y = train_targets[["timestamp", "label_5"]].copy()
    train_feature = train_feature.sort_values("timestamp").reset_index(drop=True)
    y = y.sort_values("timestamp").reset_index(drop=True)
    if len(train_feature) != len(y):
        raise AssertionError("Training feature/target alignment failed")
    if not set(FEATURES).issubset(train_feature.columns):
        raise AssertionError("Missing required features")
    if any(c in train_feature.columns for c in target_cols):
        raise AssertionError("Target column present in training features")

    artifact_dir = evidence / "model_artifact"
    artifact_dir.mkdir(exist_ok=True)
    trained = model_training.train_baseline_model(
        train_feature[["timestamp"] + FEATURES],
        y,
        model_name="logistic_regression",
        feature_version=feature_engineering.FEATURE_VERSION,
        target_name="label_5",
        horizon=HORIZON,
        dataset_identity=dataset_sha,
        split_identity=f"holdout:{holdout_start.isoformat()}",
        artifact_dir=str(artifact_dir),
        random_seed=42,
    )
    artifact = {"model": trained.model, "scaler": pickle.load(open(trained.registry_entry["model_artifact_path"], "rb"))["scaler"],
                "feature_columns": FEATURES}

    holdout_features = features.loc[features["timestamp"] >= holdout_start].copy()
    if holdout_features.empty:
        raise ValueError("Holdout is empty")
    Xh = holdout_features[FEATURES]
    probabilities = np.asarray(artifact["model"].predict_proba(artifact["scaler"].transform(Xh)))[:, list(artifact["model"].classes_).index(1)]
    signals, adapter_meta = build_backtest_signals(frame, artifact, holdout_start=holdout_start, threshold=SIGNAL_THRESHOLD)
    holdout_positions = [i for i, ts in enumerate(frame["timestamp"]) if ts >= holdout_start]
    pred_count = len(probabilities)
    signal_count = len(holdout_positions)
    actionable = sum(signals[i] != "hold" for i in holdout_positions)

    stale_path = evidence / "paper_state.json"
    stale_path.write_text(json.dumps({"stale_marker": "STALE_STAGE71_REBUILD", "positions": {"old": "must_not_survive"}}, indent=2), encoding="utf-8")
    stale_before = sha256_file(stale_path)
    stale_path.unlink()
    broker = PaperBroker(stale_path, initial_balance=args.initial_balance)

    prob_by_ts = dict(zip(holdout_features["timestamp"].astype(str), probabilities))
    sig_by_ts = {str(frame.loc[i, "timestamp"]): signals[i] for i in holdout_positions}

    def strategy(history: list[Candle], candle: Candle):
        if not history or candle.timestamp < holdout_start.isoformat():
            return ()
        s = sig_by_ts.get(str(pd.Timestamp(candle.timestamp)))
        if s not in {"buy", "sell"}:
            return ()
        prev = history[-1]
        distance = max(abs(prev.high - prev.low), abs(prev.close - prev.open), 1e-8)
        buy = s == "buy"
        price = candle.open
        sl = price - distance if buy else price + distance
        tp = price + 2 * distance if buy else price - 2 * distance
        return (ReplaySignal(
            trade_id=f"stage71-{candle.timestamp}",
            symbol=candle.symbol, volume=args.volume,
            order_type="buy" if buy else "sell", price=price, sl=sl, tp=tp,
            comment="stage71-rebuild", magic=77071
        ),)

    replay = HistoricalReplay(broker, initial_balance=args.initial_balance)
    result = replay.run(make_candles(frame), strategy)
    for trade_id, pos in list(broker.positions.items()):
        if pos.status == "OPEN":
            broker.close(trade_id)

    closed = [float(p.profit) for p in broker.positions.values() if p.status == "CLOSED"]
    from module.performance import calculate_performance
    metrics = calculate_performance(closed, initial_balance=args.initial_balance)
    ledger = broker.reconcile()
    state = json.loads(stale_path.read_text(encoding="utf-8"))
    if "stale_marker" in state:
        raise AssertionError("Stale state marker survived into final state")

    manifest = {
        "stage": "7.1-rebuild",
        "status": "EXECUTED",
        "git_sha": args.git_sha or "unknown",
        "dataset": {"path": str(args.dataset), "sha256": dataset_sha, "rows": len(frame),
                    "first_timestamp": str(frame.timestamp.iloc[0]), "last_timestamp": str(frame.timestamp.iloc[-1])},
        "holdout": {"start": holdout_start.isoformat(), "rows": len(holdout_features), "horizon": HORIZON},
        "features": {"count": len(FEATURES), "columns": FEATURES, "leakage_targets_absent": True},
        "predictions": pred_count, "signals": signal_count, "actionable_signals": actionable,
        "decision_lag_bars": adapter_meta["decision_lag_bars"],
        "broker": ledger, "metrics": metrics,
        "stale_state": {"preexisting_hash": stale_before, "isolated": True},
        "code_provenance_sha256": source_provenance(root),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (evidence / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (evidence / "execution_log.txt").write_text(json.dumps({"dataset_sha256": dataset_sha, "predictions": pred_count, "signals": signal_count, "trades": ledger["orders"]}, indent=2) + "\n", encoding="utf-8")
    hashes = {}
    for p in sorted(evidence.rglob("*")):
        if p.is_file() and p.name != "evidence_hashes.json":
            hashes[str(p.relative_to(evidence))] = sha256_file(p)
    (evidence / "evidence_hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--dataset", default=str(DATASET_REL))
    parser.add_argument("--evidence", default="stage71_evidence")
    parser.add_argument("--holdout-start", default="2026-06-11T11:53:00")
    parser.add_argument("--initial-balance", type=float, default=5000.0)
    parser.add_argument("--volume", type=float, default=0.01)
    parser.add_argument("--git-sha", default="")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
