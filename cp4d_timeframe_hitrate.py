# cp4d_timeframe_hitrate.py
# CP4d: repeat the directional hit-rate diagnostic on M15 and H1.
# Same method as CP4c (Supertrend state flips, baseline params atr=10 mult=3.0 HA;
# horizons 5/20 bars of the new timeframe; close[i+h] vs close[i]; hit = direction match).
# Same 6 calendar windows: boundaries taken from the M3 bulk fetch (start_pos=1, 86400)
# and applied to M15/H1 bars fetched with copy_rates_range over the identical span.
# Read-only. No orders. No installs.

import os, sys, json, time
import numpy as np
import pandas as pd
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = os.path.join(ROOT, "project_audit", "stability_windows_cache")
os.makedirs(CACHE, exist_ok=True)

for mod in ("numpy", "pandas", "MetaTrader5", "pandas_ta"):
    try:
        __import__(mod)
    except ImportError:
        print("MISSING DEPENDENCY:", mod)
        sys.exit(2)

import MetaTrader5 as mt5
import backtest.indicators as bi

SYMBOL = 'XAUUSD.'
WINDOW_BARS_M3 = 14400
N_WINDOWS = 6
HORIZONS = (5, 20)

t0 = time.time()
def log(msg):
    print("[%7.1fs] %s" % (time.time() - t0, msg), flush=True)

ok = mt5.initialize()
digits = None
if ok:
    info = mt5.symbol_info(SYMBOL)
    digits = info.digits if info is not None else None
if not ok or digits is None:
    print("[error] MT5 unavailable")
    sys.exit(3)

# ---------- M3 bulk -> window boundaries (calendar-identical across TFs) ----------
raw3 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 1, WINDOW_BARS_M3 * N_WINDOWS)
if raw3 is None or len(raw3) < WINDOW_BARS_M3 * N_WINDOWS:
    print("[error] insufficient M3 history")
    sys.exit(3)
raw3 = raw3[np.argsort(raw3['time'])]
bounds = [int(raw3['time'][i * WINDOW_BARS_M3]) for i in range(N_WINDOWS)] + [int(raw3['time'][-1])]
log("M3 boundaries: %s" % [str(pd.to_datetime(b, unit='s')) for b in bounds])

def hit_stats(state, closes, horizon):
    flips = hits = excluded = 0
    for i in range(1, len(state)):
        s_prev, s_cur = state[i - 1], state[i]
        if s_cur in ("buy", "sell") and s_prev != s_cur and s_prev is not None:
            if i + horizon >= len(closes):
                excluded += 1
                continue
            flips += 1
            fwd = closes[i + horizon]
            entry = closes[i]
            if (s_cur == "buy" and fwd > entry) or (s_cur == "sell" and fwd < entry):
                hits += 1
    return flips, hits, excluded

