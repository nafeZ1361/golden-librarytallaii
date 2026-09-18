# cp4b_atr_exits_test.py
# B0 DIFFERENTIAL DIAGNOSIS (user decision 2026-09-04):
#   Same coherent df= pipeline, same 5 folds, same IS-only selection (11-combo grid),
#   ONLY change: exit geometry  SL = 2 x ATR(14),  TP = 3 x ATR(14)  (ATR at entry bar,
#   pandas_ta Wilder ATR on the plain window candles) instead of fixed 100/200 pips.
#   Entry logic unchanged: Supertrend flip + trend_ali state agreement, same-bar close.
#
# Rigor chain:
#   STEP 1  harness equivalence: harness in FIXED mode (100/200) must reproduce
#           hb.run_backtest() EXACTLY on fold-0 window with baseline combo.
#   STEP 2  walk-forward with ATR exits (11 combos x 5 folds, IS-only selection,
#           frozen OOS). Raw results only.
#
# Read-only for project source. No orders. No installs.

import os, sys, json, time
import numpy as np
import pandas as pd
import pandas_ta
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
N_FOLDS = 5
MIN_IS_TRADES = 10
ATR_LEN = 14
SL_ATR_MULT, TP_ATR_MULT = 2.0, 3.0
INITIAL_BALANCE, RISK_PCT = 5000.0, 2.0

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
PIP = (10 ** -digits) * 10
log("mt5 init=%s digits=%s pip=%s" % (ok, digits, PIP))

def pip_value_per_lot(sym):
    """Harness-local replication of engine get_pip_value(sym, 1.0)."""
    i = mt5.symbol_info(sym)
    if i is None:
        raise ValueError("symbol missing")
    pip_size = (10 ** -i.digits) * 10
    pvq = (pip_size / i.trade_tick_size) * i.trade_tick_value
    if i.currency_profit != "USD":
        if mt5.symbol_info(i.currency_profit + "USD"):
            pvq *= mt5.symbol_info_tick(i.currency_profit + "USD").bid
        elif mt5.symbol_info("USD" + i.currency_profit):
            pvq /= mt5.symbol_info_tick("USD" + i.currency_profit).bid
        else:
            raise RuntimeError("no USD conversion for %s" % i.currency_profit)
    return pvq

PV_PER_LOT = pip_value_per_lot(SYMBOL)
log("pip_value_per_lot=%s USD" % PV_PER_LOT)

TOTAL = WINDOW_BARS * N_WINDOWS
raw = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 1, TOTAL)
if raw is None or len(raw) < TOTAL:
    print("[error] insufficient history")
    sys.exit(3)
raw = raw[np.argsort(raw['time'])]
log("fetch %d candles" % len(raw))

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

