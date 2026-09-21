import importlib
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

pipeline = importlib.import_module("dataset_pipeline")


def bars():
    return pd.DataFrame({"time": ["2026-01-01 00:03", "2026-01-01 00:00", "2026-01-01 00:06"],
                         "open": [101.0, 100.0, 102.0], "high": [102.0, 101.0, 103.0],
                         "low": [100.0, 99.0, 101.0], "close": [101.5, 100.5, 102.5],
                         "tick_volume": [2, 1, 3]})


class DatasetPipelineTests(unittest.TestCase):
    def test_canonical_sort_tick_volume_and_metadata(self):
        result = pipeline.prepare_dataset(bars(), symbol="XAUUSD.", timeframe="3m")
        self.assertEqual(list(result.frame["timestamp"].astype(str)), ["2026-01-01 00:00:00",
                         "2026-01-01 00:03:00", "2026-01-01 00:06:00"])
        self.assertEqual(result.metadata["volume_type"], "tick_volume")
        self.assertEqual(result.metadata["timezone"], "broker-naive")

    def test_invalid_inputs_are_explicitly_rejected(self):
        invalid = [pd.DataFrame(), bars().drop(columns="close"), bars().assign(close=np.nan),
                   bars().assign(high=np.inf), bars().assign(low=0), bars().assign(high=99.0)]
        for bad in invalid:
            with self.assertRaises(pipeline.DatasetPipelineError):
                pipeline.prepare_dataset(bad)

    def test_invalid_datetime_and_types_are_rejected(self):
        with self.assertRaises(pipeline.DatasetValidationError):
            pipeline.prepare_dataset(bars().assign(time=["bad", "2026-01-01", "2026-01-02"]))
        with self.assertRaises(pipeline.DatasetValidationError):
            pipeline.prepare_dataset(bars().assign(open=["101", "100", "102"]))
        with self.assertRaises(pipeline.DatasetValidationError):
            pipeline.prepare_dataset(bars().drop(columns="time"))

    def test_nullable_numeric_missing_values_are_dataset_validation_errors(self):
        for column, dtype in (("open", "Float64"), ("tick_volume", "Int64")):
            with self.subTest(column=column):
                nullable = bars().astype({column: dtype})
                nullable.loc[0, column] = pd.NA
                with self.assertRaises(pipeline.DatasetValidationError):
                    pipeline.prepare_dataset(nullable)

    def test_volume_and_tick_volume_are_mutually_exclusive(self):
        with self.assertRaises(pipeline.DatasetValidationError):
            pipeline.prepare_dataset(bars().assign(volume=[2, 1, 3]))

    def test_csv_loader_uses_the_same_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            bars().to_csv(path, index=False)
            result = pipeline.load_csv(path, symbol="XAUUSD.", timeframe="3m")
        self.assertEqual(result.metadata["source"], str(path))
        self.assertEqual(result.metadata["row_count"], 3)

    def test_duplicate_policy_is_explicit(self):
        duplicate = pd.concat([bars(), bars().iloc[[0]]], ignore_index=True)
        with self.assertRaises(pipeline.DuplicateTimestampError):
            pipeline.prepare_dataset(duplicate)
        first = pipeline.prepare_dataset(duplicate, duplicate_policy="first")
        last = pipeline.prepare_dataset(duplicate, duplicate_policy="last")
        self.assertEqual(len(first.frame), len(last.frame))
        self.assertEqual(len(first.frame), 3)
        self.assertEqual(first.metadata["creation_policy"]["duplicates"], "first")

    def test_deterministic_output_hash_and_no_timezone_conversion(self):
        one = pipeline.prepare_dataset(bars(), timezone_label="America/New_York")
        two = pipeline.prepare_dataset(bars(), timezone_label="America/New_York")
        self.assertEqual(one.dataset_hash, two.dataset_hash)
        self.assertTrue(one.frame.equals(two.frame))
        self.assertEqual(one.metadata["start"], "2026-01-01T00:00:00")

    def test_passthrough_does_not_shift_target_and_guards_length(self):
        features = pd.DataFrame({"x": [1, 2, 3]})
        target = pd.Series([10, 20, 30])
        copied_features, copied_target = pipeline.passthrough_features_target(features, target)
        self.assertTrue(copied_features.equals(features) and copied_target.equals(target))
        with self.assertRaises(pipeline.LeakageError):
            pipeline.passthrough_features_target(features, target.iloc[:2])


if __name__ == "__main__":
    unittest.main()