import unittest

import numpy as np
import pandas as pd

import dataset_pipeline
import time_series_validation
from time_series_validation import TimeSeriesValidationError


def bars(count=80):
    timestamp = pd.date_range("2026-01-01", periods=count, freq="min")
    close = pd.Series(np.linspace(100.0, 180.0, count), dtype=float)
    return pd.DataFrame({
        "timestamp": timestamp,
        "open": close - 0.5,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "tick_volume": np.ones(count),
    })


class TimeSeriesValidationTests(unittest.TestCase):
    def test_chronological_no_randomization(self):
        source = bars(80)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)
        self.assertTrue(split.train["timestamp"].is_monotonic_increasing)
        self.assertTrue(split.validation["timestamp"].is_monotonic_increasing)
        self.assertTrue(split.test["timestamp"].is_monotonic_increasing)
        self.assertTrue(split.validation["timestamp"].iloc[0] > split.train["timestamp"].iloc[-1])
        self.assertTrue(split.test["timestamp"].iloc[0] > split.validation["timestamp"].iloc[-1])

    def test_no_overlap_across_sets(self):
        source = bars(80)
        split = time_series_validation.split_time_series(source)
        self.assertFalse(set(split.train.index).intersection(split.validation.index))
        self.assertFalse(set(split.validation.index).intersection(split.test.index))

    def test_horizon_aware_purge_boundary(self):
        source = bars(80)
        split = time_series_validation.split_time_series(source, train_ratio=0.75, validation_ratio=0.15, test_ratio=0.10, horizon=5, purge=3)
        self.assertLess(len(split.train), 60)
        self.assertGreater(split.validation["timestamp"].iloc[0], split.train["timestamp"].iloc[-1])
        self.assertGreater(split.test["timestamp"].iloc[0], split.validation["timestamp"].iloc[-1])

    def test_walk_forward_chronology(self):
        source = bars(100)
        folds = time_series_validation.walk_forward_validation(source, train_size=25, validation_size=10, test_size=5, horizon=3, purge=2, embargo=1, step=10)
        self.assertGreater(len(folds), 0)
        for fold in folds:
            self.assertTrue(fold.train["timestamp"].is_monotonic_increasing)
            self.assertTrue(fold.validation["timestamp"].is_monotonic_increasing)
            self.assertTrue(fold.test["timestamp"].is_monotonic_increasing)
            self.assertTrue(fold.validation["timestamp"].iloc[0] > fold.train["timestamp"].iloc[-1])
            self.assertTrue(fold.test["timestamp"].iloc[0] > fold.validation["timestamp"].iloc[-1])

    def test_deterministic_repeated_output(self):
        source = bars(80)
        left = time_series_validation.split_time_series(source)
        right = time_series_validation.split_time_series(source)
        self.assertTrue(left.train.equals(right.train))
        self.assertTrue(left.validation.equals(right.validation))
        self.assertTrue(left.test.equals(right.test))
        self.assertEqual(left.split_hash, right.split_hash)

    def test_insufficient_data_raises(self):
        source = bars(8)
        with self.assertRaises(time_series_validation.TimeSeriesValidationError):
            time_series_validation.split_time_series(source, train_size=2, validation_size=2, test_size=2, horizon=3)

    def test_invalid_parameters_raise(self):
        with self.assertRaises(TimeSeriesValidationError):
            time_series_validation.split_time_series(bars(50), train_ratio=0.0)
        with self.assertRaises(ValueError):
            time_series_validation.split_time_series(bars(50), train_size=10, train_ratio=0.5)
        with self.assertRaises(TimeSeriesValidationError):
            time_series_validation.split_time_series(bars(50), horizon=0)

    def test_dataset_result_input_is_supported(self):
        prepared = dataset_pipeline.prepare_dataset(bars(50))
        split = time_series_validation.split_time_series(prepared)
        self.assertEqual(split.metadata["validation_version"], "phase5-v1")

    def test_timestamp_preservation(self):
        source = bars(60).iloc[::-1].reset_index(drop=True)
        split = time_series_validation.split_time_series(source)
        self.assertTrue(split.train["timestamp"].is_monotonic_increasing)
        self.assertTrue(split.validation["timestamp"].is_monotonic_increasing)
        self.assertTrue(split.test["timestamp"].is_monotonic_increasing)


if __name__ == "__main__":
    unittest.main()
