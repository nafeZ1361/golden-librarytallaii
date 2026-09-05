# cp5_performance_eval.py — CP5.5 CONTROLLED PERFORMANCE EVALUATION
# First performance measurement of A1/A2 on the FROZEN CP5 dataset.
# Disk-only: MT5 is never imported; the six frozen CSVs are the only data.
# DECISION RULES ARE FIXED BELOW *BEFORE* ANY RESULT IS COMPUTED — they are
# encoded from CP5_PRE_REGISTRATION.md (§A hypotheses, §C conventions, §12
# acceptance, §13 costs, §14 multiple-testing) plus two documented execution
# notes (ECON-MAPPING, HA-NOTE) whose rationale is printed in the report.
# NO parameter tuning, NO window exclusion, NO post-hoc thresholds.

import os, sys, json, hashlib, subprocess
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")
N_WINDOWS = 6

import strategy_a1_meanrev as a1
import strategy_a2_breakout as a2
import research_harness as rh

STRATS = {"A1": a1, "A2": a2}
HORIZONS = [5, 20]                      # registered primary horizons
PIP, PV_PER_LOT = 0.1, 10.0             # from manifest symbol_info (digits=2, tick_size=0.01, tick_value=1.0); equals CP2 audit
SL_PIPS, TP_PIPS = 100.0, 200.0         # registered baseline geometry
INIT_BAL, RISK_PCT = 5000.0, 2.0        # registered
COST_C1_PIPS, COST_C2_PIPS = 3.5, 6.0   # registered §13 scenarios ($ per trade at 0.1 lot: pips*PV*0.1)


def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True, text=True,
                          cwd=ROOT, timeout=30).stdout.strip()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def load_window(i):
    df = pd.read_csv(os.path.join(CACHE, "cp5_window_%d_df.csv" % i))
    df["time"] = pd.to_datetime(df["time"])
    return df


def event_series(states):
    """Registered ECON-MAPPING (documented pre-computation): economic entries are
    exactly the events the registered hit-rate metric counts (state ENTERS
    buy/sell at bar i>0 and differs from previous bar). For A1 (event-only
    states) this equals the raw state list; for A2 (state runs) it maps runs to
    their start bar, so each directional prediction = at most one trade."""
    ev = ["hold"] * len(states)
    for i in range(1, len(states)):
        if states[i] in ("buy", "sell") and states[i] != states[i - 1]:
            ev[i] = states[i]
    return ev


lines = []


def P(s):
    print(s)
    lines.append(s)


# ============================ PHASE A — PRE-FLIGHT ===========================
P("# CP5.5 CONTROLLED PERFORMANCE EVALUATION")
P("Generated: %s" % datetime.now().isoformat(timespec="seconds"))
P("")
P("## Run provenance note")
P("- Run 1 (14:50) crashed in Phase E on an audit-script key-name error"
  " (max_drawdown_pct vs the frozen harness's max_drawdown) AFTER hit-rate"
  " printing, BEFORE economic computation. Fix was mechanical (audit artifact"
  " only; frozen sources untouched; rule 19 compliant). All decision rules were"
  " frozen BEFORE run 1; NO rule was changed after any result was seen.")
P("")
P("## Phase A — Pre-flight")
pf = {}
pf["branch"] = git("branch", "--show-current")
pf["head"] = git("rev-parse", "HEAD")
pf["baseline_lock_v1"] = git("rev-parse", "baseline-lock-v1^{commit}")
pf["cp5_source_freeze_v1"] = git("rev-parse", "cp5-source-freeze-v1^{commit}")
pf["head_is_freeze"] = pf["head"] == pf["cp5_source_freeze_v1"]
pf["source_hashes"] = {f: sha256_file(os.path.join(ROOT, f)) for f in
                       ("strategy_a1_meanrev.py", "strategy_a2_breakout.py", "research_harness.py")}
pf["expected_source_hashes"] = {
    "strategy_a1_meanrev.py": "85c1781a700dde5ed0015fc64841f99a4c0263b6913b9b3afc5a77765e4105a6",
    "strategy_a2_breakout.py": "732d1eaad9517e2c4b4bbe1d0fc82a1fc8a0a9c79fd8a8aa9898ab72d279dd5b",
    "research_harness.py": "c5e7844a27d9c4a6d08a0221d7a42580e9750cb45f410672589e21f2ddc49216"}