# ---------- harness engine (mirror of run_backtest; single switchable exit geometry) ----------
def harness_backtest(df, trig, conf, mode="fixed", atr=None,
                     fixed_sl_pips=100.0, fixed_tp_pips=200.0):
    n = len(df)
    initial = INITIAL_BALANCE
    balance = initial
    peak = initial
    maxdd_pct = 0.0
    positions = []
    current = None
    gross_win = gross_loss = 0.0
    wins = losses = 0
    skipped_entries = 0
    for i in range(n):
        bar = df.iloc[i]
        t_i, c_i = trig[i], conf[i]
        if current is None:
            if t_i in ("buy", "sell") and c_i == t_i:
                entry = float(bar["close"])
                if mode == "atr":
                    a = float(atr[i]) if atr is not None else float("nan")
                    if np.isnan(a) or a <= 0:
                        skipped_entries += 1
                        continue
                    sl_dist = SL_ATR_MULT * a
                    tp_dist = TP_ATR_MULT * a
                else:
                    sl_dist = fixed_sl_pips * PIP
                    tp_dist = fixed_tp_pips * PIP
                if t_i == "buy":
                    slp, tpp, ptype = entry - sl_dist, entry + tp_dist, "buy"
                else:
                    slp, tpp, ptype = entry + sl_dist, entry - tp_dist, "sell"
                sl_pips_val = sl_dist / PIP
                raw_lot = (initial * (RISK_PCT / 100.0)) / (sl_pips_val * PV_PER_LOT)
                lot = max(0.01, round(raw_lot, 2))
                pv_usd = round(PV_PER_LOT * lot, 3)
                current = {"type": ptype, "entry": entry, "sl": slp, "tp": tpp,
                           "lot": lot, "pv": pv_usd, "entry_i": i}
        else:
            exit_price = None
            pips = None
            if current["type"] == "buy":
                if bar["high"] >= current["tp"]:
                    exit_price, pips = current["tp"], (current["tp"] - current["entry"]) / PIP
                elif current["sl"] is not None and bar["low"] <= current["sl"]:
                    exit_price, pips = current["sl"], (current["sl"] - current["entry"]) / PIP
            else:
                if bar["low"] <= current["tp"]:
                    exit_price, pips = current["tp"], (current["entry"] - current["tp"]) / PIP
                elif current["sl"] is not None and bar["high"] >= current["sl"]:
                    exit_price, pips = current["sl"], (current["entry"] - current["sl"]) / PIP
            if exit_price is not None:
                profit = pips * current["pv"]
                balance += profit
                if profit > 0:
                    wins += 1; gross_win += profit
                elif profit < 0:
                    losses += 1; gross_loss += abs(profit)
                positions.append({**current, "exit_i": i, "exit_price": exit_price,
                                  "profit": profit})
                current = None
                if balance > peak: peak = balance
                dd = peak - balance
                maxdd_pct = max(maxdd_pct, (dd / peak * 100) if peak > 0 else 0)
        if balance > peak: peak = balance
        dd = peak - balance
        maxdd_pct = max(maxdd_pct, (dd / peak * 100) if peak > 0 else 0)
    # end-of-data: open position dropped (engine parity)
    total = len(positions)
    wr = (wins / total * 100) if total else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    roi = ((balance - initial) / initial * 100)
    return {"roi": roi, "winrate": wr, "total_trades": total,
            "profit_factor": pf, "max_drawdown": maxdd_pct,
            "final_balance": balance, "total_profit": balance - initial,
            "skipped_entries": skipped_entries}

# ---------- STEP 1: equivalence (fold-0 window, baseline combo, FIXED mode) ----------
sl0 = wslice(0)
wdf0 = wdf_of(sl0)
combo0 = {"atr_period": 10, "multiplier": 3.0, "length": 60, "length_mult": 6.0}
sig0 = bi.backtest_supertrend(SYMBOL, TF, len(wdf0), atr_period=10, multiplier=3.0,
                              candle_type='ha', df=sl0)['signal']
conf0 = bi.backtest_trend_ali(SYMBOL, TF, len(wdf0), length=60, length_mult=6.0,
                              mode='Hma', candle_type='ha', df=sl0)['trend']
sig0, conf0 = align(wdf0, sig0, conf0)
ref = hb.run_backtest(wdf0.copy(), list(sig0), list(conf0), symbol=SYMBOL, tf=TF,
                      backtest_days=30, use_risk_free=False,
                      risk_free_distance_pips=50.0, use_sl=True, sl_pips=100.0,
                      use_tp=True, tp_pips=200.0, close_opposite_position=False,
                      initial_balance=INITIAL_BALANCE, position_size_mode='risk_percent',
                      fixed_lot_size=0.01, risk_percent=2, risk_based_on='initial')
mine = harness_backtest(wdf0, sig0, conf0, mode="fixed")
eq = (ref["roi"] == mine["roi"] and ref["winrate"] == mine["winrate"] and
      ref["total_trades"] == mine["total_trades"] and
      ref["profit_factor"] == mine["profit_factor"] and
      ref["final_balance"] == mine["final_balance"])