def analyze_tf(tf_name, tf_const):
    tf_str = {"M15": "15m", "H1": "1h"}[tf_name]
    rates = mt5.copy_rates_range(SYMBOL, tf_const,
                                 pd.to_datetime(bounds[0], unit='s').to_pydatetime(),
                                 pd.to_datetime(bounds[-1], unit='s').to_pydatetime())
    if rates is None or len(rates) == 0:
        print("[error] no %s data" % tf_name)
        return []
    df_all = pd.DataFrame(rates)
    df_all['time'] = pd.to_datetime(df_all['time'], unit='s')
    df_all = df_all.sort_values('time').reset_index(drop=True)
    log("[%s] fetched %d bars (%s .. %s)" % (tf_name, len(df_all),
        df_all['time'].iloc[0], df_all['time'].iloc[-1]))
    rows = []
    for w in range(N_WINDOWS):
        lo, hi = bounds[w], bounds[w + 1]
        sl_mask = (df_all['time'].astype(np.int64) // 10**9 >= lo) & \
                  (df_all['time'].astype(np.int64) // 10**9 <= hi)
        wsl = df_all[sl_mask]
        if len(wsl) < 60:
            log("[warn] %s window %d too small (%d bars) - skipped" % (tf_name, w + 1, len(wsl)))
            continue
        wsl_ep = wsl.copy()
        wsl_ep['time'] = (wsl_ep['time'].astype(np.int64) // 10**9)
        wsl_ep = wsl_ep.to_records(index=False)
        wdf = wsl.rename(columns={'tick_volume': 'volume'})[
            ['time', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)
        st = bi.backtest_supertrend(SYMBOL, tf_str, len(wdf), atr_period=10, multiplier=3.0,
                                    candle_type='ha', df=wsl_ep)["trend"]
        ta = bi.backtest_trend_ali(SYMBOL, tf_str, len(wdf), length=60, length_mult=6.0,
                                   mode='Hma', candle_type='ha', df=wsl_ep)["trend"]
        closes = wdf['close'].to_numpy()
        for label, series in (("supertrend", st), ("trend_ali", ta)):
            for h in HORIZONS:
                flips, hits, excl = hit_stats(series, closes, h)
                rate = (hits / flips * 100) if flips else None
                rows.append({"tf": tf_name, "window": w + 1, "indicator": label,
                             "horizon": h, "flips": flips, "hits": hits,
                             "hit_rate_pct": rate, "excluded_end": excl,
                             "bars": len(wdf)})
                log("[%s] window %d | %-10s | h=%2d | flips=%4d hits=%4d rate=%s"
                    % (tf_name, w + 1, label, h, flips, hits,
                       ("%.2f%%" % rate) if rate is not None else "n/a"))
    return rows

rows_m15 = analyze_tf("M15", mt5.TIMEFRAME_M15)
rows_h1 = analyze_tf("H1", mt5.TIMEFRAME_H1)

# ---------- aggregates ----------
def agg(rows, indicator, h):
    rs = [r for r in rows if r["indicator"] == indicator and r["horizon"] == h]
    f = sum(r["flips"] for r in rs); hts = sum(r["hits"] for r in rs)
    p = (hts / f) if f else None
    ci = None
    if p is not None and f > 0:
        se = (p * (1 - p) / f) ** 0.5
        ci = [max(0.0, p - 1.96 * se) * 100, min(1.0, p + 1.96 * se) * 100]
    return {"flips": f, "hits": hts, "rate": (p * 100) if p is not None else None, "wald95": ci}

m3_measured = {  # MEASURED in CP4c (2026-09-04 12:53), quoted for comparison
    "supertrend_h5": {"rate": 47.33, "wald95": [44.81, 49.84], "flips": 1515},
    "supertrend_h20": {"rate": 48.25, "wald95": [45.73, 50.77], "flips": 1515},
    "trend_ali_h5": {"rate": 48.99, "wald95": [45.80, 52.18], "flips": 943},
    "trend_ali_h20": {"rate": 49.68, "wald95": [46.49, 52.87], "flips": 942},
}

lines = ["CP4d TIMEFRAME HIT-RATE COMPARISON (M3 vs M15 vs H1) - %s" % datetime.now(),
         "method: Supertrend state flips (baseline params, HA); close[i+h] vs close[i]; same 6 calendar windows", ""]
header = "%-4s %-11s %4s %7s %7s %9s  %-24s" % ("TF", "Indicator", "H", "Flips", "Hits", "Rate%", "Wald95")
lines.append(header); lines.append("-" * len(header))
for tf_label, rows in (("M3*", None), ("M15", rows_m15), ("H1", rows_h1)):
    if rows is None:
        for key, v in m3_measured.items():
            ind, h = key.rsplit("_h", 1)
            lines.append("%-4s %-11s %4s %7d %7s %9s  %-24s"
                         % (tf_label, ind, h, v["flips"], "n/a", "%.2f" % v["rate"],
                            "[%s - %s]" % (v["wald95"][0], v["wald95"][1])))
        lines.append("(M3 = MEASURED in CP4c, quoted for comparison)")
        continue
    for ind in ("supertrend", "trend_ali"):
        for h in HORIZONS:
            a = agg(rows, ind, h)
            ci = ("[%.2f%% - %.2f%%]" % (a["wald95"][0], a["wald95"][1])) if a["wald95"] else "n/a"
            lines.append("%-4s %-11s %4d %7d %7d %9s  %-24s"
                         % (tf_label, ind, h, a["flips"], a["hits"],
                            ("%.2f" % a["rate"]) if a["rate"] is not None else "n/a", ci))
result = "\n".join(lines)

with open(os.path.join(CACHE, "cp4d_tf_hitrate_results.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "m15_rows": rows_m15,
               "h1_rows": rows_h1, "m3_measured": m3_measured,
               "aggregates_m15": {("%s_h%d" % (i, h)): agg(rows_m15, i, h)
                                  for i in ("supertrend", "trend_ali") for h in HORIZONS},
               "aggregates_h1": {("%s_h%d" % (i, h)): agg(rows_h1, i, h)
                                 for i in ("supertrend", "trend_ali") for h in HORIZONS}},
              f, indent=2, ensure_ascii=False)
with open(os.path.join(CACHE, "cp4d_tf_hitrate_results.md"), "w", encoding="utf-8") as f:
    f.write(result)

print("\n" + result)
print("[saved] project_audit/stability_windows_cache/cp4d_tf_hitrate_results.md|.json")
print("CP4d COMPLETE")