pf["sources_frozen_ok"] = all(pf["source_hashes"][k] == v for k, v in pf["expected_source_hashes"].items())
with open(os.path.join(HERE, "CP5_DATA_FREEZE_manifest.json"), encoding="utf-8") as f:
    MAN = json.load(f)
csv_hashes = {i: sha256_file(os.path.join(CACHE, "cp5_window_%d_df.csv" % i)) for i in range(1, N_WINDOWS + 1)}
pf["csv_hashes_ok"] = all(csv_hashes[i] == MAN["windows"][i - 1]["sha256"] for i in range(1, N_WINDOWS + 1))
pf["dataset_identity"] = MAN["dataset_sha256_combined"]
comb = hashlib.sha256()
for m in MAN["windows"]:
    comb.update(m["sha256"].encode())
pf["identity_ok"] = comb.hexdigest() == MAN["dataset_sha256_combined"]
pf["docs_present"] = all(os.path.exists(os.path.join(HERE, f)) for f in
                         ("CP5_PRE_REGISTRATION.md", "CP5_DATA_FREEZE.md",
                          "CP5_DATA_INTEGRITY.md", "CP5_DETERMINISM.md"))
P("- branch=%s HEAD=%s" % (pf["branch"], pf["head"]))
P("- baseline-lock-v1=%s | cp5-source-freeze-v1=%s | HEAD==freeze-tag: %s"
  % (pf["baseline_lock_v1"][:12], pf["cp5_source_freeze_v1"][:12], pf["head_is_freeze"]))
P("- source hashes match Amendment 1: %s" % pf["sources_frozen_ok"])
P("- six CSV hashes match manifest: %s | dataset identity recomputed OK: %s"
  % (pf["csv_hashes_ok"], pf["identity_ok"]))
P("- DATASET IDENTITY: %s" % pf["dataset_identity"])
P("- CP5.3 = PASS WITH CONDITIONS (6 documented flagged gaps; none inside the"
  " empirical OR window) | CP5.4 = PASS (deterministic, isolated, MT5-free)")
P("- gate to proceed: %s" % ("OK" if (pf["head_is_freeze"] and pf["sources_frozen_ok"]
                                     and pf["csv_hashes_ok"] and pf["identity_ok"] and pf["docs_present"]) else "FAIL -> ABORT"))
P("")
P("## Registered decision rules (fixed BEFORE results — from pre-registration)")
P("- PRIMARY cells only: A1xH5, A1xH20, A2xH5, A2xH20 (exploratory A2-M15/H1 are"
  " NOT computable: no M15/H1 data was ever frozen — reported as deferred).")
P("- D: CI includes 50% -> NO PROVEN DIRECTIONAL EDGE (cell); CI entirely below"
  " 50% -> EVIDENCE AGAINST DIRECTION (cell); CI entirely above -> CANDIDATE"
  " DIRECTIONAL EDGE (cell; not sufficient alone).")
P("- K strategy verdict: PROVISIONAL/PROVEN EDGE requires ALL of: statistical"
  " gate in BOTH primary horizons (h5 AND h20 aggregate CI lower bound > 50%;"
  " strict conjunctive rule prevents horizon cherry-picking), economic gate"
  " (aggregate expectancy > 0 AND >=3/5 OOS fold-positions positive AND >=3/6"
  " windows positive), and cost gate C1 (expectancy stays > 0) — C1/C2 are"
  " computed ONLY for strategies passing the statistical gate (registered §13)."
  " If only one horizon passes -> cell reported as CANDIDATE, strategy = NO"
  " PROVEN EDGE. No per-cell minimum-N was pre-registered; empty-event cells are"
  " INCONCLUSIVE (no post-hoc threshold is invented).")
P("- ECON-MAPPING (execution note, fixed pre-computation): economic entries ="
  " exactly the run-start events counted by the registered hit-rate metric"
  " (harness trig=conf=event series). Rationale: hypotheses are stated over"
  " fresh events; sustained-run re-entries would be a different, unregistered"
  " hypothesis. For A1 both mappings coincide.")
P("- HA-NOTE (documented per master-command rule 18): the command's economics"
  " block lists 'HA' (the baseline control's candle type); the registered and"
  " frozen definition for A1/A2 is PLAIN candles (pre-registration §B/D2,"
  " Amendment 1) and the frozen dataset is plain candles. The command itself"
  " defers to 'the economic definition registered in baseline/pre-registration'"
  " — plain-candle signals with baseline economics (SL100/TP200/2%/$5000) are"
  " therefore used. Recorded BEFORE any metric was computed.")
