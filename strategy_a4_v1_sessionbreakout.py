# strategy_a4_v1_sessionbreakout.py
# A4-v1 — SESSION-CONDITIONED FIRST-BREAKOUT (Cycle-R1 variant #5; contract:
# project_audit/CYCLE_R1_CONTRACT.md, registered BEFORE any evaluation).
#
# IDENTICAL to A2-v2 (strategy_a2_v2_firstbreakout.py) in OR eligibility,
# parameters (OR 120 min / 40 M3 bars, VOL_MULT 1.5, session break 30 min) and
# the first-breakout-only event rule. The ONLY addition (registered, 2 params):
# the event bar's BROKER-hour must fall inside [SESSION_START, SESSION_END)
# = [12, 20) — the London/NY overlap approximated in broker(UTC) time. Events
# outside that window are suppressed for the whole day (no later re-entry).
#
# Rationale: restricts the traded population to the high-liquidity overlap
# regime; a structural change, not a performance tweak.
# signal_fn(wdf, tf_name) -> 'buy'|'sell'|'hold'; pure; no MT5 access.

import pandas as pd

OR_MINUTES = 120
VOL_MULT = 1.5
OR_BARS = {"3m": 40, "15m": 8, "1h": 2}
TF_MINUTES = {"3m": 3, "15m": 15, "1h": 60}
SESSION_BREAK_MIN = 30
SESSION_START_HOUR = 12
SESSION_END_HOUR = 20


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
    hours = t.dt.hour.tolist()
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
        day_end = j
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
                if not (SESSION_START_HOUR <= hours[k] < SESSION_END_HOUR):
                    continue  # event suppressed outside the overlap window
                if vol[k] >= VOL_MULT * avg_or_vol:
                    if close[k] > or_high:
                        states[k] = "buy"
                        break
                    elif close[k] < or_low:
                        states[k] = "sell"
                        break
        i = day_end
    return states
