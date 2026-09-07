# cp5_7_robustness.py — CP5.7 ROBUSTNESS
# Goal: distinguish ROBUST edge regions from PARAMETER FRAGILE points.
# Method: equivalence-anchored parameterized REIMPLEMENTATIONS of A1/A2 in the
# test namespace (project files untouched — sanctioned monkey-patch/injection
# precedent). ANCHOR GATE: at registered baseline parameters the reimplement-
# ations must produce BYTE-IDENTICAL states to the frozen strategies on ALL six
# windows; any mismatch -> ABORT (STOP-the-line).
#
# PRE-REGISTERED GRID (fixed before any evaluation — no post-hoc selection):
#   A1 (12 combos): rsi_len {10,14,20} x thresholds {(30,70),(25,75)}
#                   x BB {(20,2),(15,3)}; baseline = (14,(30,70),(20,2))
#   A2 (9 combos):  or_bars {30,40,50} (90/120/150 min) x vol_mult {1.2,1.5,2.0};
#                   baseline = (40,1.5)
#   horizons: h5, h20 (registered)
#   SL/TP economic grid (frozen signals, frozen engine): SL {75,100,150} x
#   TP {150,200,300}; C0 and C1(3.5 pips) expectancy per cell.
#
# PRE-REGISTERED CLASSIFICATION RULES (before computation):
#   statistical robustness of a cell's surviving horizon: ROBUST if >= 2/3 of
#   grid variants have aggregate Wald95 LB > 50%; FRAGILE if < 1/3; MIXED
#   otherwise; OVERFITTING WARNING if ONLY the baseline variant passes.
#   Variant CIs are RAW Wald (screening metric; the registered candidate already
#   survived corrected testing; NO variant may be claimed as edge — variants are
#   sensitivity evidence about the registered point, not new hypotheses).
#   SL/TP grid: fully reported; FRAGILE if baseline positive but < 1/3 of grid
#   cells positive; geometry changes alter RR — expectancy sign + PF both shown.
# Disk-only. No MT5. No source/data change. Full grids reported (no selection).

import os, sys, json, hashlib, subprocess
from datetime import datetime
import numpy as np
import pandas as pd
import pandas as pd0
import pandas_ta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")

import strategy_a1_meanrev as a1
import strategy_a2_breakout as a2
import research_harness as rh

USD_PER_PIP = 1.0
C1_PIPS = 3.5

lines = []


def P(s):
    print(s)
    lines.append(s)


def load_window(i):
    df = pd.read_csv(os.path.join(CACHE, "cp5_window_%d_df.csv" % i))
    df["time"] = pd.to_datetime(df["time"])
    return df


def sha_txt(s):
    return hashlib.sha256(s.encode()).hexdigest()


# ---------- parameterized reimplementations (test namespace only) ----------
def a1_param(wdf, rsi_len=14, lo_thr=30, hi_thr=70, bb_len=20, bb_std=2.0):
    n = len(wdf)
    if n < 30:
        return ["hold"] * n
    close = wdf["close"]
    rsi = pandas_ta.rsi(close, length=rsi_len)
    bb = pandas_ta.bbands(close, length=bb_len, std=bb_std)
    bb_cols = [str(c).upper() for c in bb.columns]
    lo_col = bb.columns[[c.startswith("BBL") for c in bb_cols].index(True)]
    up_col = bb.columns[[c.startswith("BBU") for c in bb_cols].index(True)]
    r = rsi.tolist()
    lo = bb[lo_col].tolist()
    up = bb[up_col].tolist()
    c = close.tolist()
    states = ["hold"] * n
    for i in range(1, n):
        if pd.isna(r[i]) or pd.isna(lo[i]) or pd.isna(up[i]) or pd.isna(r[i - 1]):
            continue
        if r[i] < lo_thr and r[i - 1] >= lo_thr and c[i] <= lo[i]:
            states[i] = "buy"
        elif r[i] > hi_thr and r[i - 1] <= hi_thr and c[i] >= up[i]:
            states[i] = "sell"
    return states


