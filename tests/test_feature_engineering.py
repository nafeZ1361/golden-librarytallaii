import ast
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import dataset_pipeline
import feature_engineering as features


def bars(count=40, volume=None):
    timestamp = pd.date_range("2026-01-01", periods=count, freq="min")
    close = np.linspace(100.0, 110.0, count)
    return pd.DataFrame({
        "timestamp": timestamp, "open": close - 0.2, "high": close + 0.5,
        "low": close - 0.5, "close": close,
        "tick_volume": np.ones(count) if volume is None else volume,
    })


class FeatureEngineeringTests(unittest.TestCase):
    def test_timestamp_and_chronology_are_preserved(self):
        source = bars().iloc[::-1].reset_index(drop=True)
        result = features.build_features(source)
        self.assertTrue(result.frame.timestamp.is_monotonic_increasing)
        self.assertEqual(result.frame.timestamp.iloc[0], source.timestamp.min() + pd.Timedelta(minutes=14))

    def test_expected_columns_and_metadata(self):
        result = features.build_features(bars())
        expected = {"timestamp", "open", "high", "low", "close", "volume",
                    "return_1", "return_3", "return_5", "return_10", "log_return_1",
                    "rolling_std_10", "true_range", "atr_14", "sma_10", "ema_10",
                    "rsi_14", "roc_10", "momentum_10", "range", "body", "upper_wick",
                    "lower_wick", "body_range_ratio", "close_position", "volume_change_1",
                    "volume_mean_10", "relative_volume_10"}
        self.assertTrue(expected.issubset(result.frame.columns))
        self.assertEqual(result.metadata["feature_version"], "phase3-v1")
        self.assertEqual(result.metadata["volume_type"], "tick_volume")
        self.assertEqual(result.metadata["dataset_version"], "phase2-v1")

    def test_dataset_result_input(self):
        prepared = dataset_pipeline.prepare_dataset(bars())
        result = features.build_features(prepared)
        self.assertEqual(result.metadata["dataset_version"], prepared.metadata["version"])

    def test_repeated_output_and_hash_are_deterministic(self):
        left = features.build_features(bars())
        right = features.build_features(bars())
        self.assertTrue(left.frame.equals(right.frame))
        self.assertEqual(left.feature_hash, right.feature_hash)

    def test_input_is_not_mutated(self):
        source = bars()
        before = source.copy(deep=True)
        features.build_features(source)
        pd.testing.assert_frame_equal(source, before)

    def test_warmup_policy_is_explicit_and_deterministic(self):
        kept = features.build_features(bars(), drop_warmup=False)
        dropped = features.build_features(bars(), drop_warmup=True)
        self.assertEqual(kept.metadata["input_row_count"], kept.metadata["output_row_count"])
        self.assertLess(dropped.metadata["output_row_count"], dropped.metadata["input_row_count"])
        self.assertEqual(len(dropped.frame), 26)
        self.assertEqual(dropped.metadata["output_row_count"], len(dropped.frame))

    def test_short_history_returns_explicit_empty_output(self):
        result = features.build_features(bars(5))
        self.assertTrue(result.frame.empty)
        self.assertEqual(result.metadata["output_row_count"], 0)

    def test_short_history_retains_nan_when_warmup_not_dropped(self):
        result = features.build_features(bars(5), drop_warmup=False)
        self.assertTrue(result.frame["atr_14"].isna().all())

    def test_nan_and_infinity_are_not_created(self):
        result = features.build_features(bars(), drop_warmup=False)
        numeric = result.frame.select_dtypes(include=[np.number])
        self.assertFalse(np.isinf(numeric.to_numpy(dtype=float)).any())

    def test_duplicate_timestamp_is_rejected(self):
        with self.assertRaises(dataset_pipeline.DuplicateTimestampError):
            features.build_features(pd.concat([bars(), bars().iloc[[0]]], ignore_index=True))

    def test_constant_price_is_finite(self):
        source = bars().assign(open=100.0, high=100.0, low=100.0, close=100.0)
        result = features.build_features(source, drop_warmup=False)
        self.assertFalse(np.isinf(result.frame.select_dtypes(include=[np.number])).any().any())

    def test_zero_range_is_nan_and_removed_by_default(self):
        source = bars().assign(open=100.0, high=100.0, low=100.0, close=100.0)
        kept = features.build_features(source, drop_warmup=False)
        self.assertTrue(kept.frame["close_position"].isna().all())
        self.assertTrue(features.build_features(source).frame.empty)

    def test_zero_volume_relative_feature_is_nan(self):
        result = features.build_features(bars(volume=np.zeros(40)), drop_warmup=False)
        self.assertTrue(result.frame["relative_volume_10"].isna().all())

    def test_constant_volume_has_zero_change_and_unit_relative_volume(self):
        result = features.build_features(bars(volume=np.full(40, 7.0)))
        self.assertTrue((result.frame["volume_change_1"] == 0).all())
        self.assertTrue(np.allclose(result.frame["relative_volume_10"], 1.0))

    def test_volume_metadata_never_calls_it_exchange_volume(self):
        result = features.build_features(bars())
        self.assertEqual(result.metadata["volume_type"], "tick_volume")
        self.assertNotEqual(result.metadata["volume_type"], "exchange_volume")

    def test_no_future_data_access(self):
        source = bars()
        baseline = features.build_features(source, drop_warmup=False).frame
        changed = source.copy()
        changed.loc[30:, "close"] += 1000
        changed.loc[30:, "high"] += 1000
        altered = features.build_features(changed, drop_warmup=False).frame
        pd.testing.assert_series_equal(baseline.loc[:29, "return_1"], altered.loc[:29, "return_1"])
        pd.testing.assert_series_equal(baseline.loc[:29, "atr_14"], altered.loc[:29, "atr_14"])

    def test_ast_has_no_forbidden_future_or_label_patterns(self):
        source = Path("feature_engineering.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertFalse(any(isinstance(node, ast.Constant) and node.value == -1 for node in ast.walk(tree)))
        self.assertNotIn("shift(-1)", source)
        self.assertNotIn("target", source.lower())

    def test_import_smoke_does_not_load_mt5(self):
        command = [sys.executable, "-c", "import feature_engineering; print(sorted(__import__('sys').modules))"]
        modules = subprocess.check_output(command, text=True)
        self.assertNotIn("metatrader5", modules.lower())

    def test_numeric_dtypes_and_timestamp_output(self):
        result = features.build_features(bars())
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.frame["timestamp"]))
        self.assertTrue(all(pd.api.types.is_numeric_dtype(result.frame[name])
                            for name in result.metadata["feature_names"]))

    def test_feature_engineer_facade(self):
        result = features.FeatureEngineer(drop_warmup=True).fit_transform(bars())
        self.assertEqual(result.metadata["feature_version"], features.FEATURE_VERSION)


if __name__ == "__main__":
    unittest.main()