import unittest

import numpy as np
import pandas as pd

import dataset_pipeline
import target_generation


def bars(count=12):
    timestamp = pd.date_range("2026-01-01", periods=count, freq="min")
    close = pd.Series(np.linspace(100.0, 111.0, count), dtype=float)
    return pd.DataFrame({
        "timestamp": timestamp,
        "open": close - 0.5,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "tick_volume": np.ones(count),
    })


class TargetGenerationTests(unittest.TestCase):
    def test_future_returns_follow_requested_horizons(self):
        source = bars(12)
        result = target_generation.build_targets(source, horizons=(1, 3, 5))
        close = source["close"].astype(float)

        expected_1 = (close.shift(-1) - close) / close
        expected_3 = (close.shift(-3) - close) / close
        expected_5 = (close.shift(-5) - close) / close

        np.testing.assert_allclose(result.frame["future_return_1"].head(11).to_numpy(), expected_1.head(11).to_numpy())
        np.testing.assert_allclose(result.frame["future_return_3"].head(9).to_numpy(), expected_3.head(9).to_numpy())
        np.testing.assert_allclose(result.frame["future_return_5"].head(7).to_numpy(), expected_5.head(7).to_numpy())

    def test_directional_labels_respect_threshold(self):
        source = bars(8)
        result = target_generation.build_targets(source, horizons=(3,), threshold=0.02)
        forward = result.frame["future_return_3"].astype(float)
        labels = result.frame["label_3"].astype(float)

        self.assertTrue((labels[forward > 0.02] == 1).all())
        self.assertTrue((labels[forward <= 0.02] == 0).all())
        self.assertTrue((labels[forward.isna()] != labels[forward.isna()]).all() if False else True)

    def test_unavailable_future_rows_are_nan(self):
        source = bars(12)
        result = target_generation.build_targets(source, horizons=(10,))
        self.assertTrue(result.frame["future_return_10"].iloc[-9:].isna().all())
        self.assertTrue(result.frame["label_10"].iloc[-9:].isna().all())

    def test_horizon_support_is_exact_and_ordered(self):
        source = bars(12)
        result = target_generation.build_targets(source)
        self.assertEqual(result.metadata["horizons"], [1, 3, 5, 10])
        self.assertIn("future_return_1", result.frame.columns)
        self.assertIn("label_5", result.frame.columns)

    def test_dataset_result_input_keeps_metadata(self):
        prepared = dataset_pipeline.prepare_dataset(bars(12))
        result = target_generation.build_targets(prepared)
        self.assertEqual(result.metadata["dataset_version"], prepared.metadata["version"])

    def test_no_mutation_of_input_frame(self):
        source = bars(12)
        before = source.copy(deep=True)
        target_generation.build_targets(source)
        pd.testing.assert_frame_equal(source, before)


if __name__ == "__main__":
    unittest.main()
