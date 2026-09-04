# cp4e_a1a2_hitrate.py
# CP4e: hit-rate diagnostic for A1 (mean-reversion) and A2 (volume breakout)
# on the same 6 calendar windows, across M3 / M15 / H1 (all three, cheap).
# Raw comparison table + Wald 95% CI per aggregate. Gate: any aggregate CI
# fully above 50% qualifies that strategy/TF for a full CP4 walk-forward.

import os, sys, json
import numpy as np
import pandas as pd
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import MetaTrader5 as mt5
import research_harness as rh
import strategy_a1_meanrev as a1
import strategy_a2_breakout as a2

if not mt5.initialize():
    print("[error] MT5 unavailable")
    sys.exit(3)

STRATEGIES = {"A1_meanrev": a1.signal_fn, "A2_breakout": a2.signal_fn}
TFS = ("3m", "15m", "1h")
HORIZONS = (5, 20)

bounds = rh.window_bounds_from_m3(mt5, 6)
log = lambda m: print(m, flush=True)

all_rows = []
for tf in TFS:
    wins, _ = rh.load_windows(mt5, tf, 6, m3_boundaries=bounds)
    bars_str = "/".join(str(len(w)) for w in wins)
    log("[load] %s: %d windows (%s bars)" % (tf, len(wins), bars_str))
    for sname, sfn in STRATEGIES.items():
        rows = rh.hit_rate_diagnostic(wins, sfn, HORIZONS)
        for r in rows:
            r["tf"] = tf; r["strategy"] = sname
        all_rows.extend(rows)

# ---------- print per-window raw (M3) ----------
print("\n" + "=" * 78)
print("PER-WINDOW RAW (M3):")
header = "%-11s %4s %6s %6s %9s %8s" % ("Strategy", "H", "Evts", "Hits", "Rate%", "WaldHi")
print(header); print("-" * len(header))
for r in all_rows:
    if r["tf"] == "3m":
        print("%-11s %4d %6d %6d %9s %8.2f"
              % (r["strategy"], r["horizon"], r["events"], r["hits"],
                 ("%.2f" % r["rate_pct"]) if r["rate_pct"] is not None else "n/a",
                 r["wald95"][1] if r["wald95"] else 0))

# ---------- aggregates ----------
print("\nAGGREGATES (all 6 windows):")
aggr_header = "%-11s %-4s %4s %7s %9s  %-26s %s" % ("Strategy", "TF", "H", "Evts", "Rate%", "Wald95", "CI>50%?")
print(aggr_header); print("-" * len(aggr_header))
aggs = []
for sname in STRATEGIES:
    for tf in TFS:
        for h in HORIZONS:
            a = rh.aggregate_hr([r for r in all_rows
                                 if r["strategy"] == sname and r["tf"] == tf and r["horizon"] == h], h)
            ci_above = a["wald95"] is not None and a["wald95"][0] > 50.0
            aggs.append({**a, "strategy": sname, "tf": tf, "ci_above_50": ci_above})
            print("%-11s %-4s %4d %7d %9s  %-26s %s"
                  % (sname, tf, h, a["events"],
                     ("%.2f" % a["rate_pct"]) if a["rate_pct"] is not None else "n/a",
                     ("[%.2f%% - %.2f%%]" % (a["wald95"][0], a["wald95"][1])) if a["wald95"] else "n/a",
                     "YES" if ci_above else "no"))

qualified = [a for a in aggs if a["ci_above_50"]]
print("\nGATE: strategies/TFs with Wald95 CI fully above 50%: %s"
      % (["%s@%s h%d" % (a["strategy"], a["tf"], a["horizon"]) for a in qualified] or "NONE"))
result = "\n".join([json.dumps(aggs, indent=2, ensure_ascii=False)])

with open(os.path.join(CACHE := os.path.join(ROOT, "project_audit", "stability_windows_cache"),
                       "cp4e_a1a2_hitrate.json"), "w", encoding="utf-8") as f:
    json.dump({"created": datetime.now().isoformat(), "rows": all_rows,
               "aggregates": aggs, "qualified": [
                   {"strategy": a["strategy"], "tf": a["tf"], "horizon": a["horizon"]}
                   for a in qualified]}, f, indent=2, ensure_ascii=False)
with open(os.path.join(CACHE, "cp4e_a1a2_hitrate.md"), "w", encoding="utf-8") as f:
    f.write("CP4e A1/A2 hit-rate aggregates:\n\n" + aggr_header + "\n" +
            "\n".join("%-11s %-4s %4d %7d %9s  %-26s %s"
                      % (a["strategy"], a["tf"], a["horizon"], a["events"],
                         ("%.2f" % a["rate_pct"]) if a["rate_pct"] is not None else "n/a",
                         ("[%.2f%% - %.2f%%]" % (a["wald95"][0], a["wald95"][1])) if a["wald95"] else "n/a",
                         "YES" if a["ci_above_50"] else "no") for a in aggs))
print("[saved] project_audit/stability_windows_cache/cp4e_a1a2_hitrate.md|.json")
print("CP4e COMPLETE")
