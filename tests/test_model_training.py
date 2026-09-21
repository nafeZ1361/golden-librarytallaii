import json
import os
import tempfile
import unittest

import numpy as np
import pandas as pd

import feature_engineering
import model_training
import target_generation
import time_series_validation


def make_dataset(count=200):
    timestamp = pd.date_range("2026-01-01", periods=count, freq="min")
    close = pd.Series(np.linspace(100.0, 120.0, count), dtype=float)
    frame = pd.DataFrame({
        "timestamp": timestamp,
        "open": close - 0.5,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "tick_volume": np.ones(count),
    })
    return frame


class ModelTrainingTests(unittest.TestCase):
    def test_training_on_chronological_data(self):
        source = make_dataset(200)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(
            source,
            train_ratio=0.7,
            validation_ratio=0.15,
            test_ratio=0.15,
            horizon=5,
            purge=0,
            embargo=0,
        )

        train_features = features.frame.iloc[split.train.index].copy()
        val_features = features.frame.iloc[split.validation.index].copy()
        test_features = features.frame.iloc[split.test.index].copy()

        train_targets = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_targets = targets.frame.iloc[split.validation.index][["label_5"]].copy()
        test_targets = targets.frame.iloc[split.test.index][["label_5"]].copy()

        result = model_training.train_baseline_model(
            train_features,
            train_targets,
            validation_features=val_features,
            validation_targets=val_targets,
            test_features=test_features,
            test_targets=test_targets,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-1",
            split_identity="split-1",
            artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
        )

        self.assertIn("model", result.metadata)
        self.assertIn("metrics", result.metadata)
        self.assertIn("registry", result.metadata)
        self.assertGreater(result.metrics["validation_accuracy"], 0.0)

    def test_preprocessing_fitted_on_train_only(self):
        source = make_dataset(240)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)

        train_f = features.frame.iloc[split.train.index].copy()
        val_f = features.frame.iloc[split.validation.index].copy()

        train_y = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_y = targets.frame.iloc[split.validation.index][["label_5"]].copy()

        result = model_training.train_baseline_model(
            train_f,
            train_y,
            validation_features=val_f,
            validation_targets=val_y,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-2",
            split_identity="split-2",
            artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
        )

        self.assertTrue(np.all(np.isfinite(result.metadata["preprocessing"]["train_mean"])))
        self.assertGreater(len(result.registry_entry["model_artifact_path"]), 0)

    def test_deterministic_reproducible_training(self):
        source = make_dataset(200)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)

        train_f = features.frame.iloc[split.train.index].copy()
        val_f = features.frame.iloc[split.validation.index].copy()
        train_y = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_y = targets.frame.iloc[split.validation.index][["label_5"]].copy()

        left = model_training.train_baseline_model(
            train_f,
            train_y,
            validation_features=val_f,
            validation_targets=val_y,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-3",
            split_identity="split-3",
            artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
        )
        right = model_training.train_baseline_model(
            train_f,
            train_y,
            validation_features=val_f,
            validation_targets=val_y,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-3",
            split_identity="split-3",
            artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
        )

        self.assertEqual(left.metadata["training_metadata"]["random_seed"], right.metadata["training_metadata"]["random_seed"])
        self.assertEqual(left.registry_entry["model_name"], right.registry_entry["model_name"])

    def test_target_alignment_and_no_contamination(self):
        source = make_dataset(180)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)

        train_f = features.frame.iloc[split.train.index].copy()
        val_f = features.frame.iloc[split.validation.index].copy()
        train_y = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_y = targets.frame.iloc[split.validation.index][["label_5"]].copy()

        result = model_training.train_baseline_model(
            train_f,
            train_y,
            validation_features=val_f,
            validation_targets=val_y,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-4",
            split_identity="split-4",
            artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
        )

        self.assertEqual(result.training_frame.shape[0], len(train_f))
        self.assertEqual(result.validation_frame.shape[0], len(val_f))
        self.assertTrue(result.metadata["training_metadata"]["split_identity"] == "split-4")

    def test_model_artifact_creation(self):
        source = make_dataset(120)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)
        train_f = features.frame.iloc[split.train.index].copy()
        val_f = features.frame.iloc[split.validation.index].copy()
        train_y = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_y = targets.frame.iloc[split.validation.index][["label_5"]].copy()

        artifact_dir = tempfile.mkdtemp(prefix="phase6_artifact_")
        result = model_training.train_baseline_model(
            train_f,
            train_y,
            validation_features=val_f,
            validation_targets=val_y,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-5",
            split_identity="split-5",
            artifact_dir=artifact_dir,
        )

        self.assertTrue(os.path.exists(result.registry_entry["model_artifact_path"]))
        self.assertTrue(os.path.isfile(result.registry_entry["model_artifact_path"]))

    def test_registry_metadata_integrity(self):
        source = make_dataset(150)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)
        train_f = features.frame.iloc[split.train.index].copy()
        val_f = features.frame.iloc[split.validation.index].copy()
        train_y = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_y = targets.frame.iloc[split.validation.index][["label_5"]].copy()

        result = model_training.train_baseline_model(
            train_f,
            train_y,
            validation_features=val_f,
            validation_targets=val_y,
            model_name="logistic_regression",
            feature_version=features.metadata["feature_version"],
            target_name="label_5",
            horizon=5,
            dataset_identity="dataset-6",
            split_identity="split-6",
            artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
        )

        self.assertEqual(result.registry_entry["target_name"], "label_5")
        self.assertEqual(result.registry_entry["feature_version"], features.metadata["feature_version"])
        self.assertEqual(result.registry_entry["horizon"], 5)

    def test_invalid_input_handling(self):
        with self.assertRaises(ValueError):
            model_training.train_baseline_model(
                pd.DataFrame(),
                pd.DataFrame(),
                model_name="logistic_regression",
                artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
            )

    def test_missing_feature_handling(self):
        source = make_dataset(120)
        features = feature_engineering.build_features(source, drop_warmup=True)
        targets = target_generation.build_targets(source, horizons=(5,), threshold=0.0)
        split = time_series_validation.split_time_series(source, train_ratio=0.7, validation_ratio=0.15, test_ratio=0.15)

        train_f = features.frame.iloc[split.train.index].copy().drop(columns=["return_1"], errors="ignore")
        val_f = features.frame.iloc[split.validation.index].copy()
        train_y = targets.frame.iloc[split.train.index][["label_5"]].copy()
        val_y = targets.frame.iloc[split.validation.index][["label_5"]].copy()

        with self.assertRaises(ValueError):
            model_training.train_baseline_model(
                train_f,
                train_y,
                validation_features=val_f,
                validation_targets=val_y,
                model_name="logistic_regression",
                feature_version=features.metadata["feature_version"],
                target_name="label_5",
                horizon=5,
                dataset_identity="dataset-7",
                split_identity="split-7",
                artifact_dir=tempfile.mkdtemp(prefix="phase6_"),
            )


if __name__ == "__main__":
    unittest.main()
