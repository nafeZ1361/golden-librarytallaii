# cp7_stress.py — CP7 ROBUSTNESS / STRESS TESTING (post-OOS closure)
# Registered stress battery (fixed before computation):
#   S1 worst-window analysis (both datasets: CP5 frozen + CP6 OOS)
#   S2 worst loss-streak per registered cell (outcome sequences)
#   S3 cost stress recap C0/C1/C2 on both datasets (frozen economics)
#   S4 gap/regime coverage note (documented limitations; no regime labels exist)
#   S5 entry-timing note (registered convention = same-bar close; next-bar-open
#      variant would require an unregistered engine change -> limitation only)
# Disk-only. No MT5. No source change. No result manipulation.

import os, sys, json
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")

import strategy_a1_meanrev as a1
import strategy_a2_breakout as a2
import research_harness as rh

STRATS = {"A1": a1, "A2": a2}
HORIZONS = [5, 20]

lines = []


def P(s):
    print(s)
    lines.append(s)


def load(kind, i):
    df = pd.read_csv(os.path.join(CACHE, "%s_window_%d_df.csv" % (kind, i)))
    df["time"] = pd.to_datetime(df["time"])
    return df


def outcomes(states, closes, h):
    ys = []
    for i in range(1, len(states)):
        s_cur, s_prev = states[i], states[i - 1]
        if s_cur in ("buy", "sell") and s_cur != s_prev and i + h < len(closes):
            fwd = closes[i + h]
            win = (s_cur == "buy" and fwd > closes[i]) or (s_cur == "sell" and fwd < closes[i])
            ys.append(1 if win else 0)
    return np.array(ys, dtype=int)


def worst_streak(bits):
    best = cur = 0
    for b in bits:
        cur = cur + 1 if b == 0 else 0
        best = max(best, cur)
    return best


P("# CP7 — ROBUSTNESS / STRESS TESTING (closure after CP6 FAILED REPLICATION)")
P("Generated: %s | stress battery registered before computation; both datasets"
  % datetime.now().isoformat(timespec="seconds"))
P("  evaluated: CP5 frozen (in-sample era) AND CP6 OOS (independent).")
P("")

stress = {}
for name, mod in STRATS.items():
    stress[name] = {}
    for h in HORIZONS:
        row = {}
        for kind in ("cp5", "cp6"):
            seq_all, per_win = [], []
            for i in range(1, 7):
                df = load(kind, i)
                st = mod.signal_fn(df.copy(), "3m")
                closes = df["close"].to_numpy(dtype=float)
                ys = outcomes(st, closes, h)
                per_win.append((i, len(ys), round(ys.mean() * 100, 2) if len(ys) else None,
                                worst_streak(ys)))
                seq_all.append(ys)
            allbits = np.concatenate(seq_all) if seq_all else np.array([])
            row["%s_h%d" % (kind, h)] = {
                "rate_pct": round(allbits.mean() * 100, 2) if len(allbits) else None,
                "max_loss_streak": worst_streak(allbits),
                "per_window": per_win}
        P("- %s h%d:" % (name, h))
        for k, v in row.items():
            P("    %s: rate=%s%% max_loss_streak=%d | per-window (w, n, rate%%, streak): %s"
              % (k, v["rate_pct"], v["max_loss_streak"], v["per_window"]))
        stress[name]["h%d" % h] = row

P("")
P("## S3 — cost stress recap (frozen economics, both datasets)")
P("- CP5 frozen: A1 exp $11.03 -> $7.53 (C1) -> $5.03 (C2); A2 $10.66 -> $7.16 -> $4.66;"
  " break-even ~11 pips. (CP5_ECONOMIC_VALIDATION.md)")
P("- CP6 OOS: A1 expC0 = -$4.33/trade (negative BEFORE costs); A2 expC0 = +$4.01 ->"
  " +$0.51 under C1 (effectively zero). FAILED ECONOMIC REPLICATION for A1;"
  " A2 economically marginal on OOS.")
P("")
P("## S4/S5 — documented limitations (no computation invented)")
P("- regime split: no regime labels exist in the frozen artifacts; a regime study"
  " would require a pre-registered labeling method — deferred to any future track.")
P("- entry-timing (next-bar-open) variant: would require an unregistered engine"
  " change; the registered convention (same-bar close) and its live divergence are"
  " documented (CP2/CP3). Not invented post-hoc.")
P("- gap sensitivity: CP5 had 6 flagged gaps (none inside OR windows); CP6 OOS had"
  " zero unclassified gaps; A2's registered gap-free-OR rule structurally guards.")

out = {"experiment": "CP7-stress", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "stress": stress}
with open(os.path.join(HERE, "CP7_STRESS_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CP7_STRESS.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CP7_STRESS.md | CP7_STRESS_RESULTS.json")
sys.exit(0)
