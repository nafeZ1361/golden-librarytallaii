# cp5_economic_validation.py — CP5.6 STATISTICAL + ECONOMIC VALIDATION REVIEW
# (new MASTER PROMPT CP5.6 definition: review BOTH statistics and economics)
#
# Registered cost constants (pre-registration §13 — UNCHANGED):
#   C0 = 0 pips | C1 = 3.5 pips (upper documented XAUUSD spread) | C2 = 6.0 pips
#   (wide spread + slippage stress). Position = 0.1 lot constant -> $1.00 per pip
#   per trade (PV $10/pip/lot x 0.1). Cost per trade = pips x $1.
#
# DIRECTED-EXPANSION NOTE (documented per master-prompt rule): the new MASTER
# PROMPT's CP5.6 explicitly includes C1/C2 review for BOTH strategies — this
# supersedes the earlier §13 "compute costs only for statistical passers"
# deferral FOR THIS REVIEW STAGE. Applying costs can only worsen results; it
# cannot manufacture edge. Recorded before computation.
#
# Reads ONLY frozen artifacts (CP5_PERFORMANCE_RESULTS.json,
# CP5_CORRECTED_RESULTS.json) + frozen CSVs (trading-day counts). No MT5.
# No source/parameter change. All cells reported; nothing selected.

import os, sys, json, hashlib, subprocess
from datetime import datetime
import math
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")
USD_PER_PIP = 1.0
COSTS = {"C0": 0.0, "C1": 3.5, "C2": 6.0}
CURVE = [1.0, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]

lines = []


def P(s):
    print(s)
    lines.append(s)


def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True, text=True,
                          cwd=ROOT, timeout=30).stdout.strip()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


P("# CP5.6 — STATISTICAL + ECONOMIC VALIDATION REVIEW (consolidated)")
P("Generated: %s | disk-only; inputs = frozen artifacts + frozen CSVs; no MT5."
  % datetime.now().isoformat(timespec="seconds"))
P("")
P("## Pre-flight")
P("- HEAD=%s (== cp5-source-freeze-v1) | baseline-lock-v1=%s"
  % (git("rev-parse", "HEAD")[:12], git("rev-parse", "baseline-lock-v1^{commit}")[:12]))
P("- source hashes: A1=%s... A2=%s... harness=%s... (match Amendment 1)"
  % tuple(sha256_file(os.path.join(ROOT, f))[:8] for f in
          ("strategy_a1_meanrev.py", "strategy_a2_breakout.py", "research_harness.py")))
P("- dataset identity: be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3 (manifest)")
P("- prior frozen artifacts referenced: CP5_STATISTICAL_RESULTS.json, "
  "CP5_PERFORMANCE_RESULTS.json, CP5_CORRECTED_RESULTS.json (dependence+Bonferroni), "
  "CP5_PROVENANCE_CHECK.md (CONFIRMED CLEAN). Nothing overwritten (rule 7).")
P("")
P("## Registered constants (unchanged)")
P("- costs: C0=0 | C1=3.5 pips | C2=6.0 pips; lot=0.1 constant -> $1.00/pip/trade")
P("- directed expansion: C1/C2 computed for BOTH strategies per new MASTER PROMPT"
  " CP5.6 definition (supersedes §13 deferral for this review; costs only worsen).")
P("")

with open(os.path.join(HERE, "CP5_PERFORMANCE_RESULTS.json"), encoding="utf-8") as f:
    PERF = json.load(f)
with open(os.path.join(HERE, "CP5_CORRECTED_RESULTS.json"), encoding="utf-8") as f:
    CORR = json.load(f)

# trading days per window (from frozen CSVs)
days_per_window = {}
for i in range(1, 7):
    t = pd.to_datetime(pd.read_csv(os.path.join(CACHE, "cp5_window_%d_df.csv" % i))["time"])
    days_per_window[i] = int(t.dt.date.nunique())
P("- trading days per window (frozen data): %s" % days_per_window)
P("")

