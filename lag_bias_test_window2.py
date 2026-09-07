# -*- coding: utf-8 -*-
r"""
LAG BIAS TEST - WINDOW 2 (OLDER, NON-OVERLAPPING) - DRAFT - DO NOT RUN YET

Purpose: repeat the Window-1 baseline-vs-lagged(-1 bar) comparison on a
SECOND, older 30-day window that does not overlap the frozen Window-1 cache,
to check whether the +ROI/+WinRate direction found in Window 1 is consistent
or window-specific. Read-only market data fetch (new window only); no order
sent; no existing file modified; results appended to a NEW file.

Fetch: mt5.copy_rates_from_pos(symbol, M3, start_pos=14400, count=14400)
       start_pos=14400 skips exactly the 14400 candles already used as
       Window 1, landing on the 30 days immediately BEFORE it.

Side effects: 4 more HTML reports in backtest/ (2 baseline + 2 lagged calls
across this + a repeat-safety recheck), one new file
project_audit/determinism_cache/lag_bias_window2_result.md,
and cache files window2_df.csv/window2_signal.csv/window2_confirmation.csv
(new names - Window 1's cache files are untouched).

Run mode (same interpreter as before - project's Python 3.12):
    python .\lag_bias_test_window2.py
"""
import io, os, sys
from contextlib import redirect_stdout
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)
CACHE_DIR = os.path.join(SCRIPT_DIR, "project_audit", "determinism_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

for mod in ("numpy", "pandas", "plotly", "yfinance", "MetaTrader5", "ta", "pandas_ta"):
    try:
        __import__(mod)
    except ImportError:
        print("MISSING DEPENDENCY:", mod); sys.exit(2)

import MetaTrader5 as mt5
import pandas as pd
from backtest.hashem_backtest import backtest
from backtest.indicators import backtest_supertrend, backtest_trend_ali

SYMBOL, TF = 'XAUUSD.', '3m'
COUNT = 14400
START_POS = 14400  # skip Window 1's candles -> land on the prior 30 days
PARAMS = dict(backtest_days=30, use_risk_free=False, risk_free_distance_pips=50.0,
    use_sl=True, sl_pips=100.0, use_tp=True, tp_pips=200.0,
    close_opposite_position=False, initial_balance=5000.0,
    position_size_mode='risk_percent', fixed_lot_size=0.01,
    risk_percent=2, risk_based_on='initial', analyze_weekdays=True,
    analyze_time_sessions=True, session_duration_hours=4.0)

mt5.initialize()
rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, START_POS, COUNT)
if rates is None or len(rates) == 0:
    print("[error] MT5 returned no candles for start_pos=%d - aborting." % START_POS)
    sys.exit(3)
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.rename(columns={'tick_volume': 'volume'}, inplace=True)
df = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
limit = len(df)
print("[fetch] window2: %d candles (%s .. %s)" % (limit, df['time'].iloc[0], df['time'].iloc[-1]))

signal = backtest_supertrend(SYMBOL, TF, limit, atr_period=10, multiplier=3.0, candle_type='ha')['signal']
confirmation = backtest_trend_ali(SYMBOL, TF, limit, length=60, length_mult=6.0, mode='Hma', candle_type='ha')['trend']
if len(signal) > len(df): signal = signal[-len(df):]
if len(confirmation) > len(df): confirmation = confirmation[-len(df):]
if len(signal) < len(df): signal = signal + ['hold'] * (len(df) - len(signal))
if len(confirmation) < len(df): confirmation = confirmation + ['hold'] * (len(df) - len(confirmation))

df.to_csv(os.path.join(CACHE_DIR, "window2_df.csv"), index=False)
pd.DataFrame({"signal": signal}).to_csv(os.path.join(CACHE_DIR, "window2_signal.csv"), index=False)
pd.DataFrame({"confirmation": confirmation}).to_csv(os.path.join(CACHE_DIR, "window2_confirmation.csv"), index=False)

KEYS = ["Total Trades Executed", "Winning Trades", "Losing Trades", "Win Rate",
        "Total Profit", "Final Balance", "ROI"]

def run_once(sig, conf, tag):
    buf = io.StringIO()
    with redirect_stdout(buf):
        report = backtest(df.copy(), list(sig), list(conf), symbol=SYMBOL, tf=TF, **PARAMS)
    out = buf.getvalue()
    print("[run %s] report=%s" % (tag, report))
    stats = {}
    for line in out.splitlines():
        for k in KEYS:
            if line.strip().startswith(k + ":"):
                raw = line.split(":", 1)[1].strip().replace("$", "").replace("%", "").strip()
                try: stats[k] = float(raw)
                except ValueError: stats[k] = raw
    return stats, report

base_stats, rep_base = run_once(signal, confirmation, "w2_baseline")
lagged_signal = ["hold"] + list(signal[:-1])
lagged_confirmation = ["hold"] + list(confirmation[:-1])
lag_stats, rep_lag = run_once(lagged_signal, lagged_confirmation, "w2_lagged")

lines = []
lines.append("=" * 70)
lines.append("WINDOW 2 LAG BIAS TEST - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
lines.append("candles: %d (%s .. %s)" % (limit, df['time'].iloc[0], df['time'].iloc[-1]))
lines.append("=" * 70)
header = "%-24s %13s %13s %13s" % ("metric", "baseline(t)", "lagged(t-1)", "delta")
lines.append(header); lines.append("-" * len(header))
for k in KEYS:
    b, l = base_stats.get(k), lag_stats.get(k)
    if isinstance(b, (int, float)) and isinstance(l, (int, float)):
        lines.append("%-24s %13.2f %13.2f %13.2f" % (k, b, l, l - b))
    else:
        lines.append("%-24s %13s %13s %13s" % (k, b, l, "n/a"))
lines.append("report files: %s | %s" % (rep_base, rep_lag))

result = "\n".join(lines)
with open(os.path.join(CACHE_DIR, "lag_bias_window2_result.md"), "w", encoding="utf-8") as f:
    f.write(result)

sys.stdout.reconfigure(encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'reconfigure') else None
print("\n" + result)