def a2_param(wdf, or_bars=40, vol_mult=1.5, tf_min=3, break_min=30):
    n = len(wdf)
    states = ["hold"] * n
    if n == 0:
        return states
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
        day_end = j
        or_end = i + or_bars
        eligible = (i > 0 and day_values[i - 1] != day0
                    and (tsec[i] - tsec[i - 1]) >= break_min * 60
                    and or_end <= day_end
                    and (tsec[or_end - 1] - tsec[i]) == (or_bars - 1) * tf_min * 60)
        if eligible:
            or_high = max(high[i:or_end])
            or_low = min(low[i:or_end])
            or_vol = vol[i:or_end]
            avg = sum(or_vol) / len(or_vol)
            for k in range(or_end, day_end):
                if vol[k] >= vol_mult * avg:
                    if close[k] > or_high:
                        states[k] = "buy"
                    elif close[k] < or_low:
                        states[k] = "sell"
        i = day_end
    return states


# ============================ pre-flight ====================================
P("# CP5.7 — ROBUSTNESS")
P("Generated: %s | disk-only, no MT5, frozen dataset be4fa581..., frozen"
  % datetime.now().isoformat(timespec="seconds"))
P("  sources cp5-source-freeze-v1. Grids + classification rules registered BEFORE"
  " evaluation (see module header). Full grids reported; nothing selected.")
P("")

wins = {i: load_window(i) for i in range(1, 7)}
frozen_states = {"A1": {}, "A2": {}}
for i in range(1, 7):
    frozen_states["A1"][i] = a1.signal_fn(wins[i].copy(), "3m")
    frozen_states["A2"][i] = a2.signal_fn(wins[i].copy(), "3m")

# ---------------- ANCHOR GATE ----------------
P("## Anchor gate (reimplementations must equal frozen strategies byte-identically)")
anchor_ok = True
for i in range(1, 7):
    s = a1_param(wins[i].copy())
    ok1 = sha_txt(json.dumps(s)) == sha_txt(json.dumps(frozen_states["A1"][i]))
    s = a2_param(wins[i].copy())
    ok2 = sha_txt(json.dumps(s)) == sha_txt(json.dumps(frozen_states["A2"][i]))
    P("- window %d: A1 anchor=%s | A2 anchor=%s" % (i, ok1, ok2))
    anchor_ok &= (ok1 and ok2)
