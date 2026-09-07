# validate_pipeline_fix.py
# Regression proof for the Phase-1 fix (df-parameterized signal functions):
#   PATH A (NEW): backtest_supertrend / backtest_trend_ali with df=<window slice>
#   PATH B (OLD): same functions WITHOUT df, while mt5.copy_rates_from_pos is
#                 monkey-patched in-process to serve the SAME slice.
# Requirement: PATH A results must be IDENTICAL to PATH B (signals + stats).
# Then: full 6-window coherent scan via PATH A (the fixed pipeline).
# READ-ONLY for the project: no project file modified, no orders, no installs.

import os, sys, io, json, time
from contextlib import redirect_stdout
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = os.path.join(ROOT, "project_audit", "stability_windows_cache")
os.makedirs(CACHE, exist_ok=True)

for mod in ("numpy", "pandas", "plotly", "yfinance", "MetaTrader5", "ta", "pandas_ta"):
    try:
        __import__(mod)
    except ImportError:
        print("MISSING DEPENDENCY:", mod)
        sys.exit(2)

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
import backtest.hashem_backtest as hb
import backtest.indicators as bi

SYMBOL, TF = 'XAUUSD.', '3m'
WINDOW_BARS = 14400
N_WINDOWS = 6
KEYS = ["Total Trades Executed", "Winning Trades", "Losing Trades",
        "Win Rate", "Total Profit", "Final Balance", "ROI"]
PARAMS = dict(backtest_days=30, use_risk_free=False, risk_free_distance_pips=50.0,
              use_sl=True, sl_pips=100.0, use_tp=True, tp_pips=200.0,
              close_opposite_position=False, initial_balance=5000.0,
              position_size_mode='risk_percent', fixed_lot_size=0.01,
              risk_percent=2, risk_based_on='initial', analyze_weekdays=True,
              analyze_time_sessions=True, session_duration_hours=4.0)

t0 = time.time()
def log(msg):
    print("[%7.1fs] %s" % (time.time() - t0, msg), flush=True)

ok = mt5.initialize()
digits = None
if ok:
    info = mt5.symbol_info(SYMBOL)
    digits = info.digits if info is not None else None
log("mt5 initialize=%s digits=%s" % (ok, digits))
if not ok or digits is None:
    print("[error] MT5 unavailable - aborting.")
    sys.exit(3)

TOTAL = WINDOW_BARS * N_WINDOWS
raw = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 1, TOTAL)
if raw is None or len(raw) < TOTAL:
    print("[error] insufficient history (%s/%s)" % (0 if raw is None else len(raw), TOTAL))
    sys.exit(3)
raw = raw[np.argsort(raw['time'])]
mt = pd.to_datetime(raw['time'], unit='s')
log("fetch %d/%d candles (%s .. %s)" % (len(raw), TOTAL, mt[0], mt[-1]))

def window_slice(w):
    return raw[w * WINDOW_BARS:(w + 1) * WINDOW_BARS]

