# strategy_a2_breakout.py
# A2 — BREAKOUT WITH VOLUME CONFIRMATION (user-specified: session-range breakout + tick-volume filter)
#
# signal_fn(wdf, tf_name) -> per-bar state list: 'buy' | 'sell' | 'hold'
#
# Entry events (documented):
#   Opening Range (OR) = the first 120 minutes of each TRADING DAY (bars grouped by
#   the naive broker date): M3 -> 40 bars, M15 -> 8 bars, H1 -> 2 bars.
#   LONG  event at bar i (after OR closes, same day) when  close[i] > OR_high  AND
#         tick_volume[i] >= 1.5 x mean(OR bar volumes)   -> prediction: breakout continues UP.
#   SHORT event mirrored below the OR low with the same volume filter.
#   State resets to 'hold' when the condition stops holding (run-based events).
#   The OR/weekend boundaries come from the supplied df only. No MT5 access.

OR_MINUTES = 120
VOL_MULT = 1.5
OR_BARS = {"3m": 40, "15m": 8, "1h": 2}


def signal_fn(wdf, tf_name=None):
    n = len(wdf)
    states = ["hold"] * n
    if n == 0:
        return states
    or_bars = OR_BARS.get(tf_name or "3m", 40)
    times = wdf["time"]
    if hasattr(times.iloc[0], "date"):
        days = times.dt.date
    else:
        days = times
    day_values = days.tolist()
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
        or_end = min(i + or_bars, day_end)
        if or_end - i >= max(2, int(or_bars * 0.6)):
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