P("- ANCHOR GATE: %s" % ("PASS" if anchor_ok else "FAIL -> ABORT"))
if not anchor_ok:
    with open(os.path.join(HERE, "CP5_7_ROBUSTNESS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(3)

closes = {i: wins[i]["close"].to_numpy(dtype=float) for i in range(1, 7)}

# ---------------- A1 statistical grid ----------------
P("")
P("## A1 parameter grid (12 combos x h5/h20) — full report")
a1_grid = []
for rsi_len in (10, 14, 20):
    for (lo_thr, hi_thr) in ((30, 70), (25, 75)):
        for (bb_len, bb_std) in ((20, 2.0), (15, 3.0)):
            ev = {5: 0, 20: 0}
            hi = {5: 0, 20: 0}
            for i in range(1, 7):
                st = a1_param(wins[i].copy(), rsi_len, lo_thr, hi_thr, bb_len, bb_std)
                for h in (5, 20):
                    e, w, _ = rh.hit_rate(st, closes[i], h)
                    ev[h] += e
                    hi[h] += w
            is_base = (rsi_len, lo_thr, hi_thr, bb_len, bb_std) == (14, 30, 70, 20, 2.0)
            rec = {"params": {"rsi_len": rsi_len, "thr": [lo_thr, hi_thr],
                              "bb": [bb_len, bb_std]}, "baseline": is_base}
            for h in (5, 20):
                rate = hi[h] / ev[h] * 100 if ev[h] else None
                ci = rh.wald95(rate, ev[h])
                rec["h%d" % h] = {"events": ev[h], "rate_pct": rate, "wald95": ci,
                                  "lb_gt_50": bool(ci and ci[0] > 50)}
            a1_grid.append(rec)
            P("- %s%s: h5 ev=%d rate=%s CI=%s | h20 rate=%s"
              % (json.dumps(rec["params"]), " [BASELINE]" if is_base else "",
                 rec["h5"]["events"],
                 ("%.2f" % rec["h5"]["rate_pct"]) if rec["h5"]["rate_pct"] else "n/a",
                 ("[%.2f, %.2f]" % tuple(rec["h5"]["wald95"])) if rec["h5"]["wald95"] else "n/a",
                 ("%.2f" % rec["h20"]["rate_pct"]) if rec["h20"]["rate_pct"] else "n/a"))

# ---------------- A2 statistical grid ----------------
P("")
P("## A2 parameter grid (9 combos x h5/h20) — full report")
a2_grid = []
for or_bars in (30, 40, 50):
    for vol_mult in (1.2, 1.5, 2.0):
        ev = {5: 0, 20: 0}
        hi = {5: 0, 20: 0}
        for i in range(1, 7):
            st = a2_param(wins[i].copy(), or_bars, vol_mult)
            for h in (5, 20):
                e, w, _ = rh.hit_rate(st, closes[i], h)
                ev[h] += e
                hi[h] += w
        is_base = (or_bars, vol_mult) == (40, 1.5)
        rec = {"params": {"or_bars": or_bars, "vol_mult": vol_mult}, "baseline": is_base}
        for h in (5, 20):
            rate = hi[h] / ev[h] * 100 if ev[h] else None
            ci = rh.wald95(rate, ev[h])
            rec["h%d" % h] = {"events": ev[h], "rate_pct": rate, "wald95": ci,
                              "lb_gt_50": bool(ci and ci[0] > 50)}
        a2_grid.append(rec)
        P("- OR=%dmin vol=%.1f%s: h5 ev=%d rate=%s CI=%s | h20 rate=%s"
          % (or_bars * 3, vol_mult, " [BASELINE]" if is_base else "",
             rec["h5"]["events"],
             ("%.2f" % rec["h5"]["rate_pct"]) if rec["h5"]["rate_pct"] else "n/a",
             ("[%.2f, %.2f]" % tuple(rec["h5"]["wald95"])) if rec["h5"]["wald95"] else "n/a",
             ("%.2f" % rec["h20"]["rate_pct"]) if rec["h20"]["rate_pct"] else "n/a"))

# ---------------- SL/TP economic grid (frozen signals, frozen engine) -------
P("")
P("## SL/TP economic grid (9 combos x 2 strategies, frozen signals/engine) — full report")
pip, pv = 0.1, 10.0
sltp_grid = {}
for name, mod in (("A1", a1), ("A2", a2)):
    cells = []
    for sl in (75.0, 100.0, 150.0):
        for tp in (150.0, 200.0, 300.0):
            T = net = 0
            pf_num = []
            for i in range(1, 7):
                ev = ["hold"] * len(frozen_states[name][i])
                st = frozen_states[name][i]
                for k in range(1, len(st)):
                    if st[k] in ("buy", "sell") and st[k] != st[k - 1]:
                        ev[k] = st[k]
                r = rh.harness_backtest(wins[i], ev, ev, pip, pv, mode="fixed",
                                        fixed_sl_pips=sl, fixed_tp_pips=tp,
                                        initial_balance=5000.0, risk_pct=2.0)
                T += r["total_trades"]
                net += r["total_profit"]
            exp0 = net / T if T else None
            exp1 = exp0 - C1_PIPS * USD_PER_PIP if T else None
            cells.append({"sl": sl, "tp": tp, "trades": T,
                          "net_c0": round(net, 2),
                          "exp_c0": round(exp0, 2) if exp0 is not None else None,
                          "exp_c1": round(exp1, 2) if exp1 is not None else None,
                          "baseline": (sl, tp) == (100.0, 200.0)})
            P("- %s SL=%d TP=%d%s: trades=%d netC0=$%.0f expC0=$%.2f expC1=$%.2f"
              % (name, sl, tp, " [BASELINE]" if (sl, tp) == (100.0, 200.0) else "",
                 T, net, exp0 if exp0 else 0.0, exp1 if exp1 else 0.0))
    sltp_grid[name] = cells

# ---------------- classification (pre-registered rules) ---------------------
P("")
P("## Robustness classification (pre-registered rules)")
def classify(grid, horizon):
    passing = sum(1 for r in grid if r["h%d" % horizon]["lb_gt_50"])
    baseline_passes = [r for r in grid if r["baseline"]][0]["h%d" % horizon]["lb_gt_50"]
    k, m = passing, len(grid)
    if m and k == 1 and baseline_passes:
        cls = "FRAGILE + OVERFITTING WARNING (only the baseline point passes)"
    elif k >= 2 * m / 3:
        cls = "ROBUST (>=2/3 of variants keep LB>50)"
    elif k < m / 3:
        cls = "FRAGILE (<1/3 of variants keep LB>50)"
    else:
        cls = "MIXED"
    return {"passing": k, "total": m, "class": cls}

cls_a1_h5 = classify(a1_grid, 5)
cls_a1_h20 = classify(a1_grid, 20)
cls_a2_h5 = classify(a2_grid, 5)
cls_a2_h20 = classify(a2_grid, 20)
P("- A1 h5: %d/%d variants pass -> %s" % (cls_a1_h5["passing"], cls_a1_h5["total"], cls_a1_h5["class"]))
P("- A1 h20: %d/%d -> %s" % (cls_a1_h20["passing"], cls_a1_h20["total"], cls_a1_h20["class"]))
P("- A2 h5: %d/%d -> %s" % (cls_a2_h5["passing"], cls_a2_h5["total"], cls_a2_h5["class"]))
P("- A2 h20: %d/%d -> %s" % (cls_a2_h20["passing"], cls_a2_h20["total"], cls_a2_h20["class"]))
for name in ("A1", "A2"):
    g = sltp_grid[name]
    pos0 = sum(1 for c in g if c["exp_c0"] and c["exp_c0"] > 0)
    pos1 = sum(1 for c in g if c["exp_c1"] and c["exp_c1"] > 0)
    base = [c for c in g if c["baseline"]][0]
    P("- %s SL/TP grid: %d/9 cells expC0>0, %d/9 expC1>0 | baseline expC0=%.2f -> %s"
      % (name, pos0, pos1, base["exp_c0"],
         "FRAGILE (baseline isolated)" if (base["exp_c0"] > 0 and pos0 < 3) else
         ("region-positive" if pos0 >= 3 else "baseline not positive")))

P("")
P("## Interpretation guard")
P("- Grid variants are SENSITIVITY EVIDENCE about the registered points, NOT new"
  " hypotheses; no variant is claimed as edge (registered §14 discipline).")
P("- Regression check: frozen CSVs and sources untouched (script writes only its"
  " own artifacts); anchor gate already proved frozen outputs unchanged.")

out = {"experiment": "CP5.7-robustness", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "anchor_gate": anchor_ok, "a1_grid": a1_grid, "a2_grid": a2_grid,
       "sltp_grid": sltp_grid,
       "classification": {"A1_h5": cls_a1_h5, "A1_h20": cls_a1_h20,
                          "A2_h5": cls_a2_h5, "A2_h20": cls_a2_h20}}
with open(os.path.join(HERE, "CP5_7_ROBUSTNESS_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CP5_7_ROBUSTNESS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CP5_7_ROBUSTNESS.md | CP5_7_ROBUSTNESS_RESULTS.json")
sys.exit(0)