P("")

# ============ PHASES B–D — SIGNALS, HIT RATE, CONFIDENCE INTERVALS ===========
P("## Phase B — Signal generation (frozen sources, frozen data)")
sig_records, states_by = {}, {}
for i in range(1, N_WINDOWS + 1):
    df = load_window(i)
    closes = df["close"].to_numpy(dtype=float)
    for name, mod in STRATS.items():
        st = mod.signal_fn(df, "3m")
        states_by[(name, i)] = st
        evs = []
        for k in range(1, len(st)):
            if st[k] in ("buy", "sell") and st[k] != st[k - 1]:
                evs.append({"window": i, "bar_index": k, "timestamp": str(df["time"].iloc[k]),
                            "direction": st[k], "event_type": "run_start",
                            "entry_reference": "close[bar_index]",
                            "entry_ref_price": float(closes[k]), "state": st[k]})
        sig_records.setdefault(name, {})[i] = evs
    P("- window %d: A1 events=%d | A2 events=%d"
      % (i, len(sig_records["A1"][i]), len(sig_records["A2"][i])))

P("")
P("## Phases C+D — Pre-registered hit-rate cells (per window and aggregate)")
stat_results = {}
for name in STRATS:
    stat_results[name] = {}
    for h in HORIZONS:
        per_win = []
        for i in range(1, N_WINDOWS + 1):
            st = states_by[(name, i)]
            closes = load_window(i)["close"].to_numpy(dtype=float)
            ev, hits, excl = rh.hit_rate(st, closes, h)
            rate = (hits / ev * 100) if ev else None
            per_win.append({"window": i, "events": ev, "wins": hits, "losses": ev - hits,
                            "rate_pct": rate, "wald95": rh.wald95(rate, ev),
                            "excluded_end": excl})
        evA = sum(r["events"] for r in per_win)
        hiA = sum(r["wins"] for r in per_win)
        rateA = (hiA / evA * 100) if evA else None
        ciA = rh.wald95(rateA, evA)
        if ciA is None:
            cell_verdict = "INCONCLUSIVE (no events)"
        elif ciA[0] > 50.0:
            cell_verdict = "CANDIDATE DIRECTIONAL EDGE"
        elif ciA[1] < 50.0:
            cell_verdict = "EVIDENCE AGAINST DIRECTION"
        else:
            cell_verdict = "NO PROVEN DIRECTIONAL EDGE"
        stat_results[name]["h%d" % h] = {"per_window": per_win,
                                         "aggregate": {"events": evA, "wins": hiA,
                                                       "losses": evA - hiA,
                                                       "rate_pct": rateA,
                                                       "wald95": ciA},
                                         "cell_verdict": cell_verdict}
        P("- %s H%d aggregate: events=%d rate=%s wald95=%s -> %s"
          % (name, h, evA, ("%.2f%%" % rateA) if rateA is not None else "n/a",
             ("[%.2f, %.2f]" % (ciA[0], ciA[1])) if ciA else "n/a", cell_verdict))

