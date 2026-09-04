# strategy_a2_breakout.py
# A2 — BREAKOUT WITH VOLUME CONFIRMATION (user-specified: session-range breakout + tick-volume filter)
#
# signal_fn(wdf, tf_name) -> per-bar state list: 'buy' | 'sell' | 'hold'
#
# OR eligibility (CP5 Amendment 1, registered 2026-09-04 BEFORE any CP5 result):
#   Opening Range (OR) = the first 120 minutes of a TRADING DAY, grouped by
#   naive broker date: M3 -> 40 bars, M15 -> 8 bars, H1 -> 2 bars.
#   A day contributes signals only if ALL of the following hold:
#     (a) INTERIOR day: the day's first bar is not the window's first bar
#         (a bar-count window boundary can fall mid-session; an unverifiable
#         day start must not build a partial OR).
#     (b) TRUE session open: the previous bar belongs to the previous calendar
#         day AND a session break of >= SESSION_BREAK_MIN minutes precedes the
#         day (empirical, frozen Sep-3 fixtures: interior day-start gap is
#         ~63 min; weekend gap ~2949 min; no interior day-start below 60 min).
#     (c) COMPLETE OR: exactly OR_BARS bars present AND a gap-free span of
#         exactly (OR_BARS-1) * tf minutes (the former 60% rule is REMOVED;
#         short/holiday sessions and gap-broken ORs are skipped entirely).
#   Days failing any condition produce NO signals for the whole day.
#   The OR bars themselves never signal; events start after the OR closes.
#
#   LONG state at bar k (same day, after OR) when close[k] > OR_high AND
#        tick_volume[k] >= 1.5 x mean(OR bar volumes)  -> prediction: breakout
#        continues UP. SHORT mirrored below OR-low. Run-based states (the
#        hit-rate metric counts run-starts only). No MT5 access.
#
# Params are FIXED a priori (pre-registered): OR 120 min, VOL_MULT 1.5.

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
                    elif close[k] < or_low:
                        states[k] = "sell"
        i = day_end
    return states
