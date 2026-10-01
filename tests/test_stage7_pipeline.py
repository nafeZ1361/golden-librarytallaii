"""Focused Stage 7 tests: contract, parity with Phase-6 components, leakage, determinism.

These tests never touch the network and use small synthetic frames for unit checks;
real-dataset tests are skipped automatically if the acquired dataset is absent.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import feature_engineering
import target_generation
from stage7.config import Stage7Config
from stage7.pipeline import (
    FEATURE_NAMES,
    Stage7Error,
    build_feature_matrix,
    build_target,
    compute_split_positions,
    load_dataset_streaming,
    run_pipeline,
    sha256_file,
)

REAL_CSV = Path("stage7_data/raw/XAUUSD_m1_ftmo.csv")
REAL_SHA = "a7d856d8eacde8c2828abadd61d1fe7f977cbbf2c00269921a5798c18e886414"


def synthetic_frame(rows: int = 400, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 3000.0 + np.cumsum(rng.normal(0, 1.0, rows))
    high = close + rng.uniform(0.1, 1.5, rows)
    low = close - rng.uniform(0.1, 1.5, rows)
    open_ = low + (high - low) * rng.uniform(0, 1, rows)
    volume = rng.integers(1, 200, rows).astype(float)
    timestamps = pd.date_range("2025-01-01", periods=rows, freq="min")
    return pd.DataFrame({"timestamp": timestamps, "open": open_, "high": high,
                         "low": low, "close": close, "volume": volume})


# ------------------------------------------------------------------ contract
def test_feature_contract_is_26_phase6_names():
    assert len(FEATURE_NAMES) == 26
    assert FEATURE_NAMES == list(feature_engineering._FEATURE_NAMES)


def test_config_defaults_match_stage7_contract():
    config = Stage7Config()
    assert (config.horizon, config.target_name, config.purge, config.embargo,
            config.decision_lag, config.feature_count) == (5, "label_5", 5, 60, 1, 26)
    assert config.dataset_sha256 == REAL_SHA


# --------------------------------------------------------------------- parity
def test_features_exact_parity_with_phase6_on_synthetic():
    frame = synthetic_frame()
    mine = build_feature_matrix(frame)
    theirs = feature_engineering.build_features(frame, drop_warmup=False).frame[FEATURE_NAMES]
    np.testing.assert_allclose(mine.to_numpy(float), theirs.to_numpy(float),
                               rtol=0, atol=1e-12, equal_nan=True)


def test_target_exact_parity_with_phase4_on_synthetic():
    frame = synthetic_frame()
    reference = target_generation.build_targets(frame.copy(), horizons=[5], threshold=0.0)
    mine = build_target(frame["close"].astype(float), 5)
    np.testing.assert_array_equal(reference.frame["label_5"].to_numpy(), mine.to_numpy())


@pytest.mark.skipif(not REAL_CSV.is_file(), reason="real dataset not present")
def test_feature_parity_on_real_dataset_segments():
    frame, _ = load_dataset_streaming(REAL_CSV, 20_000, expected_rows=480_087)
    segment = frame.iloc[100_000:130_000].reset_index(drop=True)
    mine = build_feature_matrix(segment).to_numpy(float)
    theirs = feature_engineering.build_features(segment, drop_warmup=False).frame[
        FEATURE_NAMES].to_numpy(float)
    a = np.nan_to_num(mine, nan=-9e99)
    b = np.nan_to_num(theirs, nan=-9e99)
    assert np.array_equal(a, b)
    label_ref = target_generation.build_targets(segment.copy(), horizons=[5]).frame
    label_mine = build_target(segment["close"].astype(float), 5)
    keep = slice(0, len(segment) - 5)
    assert np.array_equal(label_ref["label_5"].to_numpy()[keep], label_mine.to_numpy()[keep])


# --------------------------------------------------------------- streaming IO
@pytest.mark.skipif(not REAL_CSV.is_file(), reason="real dataset not present")
def test_streaming_loader_matches_direct_read_and_validates():
    frame, stats = load_dataset_streaming(REAL_CSV, 20_000, expected_rows=480_087)
    direct = pd.read_csv(REAL_CSV, parse_dates=["datetime"]).rename(columns={"datetime": "timestamp"})
    assert len(frame) == len(direct) == 480_087
    assert (frame["timestamp"].to_numpy() == direct["timestamp"].to_numpy()).all()
    for column in ("open", "high", "low", "close", "volume"):
        np.testing.assert_array_equal(frame[column].to_numpy(), direct[column].to_numpy())
    assert stats["chunks"] == 25  # ceil(480087/20000)


def test_streaming_loader_rejects_wrong_row_count(tmp_path):
    frame = synthetic_frame(50)
    csv = tmp_path / "bars.csv"
    out = frame.rename(columns={"timestamp": "datetime"})
    out.to_csv(csv, index=False)
    with pytest.raises(Stage7Error):
        load_dataset_streaming(csv, 20, expected_rows=999)


def test_streaming_loader_rejects_non_increasing_timestamps(tmp_path):
    frame = synthetic_frame(60)
    frame.loc[30, "timestamp"] = frame.loc[0, "timestamp"]  # duplicate/out-of-order
    csv = tmp_path / "bars.csv"
    frame.rename(columns={"timestamp": "datetime"}).to_csv(csv, index=False)
    with pytest.raises(Stage7Error):
        load_dataset_streaming(csv, 20)


def test_validate_chunk_rejects_bad_ohlc():
    frame = synthetic_frame(30)
    frame.loc[5, "high"] = frame.loc[5, "low"] - 10.0
    with pytest.raises(Stage7Error):
        from stage7.pipeline import validate_chunk
        validate_chunk(frame)


# ----------------------------------------------------------------------- split
def test_split_positions_respect_purge_embargo_gaps():
    config = Stage7Config()
    positions = compute_split_positions(1000, config)
    assert positions["train_end"] == 700
    assert positions["purge_end"] - positions["purge_start"] == config.purge
    assert positions["embargo_end"] - positions["purge_end"] == config.embargo
    assert positions["holdout_start"] == positions["embargo_end"]
    assert positions["holdout_end"] == 1000


def test_split_positions_rejects_tiny_dataset():
    config = Stage7Config()
    with pytest.raises(Stage7Error):
        compute_split_positions(100, config)


# --------------------------------------------------------------------- e2e mini
def _mini_run(tmp_path: Path, run_id: str) -> dict:
    frame = synthetic_frame(3000, seed=11)
    csv = tmp_path / f"{run_id}.csv"
    frame.rename(columns={"timestamp": "datetime"}).to_csv(csv, index=False)
    config = Stage7Config(
        dataset_path=str(csv), dataset_sha256=sha256_file(csv), expected_rows=len(frame),
        chunk_rows=1000, initial_equity=10_000.0,
    )
    # Patch module-level timestamp constants check by monkeypatching via config path only;
    # run_pipeline validates first/last timestamps against stage7.config values, so we
    # instead call the internal steps for the mini test.
    return config, frame


def test_mini_pipeline_leakage_and_determinism(tmp_path, monkeypatch):
    """Full run_pipeline on a mini dataset with patched manifest bounds."""
    import stage7.config as cfg

    frame = synthetic_frame(3000, seed=11)
    csv = tmp_path / "mini.csv"
    frame.rename(columns={"timestamp": "datetime"}).to_csv(csv, index=False)
    monkeypatch.setattr(cfg, "DATASET_FIRST_TIMESTAMP", str(frame["timestamp"].iloc[0]))
    monkeypatch.setattr(cfg, "DATASET_LAST_TIMESTAMP", str(frame["timestamp"].iloc[-1]))
    config = Stage7Config(dataset_path=str(csv), dataset_sha256=sha256_file(csv),
                          expected_rows=len(frame), chunk_rows=1000)
    dir_a = tmp_path / "evidence_a"
    dir_b = tmp_path / "evidence_b"
    summary_a = run_pipeline(config, dir_a, "a")
    summary_b = run_pipeline(config, dir_b, "b")
    assert summary_a["status"] == "success"
    # determinism: identical artifact hashes across runs (run_id differs only in id fields)
    for name, digest in summary_a["artifact_hashes"].items():
        if name in {"performance_metrics.json"}:
            continue  # contains run_id field
        assert summary_b["artifact_hashes"][name] == digest, name
    # predictions/signals/trades/equity files exist and are non-empty
    for name in ("predictions.csv", "signals.csv", "trades.csv", "equity_curve.csv",
                 "dataset_manifest.json", "split_manifest.json", "feature_manifest.json",
                 "performance_metrics.json", "run_manifest.json"):
        assert (dir_a / name).stat().st_size > 0, name
    # leakage: purge+embargo gap strictly separates train end from holdout start
    split = json.loads((dir_a / "split_manifest.json").read_text())
    positions = split["positions"]
    assert positions["holdout_start"] - positions["train_end"] >= config.purge + config.embargo
    assert split["leakage_guarantees"]["train_label_horizon_clears_holdout"] is True
    # predictions align 1:1 with signals
    preds = pd.read_csv(dir_a / "predictions.csv")
    sigs = pd.read_csv(dir_a / "signals.csv")
    assert len(preds) == len(sigs) == split["positions"]["holdout_end"] - split["positions"]["holdout_start"]
    assert (preds["prediction"].to_numpy() == sigs["signal"].to_numpy()).all()
    # labels match independent recomputation from raw closes
    future = frame["close"].shift(-5).to_numpy()
    expected_label = np.where(np.isnan(future), np.nan, (future > frame["close"].to_numpy()).astype(float))
    holdout_positions = usable_positions(preds["index"].to_numpy(), frame)
    np.testing.assert_array_equal(preds["label"].to_numpy(), expected_label[holdout_positions])


def usable_positions(indices, frame):
    return indices  # indices already refer to raw frame rows


# ------------------------------------------------------------------- real E2E
@pytest.mark.skipif(not REAL_CSV.is_file(), reason="real dataset not present")
def test_real_dataset_sha_is_locked():
    assert sha256_file(REAL_CSV) == REAL_SHA