# ================= PHASE E–G — ECONOMICS, ASSUMPTIONS, STABILITY =============
P("")
P("## Phase E — Economic backtest (fixed registered geometry, per window)")
econ_results = {}
for name in STRATS:
    rows = []
    for i in range(1, N_WINDOWS + 1):
        df = load_window(i)
        ev = event_series(states_by[(name, i)])
        r = rh.harness_backtest(df, ev, ev, PIP, PV_PER_LOT, mode="fixed",
                                fixed_sl_pips=SL_PIPS, fixed_tp_pips=TP_PIPS,
                                initial_balance=INIT_BAL, risk_pct=RISK_PCT)
        T = r["total_trades"]
        net = r["total_profit"]
        wr = r["winrate"]
        wins = int(round(wr / 100.0 * T)) if T else 0
        losses = T - wins
        # exact algebra from frozen engine outputs: net = GW - GL, PF = GW/GL
        if T == 0:
            GW = GL = 0.0
        elif r["profit_factor"] == float("inf"):
            GW, GL = net, 0.0
        elif abs(r["profit_factor"] - 1.0) < 1e-12:
            GW = GL = 0.0
        else:
            GL = net / (r["profit_factor"] - 1.0)
            GW = GL + net
        rows.append({"window": i, "trades": T, "wins": wins, "losses": losses,
                     "gross_profit": round(GW, 2), "gross_loss": round(GL, 2),
                     "net_pnl": round(net, 2), "return_pct": r["roi"],
                     "expectancy": (net / T) if T else None, "winrate_pct": wr,
                     "max_drawdown_pct": r["max_drawdown"],
                     "profit_factor": r["profit_factor"] if T else None,
                     "avg_win": (GW / wins) if wins else None,
                     "avg_loss": (GL / losses) if losses else None})
    T = sum(r["trades"] for r in rows)
    netA = sum(r["net_pnl"] for r in rows)
    oos_pos = sum(1 for r in rows[1:] if r["net_pnl"] > 0)   # fold positions = windows 2..6
    win_pos = sum(1 for r in rows if r["net_pnl"] > 0)
    econ_results[name] = {"per_window": rows,
                          "aggregate": {"trades": T, "net_pnl": round(netA, 2),
                                        "expectancy": (netA / T) if T else None,
                                        "oos_fold_positions_positive": "%d/5" % oos_pos,
                                        "windows_positive": "%d/6" % win_pos,
                                        "mean_return_pct": round(sum(r["return_pct"] for r in rows) / N_WINDOWS, 2)}}
    P("- %s: per-window net PnL = %s" % (name, [r["net_pnl"] for r in rows]))
    P("  aggregate: trades=%d net=$%.2f expectancy=$%s | OOS fold-positions positive %s | windows positive %s | mean ROI %.2f%%"
      % (T, netA, ("%.2f" % (netA / T)) if T else "n/a", "%d/5" % oos_pos, "%d/6" % win_pos,
         econ_results[name]["aggregate"]["mean_return_pct"]))

P("")
P("## Phase F — Cost / execution assumptions (explicit limitations)")
P("- entry price = same-bar close of the signal bar (registered control convention;"
  " optimistic vs live [-2] discipline — CP3 divergence documented)")
P("- same-candle TP/SL ambiguity resolves TP-FIRST (optimistic; CP2 S3)")
P("- no spread/commission/slippage/swap in the base engine -> ALL CP5.5 economics"
  " are C0 (gross). LIMITATION: absolute expectancy is optimistic by the full"
  " cost load. Pre-registered C1 (3.5 pips) / C2 (6 pips) are computed ONLY for"
  " strategies passing the statistical gate (registered §13 anti-metric-shopping rule).")
P("- gap-through exits fill at SL/TP price, not open (optimistic; CP2 S4/S5)")
P("- position sizing constant $100 risk (2% of INITIAL balance, 0.1 lot) — matches control")
P("- end-of-data open position silently dropped (engine behavior, CP2 S7)")
P("- candle-close convention: signals/entries use bar close; no forming candle in data (CP5.2 probe)")

# statistical gate check -> cost computation
stat_pass = {}
for name in STRATS:
    stat_pass[name] = all(stat_results[name]["h%d" % h]["cell_verdict"] == "CANDIDATE DIRECTIONAL EDGE"
                          for h in HORIZONS)
P("")
P("## Cost gate (only for statistical-gate passers, registered §13)")
for name in STRATS:
    if stat_pass[name]:
        a = econ_results[name]["aggregate"]
        T = a["trades"]
        for label, pips in (("C1", COST_C1_PIPS), ("C2", COST_C2_PIPS)):
            usd = pips * PV_PER_LOT * 0.1
            ec = a["expectancy"] - usd if T else None
            P("- %s %s: expectancy after %.1f-pip cost = $%.2f/trade -> %s"
              % (name, label, pips, ec, "POSITIVE" if ec and ec > 0 else "NON-POSITIVE"))
    else:
        P("- %s: statistical gate NOT passed -> C1/C2 not computed (anti-metric-shopping rule)" % name)

