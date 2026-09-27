import unittest
import numpy as np
import pandas as pd
from ml_backtest_adapter import build_backtest_signals

class FakeScaler:
    def transform(self, X): return X.to_numpy(dtype=float)

class FakeModel:
    classes_ = np.array([0, 1])
    def predict_proba(self, X):
        p = X[:, 0]
        return np.column_stack([1-p, p])

def data(n=40):
    c=np.linspace(100,120,n)
    return pd.DataFrame({"timestamp":pd.date_range("2026-01-01",periods=n,freq="min"),"open":c,"high":c+1,"low":c-1,"close":c,"tick_volume":np.ones(n)})

class MLBacktestAdapterTests(unittest.TestCase):
    def test_signal_is_lagged_one_bar_and_holdout_only(self):
        frame=data()
        artifact={"model":FakeModel(),"scaler":FakeScaler(),"feature_columns":["return_1"]}
        signals,meta=build_backtest_signals(frame,artifact,holdout_start="2026-01-01 00:30",threshold=0.55)
        self.assertTrue(all(s=="hold" for s in signals[:31]))
        self.assertEqual(meta["decision_lag_bars"],1)
        self.assertEqual(len(signals),len(frame))

    def test_requires_chronological_data(self):
        frame=data().iloc[::-1].reset_index(drop=True)
        artifact={"model":FakeModel(),"scaler":FakeScaler(),"feature_columns":["return_1"]}
        with self.assertRaises(ValueError):
            build_backtest_signals(frame,artifact,holdout_start="2026-01-01 00:30")

if __name__=="__main__": unittest.main()
