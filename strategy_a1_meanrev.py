# strategy_a1_meanrev.py
# A1 — MEAN-REVERSION (user-specified architecture: RSI extreme + Bollinger re-entry)
#
# signal_fn(wdf, tf_name) -> per-bar state list: 'buy' | 'sell' | 'hold'
#
# Entry events (documented, no parameters tuned on OOS):
#   LONG  event at bar i when  RSI14 crosses DOWN through 30  AND  close[i] <= BB_lower(20,2)
#         -> prediction: price mean-reverts UP over the next horizon bars.
#   SHORT event at bar i when  RSI14 crosses UP through 70    AND  close[i] >= BB_upper(20,2)
#         -> prediction: price mean-reverts DOWN.
#   'hold' on all other bars. Only the cross bar fires (fresh extreme).
#
# Computed purely on the supplied window df (plain candles). No MT5 access.

import pandas as pd
import pandas_ta


def signal_fn(wdf, tf_name=None):
    n = len(wdf)
    if n < 30:
        return ["hold"] * n
    close = wdf["close"]
    rsi = pandas_ta.rsi(close, length=14)
    bb = pandas_ta.bbands(close, length=20, std=2)
    bb_cols = [str(c).upper() for c in bb.columns]
    lo_col = bb.columns[[c.startswith("BBL") for c in bb_cols].index(True)]
    up_col = bb.columns[[c.startswith("BBU") for c in bb_cols].index(True)]
    lower, upper = bb[lo_col].tolist(), bb[up_col].tolist()
    r = rsi.tolist(); lo = lower; up = upper
    c = close.tolist()

    states = ["hold"] * n
    for i in range(1, n):
        # NaN-aware warm-up guard: float('nan') (pandas tolist) is not None,
        # so the former `is None` checks never fired (CP5 F1, behavior-preserving).
        if pd.isna(r[i]) or pd.isna(lo[i]) or pd.isna(up[i]) or pd.isna(r[i - 1]):
            continue
        if r[i] < 30 and r[i - 1] >= 30 and c[i] <= lo[i]:
            states[i] = "buy"
        elif r[i] > 70 and r[i - 1] <= 70 and c[i] >= up[i]:
            states[i] = "sell"
    return states