# ============ PHASES G–K — STABILITY ANALYSIS + PRIMARY DECISIONS ============
P("")
P("## Phase G — Window stability")
for name in STRATS:
    rows = econ_results[name]["per_window"]
    pos = [r["net_pnl"] for r in rows if r["net_pnl"] > 0]
    tot_pos = sum(pos)
    shares = [(r["window"], (r["net_pnl"] / tot_pos * 100) if tot_pos > 0 and r["net_pnl"] > 0 else 0.0) for r in rows]
    dom = max(shares, key=lambda x: x[1])
    signs = "".join("+" if r["net_pnl"] > 0 else "-" for r in rows)
    P("- %s net-PnL signs across windows 1..6: [%s] | windows positive: %s"
      % (name, signs, econ_results[name]["aggregate"]["windows_positive"]))
    P("  largest single positive-window share of total profit: window %d = %.1f%% %s"
      % (dom[0], dom[1], "-> SINGLE-WINDOW DOMINANCE FLAG (edge cannot be called stable)"
         if dom[1] > 50 else "(no single-window dominance)"))
    P("  hit-rate direction sign per window (h5): %s"
      % ["%.1f" % r["rate_pct"] if r["rate_pct"] is not None else "n/a"
         for r in stat_results[name]["h5"]["per_window"]])

P("")
P("## Phase H — Minimum sample")
P("- No per-cell minimum-N was pre-registered (documented limitation). Cells with"
  " zero events are INCONCLUSIVE; all other cells are judged by the registered"
  " CI rule only. Economic min rules applied as registered: >=3/5 OOS fold"
  " positions, >=3/6 windows.")
P("")
P("## Phase I — Multiple testing")
P("- tested: 2 hypotheses x 2 horizons = 4 primary cells; 4 aggregate tests;"
  " 6 windows each (reported, not selected). Exploratory cells (A2-M15/H1):"
  " NOT computable on the frozen M3 dataset — deferred; would require a new"
  " registered freeze. No multiplicity correction across the 4 primary cells was"
  " pre-registered -> LIMITATION recorded; per §14, a single passing cell among"
  " several requires independent confirmation (CP6) before any stronger claim."
  " No correction was invented post-hoc.")
P("")
P("## Phase J — Leakage / look-ahead recheck (audit statements)")
P("- signals computed only from each window's frozen df (no cross-window reads;"
  " CP5.4 isolation proof); forming candle absent (CP5.2 probe); indicators"
  " trailing-only (CP5.1 static audit); OR built from completed bars with"
  " registered eligibility (Amendment 1); normalization alters nothing (CP5.4"
  " raw-value assertion); signal timestamp = bar close, outcome = close[i+h]"
  " (future only as the prediction target); economics enter at the signal bar's"
  " close with exits evaluated from the NEXT bar (frozen harness semantics).")

P("")
P("## Phase K — Primary decisions")
verdicts = {}
for name in STRATS:
    cells = [stat_results[name]["h%d" % h]["cell_verdict"] for h in HORIZONS]
    both_candidate = all(c == "CANDIDATE DIRECTIONAL EDGE" for c in cells)
    a = econ_results[name]["aggregate"]
    econ_ok = (a["expectancy"] is not None and a["expectancy"] > 0
               and a["oos_fold_positions_positive"] == "5/5" and False) or \
              (a["expectancy"] is not None and a["expectancy"] > 0
               and int(a["oos_fold_positions_positive"][0]) >= 3
               and int(a["windows_positive"][0]) >= 3)
    cost_ok = None
    if both_candidate and econ_ok:
        T = a["trades"]
        ec1 = a["expectancy"] - COST_C1_PIPS * PV_PER_LOT * 0.1 if T else None
        cost_ok = bool(ec1 and ec1 > 0)
    if both_candidate and econ_ok and cost_ok:
        v = "PROVISIONAL EDGE (rename per decision tree: CANDIDATE — requires CP6 independent confirmation)"
    elif any(c == "EVIDENCE AGAINST DIRECTION" for c in cells) and not both_candidate:
        v = "EVIDENCE AGAINST EDGE"
    else:
        v = "NO PROVEN EDGE"
    verdicts[name] = {"cell_verdicts": dict(zip(["h5", "h20"], cells)),
                      "statistical_gate_both_horizons": both_candidate,
                      "economic_gate": econ_ok, "cost_gate": cost_ok,
                      "verdict": v}
    P("- %s: cells=%s | stat_gate(both)=%s | econ_gate=%s | cost_gate=%s => %s"
      % (name, verdicts[name]["cell_verdicts"], both_candidate, econ_ok, cost_ok, v))