log("STEP1 harness equivalence (fixed mode): %s | ref=%s | mine=%s"
    % (eq, {k: ref[k] for k in ("roi", "winrate", "total_trades", "profit_factor")},
       {k: mine[k] for k in ("roi", "winrate", "total_trades", "profit_factor")}))
if not eq:
    print("[FAIL] harness is not equivalent to the project engine - STOP")
    sys.exit(1)

# ---------- STEP 2: walk-forward with ATR exits ----------
GRID = [{"atr_period": a, "multiplier": m, "length": 60, "length_mult": 6.0}
        for a in (10, 14, 20) for m in (2.5, 3.0, 3.5)]
GRID += [{"atr_period": 10, "multiplier": 3.0, "length": L, "length_mult": 6.0}
         for L in (40, 80)]

folds = []
for f in range(N_FOLDS):
    is_sl, oos_sl = wslice(f), wslice(f + 1)
    is_df, oos_df = wdf_of(is_sl), wdf_of(oos_sl)
    atr_is = pandas_ta.atr(is_df["high"], is_df["low"], is_df["close"], length=ATR_LEN)
    atr_oos = pandas_ta.atr(oos_df["high"], oos_df["low"], oos_df["close"], length=ATR_LEN)
    log("FOLD %d: IS=%s..%s | OOS=%s..%s"
        % (f + 1, is_df["time"].iloc[0], is_df["time"].iloc[-1],
           oos_df["time"].iloc[0], oos_df["time"].iloc[-1]))
    is_table = []
    for gi, combo in enumerate(GRID):
        wdf = is_df
        sig = bi.backtest_supertrend(SYMBOL, TF, len(wdf), atr_period=combo["atr_period"],
                                     multiplier=combo["multiplier"], candle_type='ha',
                                     df=is_sl)['signal']
        conf = bi.backtest_trend_ali(SYMBOL, TF, len(wdf), length=combo["length"],
                                     length_mult=combo["length_mult"], mode='Hma',
                                     candle_type='ha', df=is_sl)['trend']
        sig, conf = align(wdf, sig, conf)
        r = harness_backtest(wdf, sig, conf, mode="atr", atr=atr_is.tolist())
        is_table.append({"combo": combo, "is": r})
        log("  IS combo %2d/%d atr=%s mult=%s len=%s -> trades=%s roi=%.2f pf=%.2f"
            % (gi + 1, len(GRID), combo["atr_period"], combo["multiplier"],
               combo["length"], r["total_trades"], r["roi"], r["profit_factor"]))
    eligible = [t for t in is_table if t["is"]["total_trades"] >= MIN_IS_TRADES]
    if not eligible:
        log("  [fold %d] THIN_IS - OOS skipped" % (f + 1))
        folds.append({"fold": f + 1, "status": "THIN_IS", "is_table": is_table})
        continue
    best = max(eligible, key=lambda t: (t["is"]["roi"], t["is"]["total_trades"],
                                        t["is"]["profit_factor"]))
    log("  selected (IS-only): atr=%s mult=%s len=%s | IS roi=%.2f trades=%s"
        % (best["combo"]["atr_period"], best["combo"]["multiplier"],
           best["combo"]["length"], best["is"]["roi"], best["is"]["total_trades"]))
    owdf = oos_df
    osig = bi.backtest_supertrend(SYMBOL, TF, len(owdf), atr_period=best["combo"]["atr_period"],
                                  multiplier=best["combo"]["multiplier"], candle_type='ha',
                                  df=oos_sl)['signal']
    oconf = bi.backtest_trend_ali(SYMBOL, TF, len(owdf), length=best["combo"]["length"],
                                  length_mult=best["combo"]["length_mult"], mode='Hma',
                                  candle_type='ha', df=oos_sl)['trend']
    osig, oconf = align(owdf, osig, oconf)
    oos = harness_backtest(owdf, osig, oconf, mode="atr", atr=atr_oos.tolist())
    log("  OOS (frozen): roi=%.2f wr=%.2f pf=%.2f maxdd=%.2f"
        % (oos["roi"], oos["winrate"], oos["profit_factor"], oos["max_drawdown"]))
    folds.append({"fold": f + 1, "status": "OK",
                  "is_bounds": [str(is_df["time"].iloc[0]), str(is_df["time"].iloc[-1])],
                  "oos_bounds": [str(oos_df["time"].iloc[0]), str(oos_df["time"].iloc[-1])],
                  "selected_combo": best["combo"], "is": best["is"], "oos": oos,
                  "degradation_roi": oos["roi"] - best["is"]["roi"],
                  "is_table": is_table})

