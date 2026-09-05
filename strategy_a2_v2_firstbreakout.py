# strategy_a2_v2_firstbreakout.py
# A2-v2 — FIRST-BREAKOUT OPENING RANGE BREAKOUT (variant #1 of the Adaptive
# Research Loop; parent diagnosis: CP_R0_FAILURE_DIAGNOSIS.md; pre-registration:
# CP5_9_A2V2_PRE_REGISTRATION.md, registered BEFORE any v2 evaluation).
#
# ONLY structural change vs A2-v1 (strategy_a2_breakout.py, frozen at
# cp5-source-freeze-v1): the EVENT RULE. All OR-eligibility, parameters
# (OR 120 min / 40 M3 bars, VOL_MULT 1.5, session break 30 min) and the volume
# filter are IDENTICAL to v1.
#
# v1 emitted a STATE per bar of each breakout run (clustering: overlapping
# forward windows, rho1 up to 0.394). v2 emits AT MOST ONE event per eligible
# day: the FIRST bar after the OR closes where (volume filter passes) AND
# (close breaks above OR_high -> 'buy' | below OR_low -> 'sell').
#
# signal_fn(wdf, tf_name) -> per-bar state list 'buy'|'sell'|'hold'
# (single-bar events; the registered hit-rate metric counts each as one event).
# Computed purely on the supplied window df (plain candles). No MT5 access.

import pandas as pd

OR_MINUTES = 120
VOL_MULT = 1.5
OR_BARS = {"3m": 40, "15m": 8, "1h": 2}
TF_MINUTES = {"3m": 3, "15m": 15, "1h": 60}
SESSION_BREAK_MIN = 30


def signal_fn(wdf, tf_name=None):
    n = len(wdf)
    states = ["hold"] * n
    if n == 0:
        return states
    tf = tf_name or "3m"
    or_bars = OR_BARS.get(tf, 40)
    tf_min = TF_MINUTES.get(tf, 3)
    t = pd.to_datetime(wdf["time"])
    day_values = t.dt.date.tolist()
    tsec = (t.astype("int64") // 10**9).tolist()
    high = wdf["high"].tolist()
    low = wdf["low"].tolist()
    close = wdf["close"].tolist()
    vol = wdf["volume"].tolist()

    i = 0
    while i < n:
        day0 = day_values[i]
        j = i
        while j < n and day_values[j] == day0:
            j += 1
        day_end = j  # exclusive
        or_end = i + or_bars
        eligible = (
            i > 0
            and day_values[i - 1] != day0
            and (tsec[i] - tsec[i - 1]) >= SESSION_BREAK_MIN * 60
            and or_end <= day_end
            and (tsec[or_end - 1] - tsec[i]) == (or_bars - 1) * tf_min * 60
        )
        if eligible:
            or_high = max(high[i:or_end])
            or_low = min(low[i:or_end])
            or_vol = vol[i:or_end]
            avg_or_vol = sum(or_vol) / len(or_vol)
            for k in range(or_end, day_end):
                if vol[k] >= VOL_MULT * avg_or_vol:
                    if close[k] > or_high:
                        states[k] = "buy"
                        break  # v2: first bar meeting BOTH volume AND breakout
                    elif close[k] < or_low:
                        states[k] = "sell"
                        break  # (scan continues past volume-only, non-breakout bars)
        i = day_end
    return states
