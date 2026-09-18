# cp4_walkforward.py
# CHECKPOINT CP4 - HONEST OPTIMIZATION / WALK-FORWARD (reduced documented grid: CP4a)
# Walk-forward: fold i => IS = window i, OOS = window i+1 (rolling).
# Parameter selection uses IN-SAMPLE ONLY (ROI, min 10 IS trades guard).
# OOS runs ONCE with frozen params. OOS is never used for selection.
# Grid (documented): ST atr{10,14,20} x mult{2.5,3.0,3.5} (+TA length{40,80} at baseline ST)
# SL/TP fixed at baseline (100/200 pips) - risk-geometry sensitivity deferred to CP5.
# Metrics via project run_backtest(): roi/winrate/trades/PF/maxDD/final_balance.
# No orders. No installs. No project source changes.

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

for mod in ("numpy", "pandas", "plotly", "yfinance", "MetaTrader5", "ta", "pandas_ta"):
    try:
        __import__(mod)
    except ImportError:
        print("MISSING DEPENDENCY:", mod)
        sys.exit(2)

import MetaTrader5 as mt5
import backtest.hashem_backtest as hb
import backtest.indicators as bi

SYMBOL, TF = 'XAUUSD.', '3m'
WINDOW_BARS = 14400
N_WINDOWS = 6
N_FOLDS = N_WINDOWS - 1
MIN_IS_TRADES = 10
KEYS = ["Total Trades Executed", "Win Rate", "Total Profit", "Final Balance", "ROI"]

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
log("mt5 init=%s digits=%s" % (ok, digits))

TOTAL = WINDOW_BARS * N_WINDOWS
raw = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 1, TOTAL)
if raw is None or len(raw) < TOTAL:
    print("[error] insufficient history")
    sys.exit(3)
raw = raw[np.argsort(raw['time'])]
mtimes = pd.to_datetime(raw['time'], unit='s')
log("fetch %d/%d (%s .. %s)" % (len(raw), TOTAL, mtimes[0], mtimes[-1]))

def wslice(w):
    return raw[w * WINDOW_BARS:(w + 1) * WINDOW_BARS]