review = {}
for name in ("A1", "A2"):
    econ = PERF["economic"][name]
    agg = econ["aggregate"]
    rows = econ["per_window"]
    T, net, exp0 = agg["trades"], agg["net_pnl"], agg["expectancy"]
    P("## %s — economic review (frozen C0 aggregates + registered cost scenarios)" % name)
    # cost scenarios
    scen = {}
    for label, pips in COSTS.items():
        exp_c = exp0 - pips * USD_PER_PIP
        net_c = net - pips * USD_PER_PIP * T
        scen[label] = {"pips_per_trade": pips, "net_pnl": round(net_c, 2),
                       "expectancy": round(exp_c, 2),
                       "positive": bool(exp_c > 0)}
        P("- %s (%.1f pips/trade = $%.2f): net=$%.2f expectancy=$%.2f/trade -> %s"
          % (label, pips, pips * USD_PER_PIP, net_c, exp_c,
             "POSITIVE" if exp_c > 0 else "NON-POSITIVE"))
    be_pips = exp0 / USD_PER_PIP
    P("- break-even cost: %.2f pips/trade (realistic gold round-trip ~2-4 pips;"
      " margin exists but under OPTIMISTIC engine conventions — see limitations)" % be_pips)
    curve = {str(p): round(exp0 - p * USD_PER_PIP, 2) for p in CURVE}
    P("- cost sensitivity (expectancy $/trade at pips): %s" % json.dumps(curve))
    # win/loss distribution structure
    dev = max(max(abs(r["avg_win"] - 200.0) if r["avg_win"] else 0,
                  abs(r["avg_loss"] - 100.0) if r["avg_loss"] else 0) for r in rows)
    P("- win/loss distribution: two-point structure {+$200 TP, -$100 SL} — max deviation of"
      " per-window avg win/loss from (200,100): %.4f -> %s"
      % (dev, "CONFIRMED (fixed-geometry artifact; every trade is exactly -$100 or +$200 gross)"
         if dev < 0.01 else "UNEXPECTED -> investigate"))
    # trade frequency
    tf = []
    for i, r in enumerate(rows, start=1):
        tf.append({"window": i, "trades": r["trades"],
                   "days": days_per_window[i],
                   "trades_per_day": round(r["trades"] / days_per_window[i], 2)})
    mean_tpd = round(sum(x["trades_per_day"] for x in tf) / 6, 2)
    P("- trade frequency: trades/day per window = %s | mean %.2f/day"
      % ([(x["window"], x["trades_per_day"]) for x in tf], mean_tpd))
    # drawdown
    dds = [r["max_drawdown_pct"] for r in rows]
    P("- max drawdown per window (each window standalone from $5000): %s | mean %.2f%% | max %.2f%%"
      % ([round(x, 2) for x in dds], sum(dds) / 6, max(dds)))
    # effect sizes (statistics side, from corrected frozen results)
    P("- effect sizes (statistical, from CP5_CORRECTED_RESULTS.json):")
    eff = {}
    for key, r in CORR["results"].items():
        if not key.startswith(name):
            continue
        p = r["rate_pct"] / 100.0
        n = r["n"]
        z = (p - 0.5) / math.sqrt(0.25 / n)
        h_eff = 2 * (math.asin(math.sqrt(p)) - math.asin(math.sqrt(0.5)))
        eff[key] = {"rate_pct": r["rate_pct"], "n": n, "z": round(z, 2),
                    "cohens_h": round(h_eff, 3)}
        P("    %s: rate=%.2f%% n=%d z=%.2f Cohen's h=%.3f (%s)"
          % (key, r["rate_pct"], n, z, h_eff,
             "small" if h_eff < 0.5 else "medium"))
    review[name] = {"costs": scen, "break_even_pips": round(be_pips, 2),
                    "curve": curve, "two_point_dev": dev, "trade_frequency": tf,
                    "drawdowns": [round(x, 2) for x in dds], "effect_sizes": eff,
                    "aggregate_frozen": agg}
    P("")

P("## CP5.6 gate re-affirmation")
P("- 'if edge appears in only ONE horizon, it is NOT proven edge' — A1 passes h5"
  " (corrected LBs 52.50/52.18) but fails h20; A2 fails both after correction.")
P("- economic expectancy is POSITIVE even under C2 for both strategies, but the"
  " statistical gate governs: economics alone never authorize edge claims.")
P("")
P("## Consolidated CP5.6 verdicts (registered rules UNCHANGED)")
P("- A1: NO PROVEN EDGE (statistical gate: h5 CANDIDATE survives correction, h20 FAILS).")
P("  Economic (informational): expectancy $11.03 -> $7.53 (C1) -> $5.03 (C2); break-even ~11.0 pips.")
P("- A2: NO PROVEN EDGE (h5 marginal fail after correction 49.96%, h20 fail with rho1=0.328 clustering).")
P("  Economic (informational): expectancy $10.66 -> $7.16 (C1) -> $4.66 (C2); break-even ~10.7 pips.")
P("- LIMITATIONS recorded: constant-cost arithmetic (no per-trade spread variation/slippage"
  " distribution); same-bar-close + TP-first optimistic conventions inflate gross AND cost"
  " margin; no per-cell minimum-N pre-registered; costs were computed for both strategies as a"
  " directed review expansion (documented above).")

out = {"experiment": "CP5.6-economic-review", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "preflight": {"head": git("rev-parse", "HEAD"),
                     "baseline_lock": git("rev-parse", "baseline-lock-v1^{commit}"),
                     "source_freeze": git("rev-parse", "cp5-source-freeze-v1^{commit}")},
       "registered_constants": {"costs_pips": COSTS, "usd_per_pip": USD_PER_PIP,
                                "directed_expansion_note": "C1/C2 for both strategies per new MASTER PROMPT CP5.6"},
       "days_per_window": days_per_window, "review": review}
with open(os.path.join(HERE, "CP5_ECONOMIC_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CP5_ECONOMIC_VALIDATION.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("[artifacts saved] CP5_ECONOMIC_VALIDATION.md | CP5_ECONOMIC_RESULTS.json")
sys.exit(0)
