# coherent_stability_test.py  (v2 - epoch-safe, unbuffered-friendly)
# T1: TRUE per-window stability with COHERENT signal/price pairing.
# MetaTrader5.copy_rates_from_pos is monkey-patched IN-PROCESS ONLY to serve
# frozen EPOCH-INT slices (byte-identical semantics to production fetch), so the
# REAL project indicator functions compute on the exact window data being scored.
# No project file modified. No orders. No installs.
# Side effects: ~7 HTML reports in backtest/, evidence files in
#               project_audit/stability_windows_cache/coherent_*

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

# ---------- real bulk fetch (forming candle excluded; time kept as epoch int) ----------
ok = mt5.initialize()
digits = None
if ok:
    info = mt5.symbol_info(SYMBOL)
    digits = info.digits if info is not None else None
log("mt5 initialize=%s digits=%s" % (ok, digits))
if not ok or digits is None:
    print("[error] MT5/symbol unavailable - aborting (no silent digits fallback).")
    sys.exit(3)

TOTAL = WINDOW_BARS * N_WINDOWS
raw = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 1, TOTAL)
if raw is None or len(raw) == 0:
    print("[error] MT5 returned no candles.")
    sys.exit(3)
raw = raw[np.argsort(raw['time'])]                     # ascending; keep structured numpy (production-identical)
master_time = pd.to_datetime(raw['time'], unit='s')
log("fetch %d/%d candles (%s .. %s)" % (len(raw), TOTAL,
    master_time[0], master_time[-1]))
if len(raw) < TOTAL:
    print("[warning] fewer candles than requested; trailing windows will be skipped.")

# ---------- in-process patch: serve frozen EPOCH slices ----------
CURRENT = {"df": None}

def fake_copy_rates_from_pos(symbol, timeframe, start_pos, count):
    df = CURRENT["df"]
    if df is None:
        raise RuntimeError("patched fetch called with no active window")
    return df.iloc[-count:] if count < len(df) else df

REAL_COPY = mt5.copy_rates_from_pos
mt5.copy_rates_from_pos = fake_copy_rates_from_pos

def window_pair(w):
    sl = raw[w * WINDOW_BARS:(w + 1) * WINDOW_BARS]     # structured-array slice (production-identical)
    if len(sl) == 0:
        return None, None
    t = pd.to_datetime(sl['time'], unit='s')
    wdf = pd.DataFrame(sl)
    wdf = wdf.rename(columns={'tick_volume': 'volume'})
    wdf = wdf[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    wdf['time'] = t.values
    return wdf.reset_index(drop=True), sl

def align(df, sig, conf):
    sig, conf = list(sig), list(conf)
    if len(sig) > len(df): sig = sig[-len(df):]
    if len(conf) > len(df): conf = conf[-len(df):]
    if len(sig) < len(df): sig += ['hold'] * (len(df) - len(sig))
    if len(conf) < len(df): conf += ['hold'] * (len(df) - len(conf))
    return sig, conf

def run_window(w, tag):
    wdf, wraw = window_pair(w)
    CURRENT["df"] = wraw
    ts = time.time()
    signal = bi.backtest_supertrend(SYMBOL, TF, len(wdf), atr_period=10,
                                    multiplier=3.0, candle_type='ha')['signal']
    confirmation = bi.backtest_trend_ali(SYMBOL, TF, len(wdf), length=60,
                                         length_mult=6.0, mode='Hma',
                                         candle_type='ha')['trend']
    log("%s signals computed in %.1fs" % (tag, time.time() - ts))
    signal, confirmation = align(wdf, signal, confirmation)
    CURRENT["df"] = None
    buf = io.StringIO()
    with redirect_stdout(buf):
        report = hb.backtest(wdf.copy(), list(signal), list(confirmation),
                             symbol=SYMBOL, tf=TF, **PARAMS)
    out = buf.getvalue()
    with open(os.path.join(CACHE, "coherent_%s_stdout.txt" % tag),
              "w", encoding="utf-8") as f:
        f.write(out)
    stats = {}
    for line in out.splitlines():
        for k in KEYS:
            if line.strip().startswith(k + ":"):
                v = line.split(":", 1)[1].strip().replace("$", "").replace("%", "").strip()
                try:
                    stats[k] = float(v)
                except ValueError:
                    stats[k] = v
    return stats, report, len(wdf), str(wdf['time'].iloc[0]), str(wdf['time'].iloc[-1])

# ---------- run all windows coherently ----------
log("mode: COHERENT pairing (signals from the SAME window data as prices)")
results = []
for w in range(N_WINDOWS):
    wdf, _ = window_pair(w)
    if wdf is None or len(wdf) < WINDOW_BARS:
        log("window %d SKIPPED (incomplete)" % (w + 1))
        continue
    stats, rep, n, tstart, tend = run_window(w, "w%d" % (w + 1))
    results.append({"window": w + 1, "start": tstart, "end": tend, "candles": n,
                    "stats": stats, "report": rep})
    log("window %d RESULT %s -> %s | trades=%s | wr=%s%% | roi=%s%%"
        % (w + 1, tstart, tend, stats.get("Total Trades Executed"),
           stats.get("Win Rate"), stats.get("ROI")))

# ---------- in-mode determinism recheck (skipped: engine determinism already proven twice) ----------
det = None
if results and os.environ.get("COHERENT_RECHECK") == "1":
    last = results[-1]["window"] - 1
    s_again, _, _, _, _ = run_window(last, "w%d_again" % results[-1]["window"])
    det = (s_again == results[-1]["stats"])
    log("determinism recheck (coherent mode) identical: %s" % det)

# ---------- summary ----------
rois = [r["stats"].get("ROI") for r in results if r["stats"].get("ROI") is not None]
lines = ["COHERENT MULTI-WINDOW BASELINE STABILITY TEST - %s" % datetime.now(),
         "pairing: signals computed on the SAME window data as prices (patched fetch)",
         "windows: %d | candles/window: %d | digits: %s" % (len(results), WINDOW_BARS, digits),
         "", "metric table (coherent):", ""]
header = "%-6s %-20s %-20s %8s %9s %10s %8s" % ("Win", "Start", "End", "Trades", "WinRate", "Profit", "ROI")
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
lines.append("")
lines.append("determinism recheck (coherent mode): %s" % (det if results else "n/a"))
lines.append("")
lines.append("note: same periods as the earlier INVALID (self-fetched) run -> direct comparison.")

result = "\n".join(lines)
with open(os.path.join(CACHE, "coherent_results.md"), "w", encoding="utf-8") as f:
    f.write(result)
with open(os.path.join(CACHE, "coherent_results.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "symbol": SYMBOL, "tf": TF,
               "digits": digits, "mode": "coherent", "results": results,
               "determinism_recheck": det},
              f, indent=2, default=str, ensure_ascii=False)

print("\n" + "=" * 70)
print(result)
print("=" * 70)
print("[saved] project_audit/stability_windows_cache/coherent_results.md|.json")
print("TEST COMPLETE")