def wdf_of(sl):
    t = pd.to_datetime(sl['time'], unit='s')
    d = pd.DataFrame(sl).rename(columns={'tick_volume': 'volume'})[
        ['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    d['time'] = t.values
    return d.reset_index(drop=True)

def align(df, sig, conf):
    sig, conf = list(sig), list(conf)
    if len(sig) > len(df): sig = sig[-len(df):]
    if len(conf) > len(df): conf = conf[-len(df):]
    if len(sig) < len(df): sig += ['hold'] * (len(df) - len(sig))
    if len(conf) < len(df): conf += ['hold'] * (len(df) - len(conf))
    return sig, conf

def run_rb(df, sig, conf):
    """Project run_backtest() engine: returns roi/winrate/trades/PF/maxDD/..."""
    return hb.run_backtest(df.copy(), list(sig), list(conf), symbol=SYMBOL, tf=TF,
                           backtest_days=30, use_risk_free=False,
                           risk_free_distance_pips=50.0, use_sl=True, sl_pips=100.0,
                           use_tp=True, tp_pips=200.0, close_opposite_position=False,
                           initial_balance=5000.0, position_size_mode='risk_percent',
                           fixed_lot_size=0.01, risk_percent=2, risk_based_on='initial')

def signals_for(sl, combo):
    wdf = wdf_of(sl)
    sig = bi.backtest_supertrend(SYMBOL, TF, len(wdf), atr_period=combo["atr_period"],
                                 multiplier=combo["multiplier"], candle_type='ha',
                                 df=sl)['signal']
    conf = bi.backtest_trend_ali(SYMBOL, TF, len(wdf), length=combo["length"],
                                 length_mult=combo["length_mult"], mode='Hma',
                                 candle_type='ha', df=sl)['trend']
    return wdf, align(wdf, sig, conf)

# ---------- engine-equivalence cross-check (backtest() vs run_backtest()), fold 0 baseline ----------
sl0 = wslice(0)
wdf0 = wdf_of(sl0)
combo0 = {"atr_period": 10, "multiplier": 3.0, "length": 60, "length_mult": 6.0}
wdf0, (sig0, conf0) = signals_for(sl0, combo0)
import io
from contextlib import redirect_stdout
buf = io.StringIO()
with redirect_stdout(buf):
    hb.backtest(wdf0.copy(), list(sig0), list(conf0), symbol=SYMBOL, tf=TF,
                backtest_days=30, use_risk_free=False, risk_free_distance_pips=50.0,
                use_sl=True, sl_pips=100.0, use_tp=True, tp_pips=200.0,
                close_opposite_position=False, initial_balance=5000.0,
                position_size_mode='risk_percent', fixed_lot_size=0.01,
                risk_percent=2, risk_based_on='initial', analyze_weekdays=False,
                analyze_time_sessions=False, session_duration_hours=4.0)
bt_stats = {}
for line in buf.getvalue().splitlines():
    for k in ("Total Trades Executed", "Win Rate", "ROI"):
        if line.strip().startswith(k + ":"):
            v = line.split(":", 1)[1].strip().replace("$", "").replace("%", "").strip()
            bt_stats[k] = float(v)
rb = run_rb(wdf0, sig0, conf0)
eq = (bt_stats.get("Total Trades Executed") == rb["total_trades"] and
      abs(bt_stats.get("Win Rate", 0) - rb["winrate"]) <= 0.005 and
      abs(bt_stats.get("ROI", 0) - rb["roi"]) <= 0.005)
log("engine equivalence backtest()==run_backtest(): %s (bt=%s | rb=%s)" % (eq, bt_stats, rb))
if not eq:
    print("[FAIL] engine divergence between backtest() and run_backtest() - STOP")
    sys.exit(1)
check_equiv = eq

# ---------- grid ----------
GRID = [{"atr_period": a, "multiplier": m, "length": 60, "length_mult": 6.0}
        for a in (10, 14, 20) for m in (2.5, 3.0, 3.5)]
GRID += [{"atr_period": 10, "multiplier": 3.0, "length": L, "length_mult": 6.0}
         for L in (40, 80)]
log("grid: %d combinations | folds: %d (rolling IS=win_i, OOS=win_i+1)" % (len(GRID), N_FOLDS))

# ---------- walk-forward ----------
folds = []
for f in range(N_FOLDS):
    is_sl = wslice(f)
    oos_sl = wslice(f + 1)
    is_df, oos_df = wdf_of(is_sl), wdf_of(oos_sl)
    log("FOLD %d: IS=%s..%s | OOS=%s..%s"
        % (f + 1, pd.to_datetime(is_sl['time'][0], unit='s'),
           pd.to_datetime(is_sl['time'][-1], unit='s'),
           pd.to_datetime(oos_sl['time'][0], unit='s'),
           pd.to_datetime(oos_sl['time'][-1], unit='s')))

    is_table = []
    for gi, combo in enumerate(GRID):
        wdf, (sig, conf) = signals_for(is_sl, combo)
        r = run_rb(wdf, sig, conf)
        is_table.append({"combo": combo, "is": r})
        log("  IS combo %2d/%d atr=%s mult=%s len=%s -> trades=%s roi=%s"
            % (gi + 1, len(GRID), combo["atr_period"], combo["multiplier"],
               combo["length"], r["total_trades"] if r else None,
               r["roi"] if r else None))

    eligible = [t for t in is_table if t["is"] and t["is"]["total_trades"] >= MIN_IS_TRADES]
    if not eligible:
        log("  [fold %d] no combo reached %d IS trades -> fold flagged THIN, OOS skipped"
            % (f + 1, MIN_IS_TRADES))
        folds.append({"fold": f + 1, "status": "THIN_IS", "is_table": is_table})
        continue

    best = max(eligible, key=lambda t: (t["is"]["roi"], t["is"]["total_trades"],
                                        t["is"].get("profit_factor", 0)))
    log("  selected (IS-only): atr=%s mult=%s len=%s | IS roi=%.2f%% trades=%s"
        % (best["combo"]["atr_period"], best["combo"]["multiplier"],
           best["combo"]["length"], best["is"]["roi"], best["is"]["total_trades"]))

    # freeze -> OOS (once, untouched)
    wdf_o, (sig_o, conf_o) = signals_for(oos_sl, best["combo"])
    oos = run_rb(wdf_o, sig_o, conf_o)
    log("  OOS (frozen params): roi=%s | winrate=%s | pf=%s | maxdd=%s"
        % (oos["roi"] if oos else None, oos["winrate"] if oos else None,
           oos["profit_factor"] if oos else None, oos["max_drawdown"] if oos else None))

    folds.append({"fold": f + 1, "status": "OK",
                  "is_bounds": [str(pd.to_datetime(is_sl['time'][0], unit='s')),
                                str(pd.to_datetime(is_sl['time'][-1], unit='s'))],
                  "oos_bounds": [str(pd.to_datetime(oos_sl['time'][0], unit='s')),
                                 str(pd.to_datetime(oos_sl['time'][-1], unit='s'))],
                  "selected_combo": best["combo"], "is": best["is"], "oos": oos,
                  "degradation_roi": (oos["roi"] - best["is"]["roi"]) if oos else None,
                  "is_table": is_table})

# ---------- aggregate ----------
ok_folds = [f for f in folds if f.get("status") == "OK"]
oos_rois = [f["oos"]["roi"] for f in ok_folds if f["oos"]]
oos_pos = sum(1 for x in oos_rois if x > 0)
oos_neg = sum(1 for x in oos_rois if x <= 0)
degs = [f["degradation_roi"] for f in ok_folds if f.get("degradation_roi") is not None]
expectancies = [f["oos"]["total_profit"] / f["oos"]["total_trades"]
                for f in ok_folds if f["oos"] and f["oos"]["total_trades"]]

verdict = ("CANDIDATE EDGE (needs CP5 robustness)" if oos_rois and oos_pos > len(oos_rois) / 2
           else "NO PROVEN EDGE")

lines = ["CP4 WALK-FORWARD RESULTS (coherent df= pipeline) - %s" % datetime.now(),
         "grid=%d combos | folds=%d | selection=IS-only ROI (min %d trades) | SL/TP fixed 100/200"
         % (len(GRID), N_FOLDS, MIN_IS_TRADES),
         "engine equivalence backtest()==run_backtest(): %s" % check_equiv,
         ""]
header = "%-5s %-13s %9s %9s %9s %9s %10s" % ("Fold", "Sel(ST/TA)", "IS_ROI", "OOS_ROI", "OOS_TR", "OOS_PF", "Degrad.")
lines.append(header); lines.append("-" * len(header))
for f in ok_folds:
    c = f["selected_combo"]
    lines.append("%-5s %-13s %9.2f %9.2f %9.0f %9.2f %10.2f"
                 % (f["fold"], "%s/%s" % (c["atr_period"], c["length"]),
                    f["is"]["roi"], f["oos"]["roi"], f["oos"]["total_trades"],
                    f["oos"]["profit_factor"], f["degradation_roi"]))
lines.append("")
lines.append("OOS windows: %d | profitable=%d losing=%d" % (len(oos_rois), oos_pos, oos_neg))
if oos_rois:
    lines.append("OOS ROI avg=%.2f min=%s max=%s" % (sum(oos_rois) / len(oos_rois), min(oos_rois), max(oos_rois)))
if degs:
    lines.append("IS->OOS degradation avg=%.2f (positive=OOS worse)" % (sum(degs) / len(degs)))
if expectancies:
    lines.append("OOS expectancy avg=%.2f $/trade" % (sum(expectancies) / len(expectancies)))
lines.append("")
lines.append("EDGE VERDICT: %s" % verdict)
result = "\n".join(lines)

with open(os.path.join(CACHE, "cp4_walkforward_results.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "mode": "walk-forward reduced grid",
               "engine_equivalence": check_equiv, "grid_size": len(GRID),
               "folds": folds, "oos_rois": oos_rois, "oos_positive": oos_pos,
               "oos_losing": oos_neg, "verdict": verdict}, f, indent=2, default=str, ensure_ascii=False)
with open(os.path.join(CACHE, "cp4_walkforward_results.md"), "w", encoding="utf-8") as f:
    f.write(result)

print("\n" + "=" * 70)
print(result)
print("=" * 70)
print("[saved] project_audit/stability_windows_cache/cp4_walkforward_results.md|.json")
print("CP4 COMPLETE")