def window_df(sl):
    t = pd.to_datetime(sl['time'], unit='s')
    wdf = pd.DataFrame(sl).rename(columns={'tick_volume': 'volume'})
    wdf = wdf[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    wdf['time'] = t.values
    return wdf.reset_index(drop=True)

def align(df, sig, conf):
    sig, conf = list(sig), list(conf)
    if len(sig) > len(df): sig = sig[-len(df):]
    if len(conf) > len(df): conf = conf[-len(df):]
    if len(sig) < len(df): sig += ['hold'] * (len(df) - len(sig))
    if len(conf) < len(df): conf += ['hold'] * (len(df) - len(conf))
    return sig, conf

def parse_stats(out):
    stats = {}
    for line in out.splitlines():
        for k in KEYS:
            if line.strip().startswith(k + ":"):
                v = line.split(":", 1)[1].strip().replace("$", "").replace("%", "").strip()
                try:
                    stats[k] = float(v)
                except ValueError:
                    stats[k] = v
    return stats

def run_backtest(wdf, sig, conf, tag):
    buf = io.StringIO()
    with redirect_stdout(buf):
        report = hb.backtest(wdf.copy(), list(sig), list(conf), symbol=SYMBOL, tf=TF, **PARAMS)
    out = buf.getvalue()
    with open(os.path.join(CACHE, "v2_%s_stdout.txt" % tag), "w", encoding="utf-8") as f:
        f.write(out)
    return parse_stats(out), report

# ---------- A/B regression check on window 1 ----------
sl1 = window_slice(0)
wdf1 = window_df(sl1)

sig_a = bi.backtest_supertrend(SYMBOL, TF, len(wdf1), atr_period=10,
                               multiplier=3.0, candle_type='ha', df=sl1)['signal']
conf_a = bi.backtest_trend_ali(SYMBOL, TF, len(wdf1), length=60, length_mult=6.0,
                               mode='Hma', candle_type='ha', df=sl1)['trend']
log("PATH A (df= parameter) done for window 1")

REAL_COPY = mt5.copy_rates_from_pos
CURRENT = {"df": sl1}
mt5.copy_rates_from_pos = lambda s, tf, sp, c: (CURRENT["df"].iloc[-c:]
                                               if c < len(CURRENT["df"]) else CURRENT["df"])
sig_b = bi.backtest_supertrend(SYMBOL, TF, len(wdf1), atr_period=10,
                               multiplier=3.0, candle_type='ha')['signal']
conf_b = bi.backtest_trend_ali(SYMBOL, TF, len(wdf1), length=60, length_mult=6.0,
                               mode='Hma', candle_type='ha')['trend']
mt5.copy_rates_from_pos = REAL_COPY
log("PATH B (monkeypatched fetch, same slice) done for window 1")

signals_equal = (list(sig_a) == list(sig_b)) and (list(conf_a) == list(conf_b))
stats_a, rep_a = run_backtest(wdf1, align(wdf1, sig_a, conf_a)[0], align(wdf1, sig_a, conf_a)[1], "w1_pathA")
wdfB = window_df(sl1)
sA, cA = align(wdf1, sig_a, conf_a)
stats_b, _ = run_backtest(wdfB, sA, cA, "w1_pathB")
stats_equal = stats_a == stats_b
log("A/B signals identical: %s | stats identical: %s" % (signals_equal, stats_equal))
if not (signals_equal and stats_equal):
    print("[FAIL] the df= fix does NOT reproduce the reference path - investigate before use.")
    sys.exit(1)
log("REGRESSION CHECK PASSED - the df= fix is byte-equivalent to the reference path.")

# ---------- full 6-window coherent scan via the FIXED pipeline ----------
results = []
for w in range(N_WINDOWS):
    sl = window_slice(w)
    wdf = window_df(sl)
    if len(wdf) < WINDOW_BARS:
        log("window %d SKIPPED (incomplete)" % (w + 1))
        continue
    signal = bi.backtest_supertrend(SYMBOL, TF, len(wdf), atr_period=10,
                                    multiplier=3.0, candle_type='ha', df=sl)['signal']
    confirmation = bi.backtest_trend_ali(SYMBOL, TF, len(wdf), length=60, length_mult=6.0,
                                         mode='Hma', candle_type='ha', df=sl)['trend']
    signal, confirmation = align(wdf, signal, confirmation)
    stats, report = run_backtest(wdf, signal, confirmation, "w%d" % (w + 1))
    results.append({"window": w + 1, "start": str(wdf['time'].iloc[0]), "end": str(wdf['time'].iloc[-1]),
                    "candles": len(wdf), "stats": stats, "report": report})
    log("window %d RESULT %s -> %s | trades=%s | wr=%s%% | roi=%s%%"
        % (w + 1, wdf['time'].iloc[0], wdf['time'].iloc[-1],
           stats.get("Total Trades Executed"), stats.get("Win Rate"), stats.get("ROI")))

rois = [r["stats"].get("ROI") for r in results if r["stats"].get("ROI") is not None]
lines = ["COHERENT SCAN VIA FIXED PIPELINE (df= parameter) - %s" % datetime.now(),
         "A/B regression check: signals_equal=%s stats_equal=%s" % (signals_equal, stats_equal),
         "", header := "%-6s %-20s %-20s %8s %9s %10s %8s" % ("Win", "Start", "End", "Trades", "WinRate", "Profit", "ROI")]
lines.append(header); lines.append("-" * len(header))
for r in results:
    s = r["stats"]
    lines.append("%-6s %-20s %-20s %8s %9s %10s %8s"
                 % (r["window"], r["start"][:19], r["end"][:19],
                    s.get("Total Trades Executed"), s.get("Win Rate"),
                    s.get("Total Profit"), s.get("ROI")))
if rois:
    lines.append("")
    lines.append("ROI min=%s max=%s avg=%.2f positive=%d/%d"
                 % (min(rois), max(rois), sum(rois) / len(rois),
                    sum(1 for x in rois if x > 0), len(rois)))
result = "\n".join(lines)
with open(os.path.join(CACHE, "coherent_v2_results.md"), "w", encoding="utf-8") as f:
    f.write(result)
with open(os.path.join(CACHE, "coherent_v2_results.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "mode": "fixed-df-param",
               "ab_regression": {"signals_equal": signals_equal, "stats_equal": stats_equal},
               "results": results}, f, indent=2, default=str, ensure_ascii=False)
print("\n" + result)
print("[saved] project_audit/stability_windows_cache/coherent_v2_results.md|.json")
print("VALIDATION COMPLETE")
