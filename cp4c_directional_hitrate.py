# cp4c_directional_hitrate.py
# CHEAP DIAGNOSTIC (user-specified): directional hit-rate of Supertrend flips.
# For every Supertrend state flip (baseline params atr=10, mult=3.0, HA candles)
# at bar i: predicted direction = new state ('buy'/'sell').
# Actual outcome = close[i+h] vs close[i] for h in {5, 20}  (close-to-close).
# Hit = predicted direction matches actual move. Pure metric; no SL/TP, no IS/OOS.
# Supplementary: same metric for trend_ali state flips (labeled secondary).
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

for mod in ("numpy", "pandas", "MetaTrader5", "ta", "pandas_ta"):
    try:
        __import__(mod)
    except ImportError:
        print("MISSING DEPENDENCY:", mod)
        sys.exit(2)

import MetaTrader5 as mt5
import numpy as np
import backtest.indicators as bi

SYMBOL, TF = 'XAUUSD.', '3m'
WINDOW_BARS = 14400
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

TOTAL = WINDOW_BARS * N_WINDOWS
raw = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 1, TOTAL)
if raw is None or len(raw) < TOTAL:
    print("[error] insufficient history")
    sys.exit(3)
raw = raw[np.argsort(raw['time'])]
log("fetch %d candles (%s .. %s)"
    % (len(raw), pd.to_datetime(raw['time'][0], unit='s'),
       pd.to_datetime(raw['time'][-1], unit='s')))

def wslice(w):
    return raw[w * WINDOW_BARS:(w + 1) * WINDOW_BARS]

def wdf_of(sl):
    t = pd.to_datetime(sl['time'], unit='s')
    d = pd.DataFrame(sl).rename(columns={'tick_volume': 'volume'})[
        ['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    d['time'] = t.values
    return d.reset_index(drop=True)

def hit_stats(state, closes, horizon):
    """state: per-bar 'buy'/'sell' (may contain None); flip at i where state changes."""
    flips = hits = excluded = 0
    for i in range(1, len(state) - 0):
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

rows = []
for w in range(N_WINDOWS):
    sl = wslice(w)
    wdf = wdf_of(sl)
    closes = wdf["close"].to_numpy()
    st = bi.backtest_supertrend(SYMBOL, TF, len(wdf), atr_period=10, multiplier=3.0,
                                candle_type='ha', df=sl)["trend"]          # 'buy'/'sell' state
    ta = bi.backtest_trend_ali(SYMBOL, TF, len(wdf), length=60, length_mult=6.0,
                               mode='Hma', candle_type='ha', df=sl)["trend"]
    for label, series in (("supertrend", st), ("trend_ali", ta)):
        for h in HORIZONS:
            flips, hits, excl = hit_stats(series, closes, h)
            rate = (hits / flips * 100) if flips else None
            rows.append({"window": w + 1, "indicator": label, "horizon": h,
                         "flips": flips, "hits": hits, "hit_rate_pct": rate,
                         "excluded_end": excl})
            log("window %d | %-10s | h=%2d | flips=%4d hits=%4d rate=%s | excl_end=%d"
                % (w + 1, label, h, flips, hits,
                   ("%.2f%%" % rate) if rate is not None else "n/a", excl))

# ---------- aggregate ----------
def agg(indicator, h):
    rs = [r for r in rows if r["indicator"] == indicator and r["horizon"] == h]
    f = sum(r["flips"] for r in rs); hts = sum(r["hits"] for r in rs)
    ex = sum(r["excluded_end"] for r in rs)
    p = (hts / f) if f else None
    ci = None
    if p is not None and f > 0:
        se = (p * (1 - p) / f) ** 0.5
        ci = [max(0.0, p - 1.96 * se) * 100, min(1.0, p + 1.96 * se) * 100]
    return {"flips": f, "hits": hts, "hit_rate_pct": (p * 100) if p is not None else None,
            "wald95_pct": ci, "excluded_end": ex}

aggregates = {("%s_h%d" % (ind, h)): agg(ind, h)
              for ind in ("supertrend", "trend_ali") for h in HORIZONS}

lines = ["CP4c DIRECTIONAL HIT-RATE DIAGNOSTIC - %s" % datetime.now(),
         "method: Supertrend state flips (baseline params, HA) vs close[i+h] vs close[i]",
         "horizons: 5 and 20 bars | windows: 6 (each 14,400 M3 bars) | metric: hit rate %",
         ""]
header = "%-6s %-11s %4s %7s %7s %9s %9s" % ("Win", "Indicator", "H", "Flips", "Hits", "Rate%", "ExclEnd")
lines.append(header); lines.append("-" * len(header))
for r in rows:
    lines.append("%-6s %-11s %4d %7d %7d %9s %9d"
                 % (r["window"], r["indicator"], r["horizon"], r["flips"],
                    r["hits"], ("%.2f" % r["hit_rate_pct"]) if r["hit_rate_pct"] is not None else "n/a",
                    r["excluded_end"]))
lines.append("")
lines.append("AGGREGATE (sum over 6 windows):")
for key, a in aggregates.items():
    ci = ("[%.2f%% - %.2f%%]" % (a["wald95_pct"][0], a["wald95_pct"][1])) if a["wald95_pct"] else "n/a"
    lines.append("  %-16s flips=%5d hits=%5d rate=%s | Wald95=%s"
                 % (key, a["flips"], a["hits"],
                    ("%.2f%%" % a["hit_rate_pct"]) if a["hit_rate_pct"] is not None else "n/a", ci))
lines.append("")
lines.append("reading rule (user-defined): rate ~= 50% -> indicators give no directional edge;")
lines.append("rate clearly >50% -> direction OK, problem is entry timing / trade management.")
result = "\n".join(lines)

with open(os.path.join(CACHE, "cp4c_hitrate_results.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "rows": rows,
               "aggregates": aggregates}, f, indent=2, ensure_ascii=False)
with open(os.path.join(CACHE, "cp4c_hitrate_results.md"), "w", encoding="utf-8") as f:
    f.write(result)

print("\n" + result)
print("[saved] project_audit/stability_windows_cache/cp4c_hitrate_results.md|.json")
print("CP4c COMPLETE")