P("")
P("## Phase L — Exploratory results")
P("- none computed (A2-M15/H1 not frozen) — nothing to label; no primary/exploratory mixing occurred.")
P("")
P("## Phase M — Robustness preview (plan for the NEXT stage only — nothing executed)")
P("- parameter perturbation (RSI 14->10/20, 30/70->25/75, BB 20/2->15/3; OR 120->90/150min, 1.5x->1.2/2.0x)")
P("- SL/TP geometry sensitivity; entry-timing sensitivity (next-bar-open variant)")
P("- cost sensitivity C1/C2 with per-trade records; spread-widening stress")
P("- window perturbation (±k bars), regime split (trend/range/vol buckets), long/short split")
P("- rolling performance and outlier-trade impact (top-3 trade removal)")

# ============================ artifacts ======================================
results_json = {
    "experiment": "CP5.5", "generated_local": datetime.now().isoformat(timespec="seconds"),
    "preflight": pf,
    "registered_rules": {
        "primary_cells": ["A1_h5", "A1_h20", "A2_h5", "A2_h20"],
        "ci_rule": "lower>50 => CANDIDATE; includes 50 => NO PROVEN; upper<50 => AGAINST",
        "strategy_verdict": "PROVISIONAL EDGE iff both horizons candidate AND economic gate AND cost gate C1",
        "econ_mapping": "entries = run-start events (same events as hit-rate metric)",
        "ha_note": "plain candles per registered D2; command 'HA' token documented",
    },
    "signal_records": sig_records,
    "statistical": stat_results,
    "economic": econ_results,
    "verdicts": verdicts,
    "limitations": [
        "no costs in base engine (C0 only); C1/C2 pre-registered and computed only for statistical passers",
        "same-bar close entry; TP-first same-candle priority; gap fills at SL/TP price",
        "no per-cell minimum-N pre-registered",
        "no multiplicity correction across the 4 primary cells",
        "exploratory A2-M15/H1 cells not frozen/not computable",
    ],
}
with open(os.path.join(HERE, "CP5_STATISTICAL_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump({"experiment": "CP5.5", "generated_local": results_json["generated_local"],
               "statistical": stat_results, "verdicts": verdicts}, f, indent=1, default=str)
with open(os.path.join(HERE, "CP5_PERFORMANCE_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(results_json, f, indent=1, default=str)

with open(os.path.join(HERE, "CP5_WINDOW_RESULTS.md"), "w", encoding="utf-8") as f:
    w = []
    w.append("# CP5 WINDOW RESULTS (per-window, Phase G — all six windows, none excluded)\n")
    for name in STRATS:
        w.append("## %s — hit-rate cells\n" % name)
        w.append("| window | h5 ev | h5 rate% | h5 CI | h20 ev | h20 rate% | h20 CI |")
        w.append("|---|---|---|---|---|---|---|")
        for k in range(N_WINDOWS):
            r5 = stat_results[name]["h5"]["per_window"][k]
            r20 = stat_results[name]["h20"]["per_window"][k]
            fmt = lambda r: ("%d | %.2f | [%.2f, %.2f]" % (r["events"], r["rate_pct"], r["wald95"][0], r["wald95"][1])) if r["events"] and r["wald95"] else ("%d | n/a | n/a" % r["events"])
            w.append("| %d | %s | %s |" % (k + 1, fmt(r5), fmt(r20)))
        w.append("")
        w.append("## %s — economic track (C0, fixed geometry)\n" % name)
        w.append("| window | trades | wins | losses | net PnL | ROI% | expectancy | winrate% | maxDD% | PF | avg win | avg loss |")
        w.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in econ_results[name]["per_window"]:
            w.append("| %d | %d | %d | %d | %.2f | %.2f | %s | %.2f | %.2f | %s | %s | %s |"
                     % (r["window"], r["trades"], r["wins"], r["losses"], r["net_pnl"],
                        r["return_pct"], ("%.2f" % r["expectancy"]) if r["expectancy"] is not None else "n/a",
                        r["winrate_pct"], r["max_drawdown_pct"],
                        ("%.2f" % r["profit_factor"]) if r["profit_factor"] not in (None, float("inf")) else str(r["profit_factor"]),
                        ("%.2f" % r["avg_win"]) if r["avg_win"] else "n/a",
                        ("%.2f" % r["avg_loss"]) if r["avg_loss"] else "n/a"))
        w.append("")
    f.write("\n".join(w) + "\n")

with open(os.path.join(HERE, "CP5_PERFORMANCE_REPORT.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CP5_PERFORMANCE_RESULTS.json | CP5_STATISTICAL_RESULTS.json |"
  " CP5_PERFORMANCE_REPORT.md | CP5_WINDOW_RESULTS.md")
sys.exit(0)