# ---------- aggregate + verdict per user rule ----------
ok_folds = [f for f in folds if f.get("status") == "OK"]
pos_is = sum(1 for f in ok_folds if f["is"]["roi"] > 0)
oos_rois = [f["oos"]["roi"] for f in ok_folds if f["oos"]]
oos_pos = sum(1 for x in oos_rois if x > 0)
oos_neg = len(oos_rois) - oos_pos
exp_oos = [f["oos"]["total_profit"] / f["oos"]["total_trades"]
           for f in ok_folds if f["oos"] and f["oos"]["total_trades"]]

if pos_is < (len(ok_folds) / 2):
    branch = "ENTRY-LOGIC PROBLEM -> CP3 redesign (different entry filter/logic)"
else:
    branch = "EXIT-GEOMETRY WAS THE PROBLEM -> rerun CP4 with ATR exits + fuller grid"

lines = ["CP4b B0 DIAGNOSTIC - ATR-BASED EXITS (SL=2xATR14, TP=3xATR14) - %s" % datetime.now(),
         "harness equivalence (fixed mode vs run_backtest): %s" % eq,
         "folds=%d | IS-only selection | min %d IS trades" % (len(ok_folds), MIN_IS_TRADES),
         "", header := "%-5s %-13s %9s %9s %9s %9s %10s" % ("Fold", "Sel(ST/TA)", "IS_ROI", "OOS_ROI", "OOS_TR", "OOS_PF", "Degrad.")]
lines.append(header); lines.append("-" * len(header))
for f in ok_folds:
    c = f["selected_combo"]
    lines.append("%-5s %-13s %9.2f %9.2f %9.0f %9.2f %10.2f"
                 % (f["fold"], "%s/%s" % (c["atr_period"], c["length"]),
                    f["is"]["roi"], f["oos"]["roi"], f["oos"]["total_trades"],
                    f["oos"]["profit_factor"], f["degradation_roi"]))
lines.append("")
lines.append("folds with POSITIVE best-IS ROI: %d/%d" % (pos_is, len(ok_folds)))
if oos_rois:
    lines.append("OOS: profitable=%d losing=%d avg=%.2f" % (oos_pos, oos_neg, sum(oos_rois) / len(oos_rois)))
if exp_oos:
    lines.append("OOS expectancy avg=%.2f $/trade" % (sum(exp_oos) / len(exp_oos)))
lines.append("")
lines.append("BRANCH VERDICT: %s" % branch)
result = "\n".join(lines)

with open(os.path.join(CACHE, "cp4b_atr_results.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "mode": "B0 ATR exits",
               "harness_equivalence": eq, "folds": folds, "pos_is_folds": pos_is,
               "oos_rois": oos_rois, "branch": branch}, f, indent=2, default=str, ensure_ascii=False)
with open(os.path.join(CACHE, "cp4b_atr_results.md"), "w", encoding="utf-8") as f:
    f.write(result)

print("\n" + "=" * 70)
print(result)
print("=" * 70)
print("[saved] project_audit/stability_windows_cache/cp4b_atr_results.md|.json")
print("B0 COMPLETE")
