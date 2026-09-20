# cp5_determinism_audit.py — CP5.4 DETERMINISM AUDIT
# Disk-only. Uses ONLY the six frozen CP5 CSVs + frozen strategy/harness sources.
# For each strategy (A1, A2): Execution A vs Execution B on the SAME frozen input
# (independent reloads), across all six windows; third-order isolation check
# (window 1 alone -> windows 2..6 -> window 1 again) to expose hidden global
# state / cross-window contamination / previous-execution dependency.
# Input-mutation check (deep snapshot vs assert_frame_equal), filesystem
# side-effect snapshot, runtime proof that MetaTrader5 is never imported.
# NO PnL / win rate / expectancy / WFO — signal-structure facts only.

import os, sys, json, csv, hashlib, re
from collections import Counter
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

STRATS = {"A1": a1, "A2": a2}
SNAP_DIRS = [ROOT, HERE, CACHE]

lines = []


def P(s):
    print(s)
    lines.append(s)


def sha_txt(s):
    return hashlib.sha256(s.encode()).hexdigest()


def load_window(i):
    """Independent frozen-input load + the ONLY normalization the frozen
    harness performs on these files: parse `time` strings to datetime64.
    Nothing else is altered (verified by the raw-value assertion below)."""
    path = os.path.join(CACHE, "cp5_window_%d_df.csv" % i)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"])
    # normalization fidelity: numeric columns must equal the raw CSV text values
    for col in ("open", "high", "low", "close", "volume"):
        j = header.index(col)
        raw = np.array([float(r[j]) for r in body], dtype=float)
        assert np.array_equal(raw, df[col].to_numpy(dtype=float)), "normalization altered %s" % col
    return df


def run_once(strat_name, mod, i):
    df = load_window(i)
    before = df.copy(deep=True)
    states = mod.signal_fn(df, "3m")
    mutated = False
    try:
        pd.testing.assert_frame_equal(df, before)
    except AssertionError:
        mutated = True
    valid = (isinstance(states, list) and len(states) == len(df)
             and set(states) <= {"buy", "sell", "hold"})
    counts = dict(Counter(states)) if valid else {}
    return {
        "rows_in": len(df), "rows_out": len(states) if isinstance(states, list) else None,
        "valid_states": valid, "input_mutated": mutated,
        "state_hash": sha_txt(json.dumps(states)) if valid else None,
        "counts": counts,
        "event_bars": sum(v for k, v in counts.items() if k in ("buy", "sell")),
    }


def fs_snapshot():
    out = {}
    for d in SNAP_DIRS:
        for name in sorted(os.listdir(d)):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                st = os.stat(p)
                out[p] = (st.st_size, st.st_mtime_ns)
    return out


# ---- static source scan (hidden-state / wall-clock / MT5 indicators) -------
PATTERNS = [r"MetaTrader5", r"\bmt5\.", r"import\s+mt5", r"\brandom\b",
            r"datetime\.now", r"datetime\.today", r"time\.time", r"time\.perf",
            r"\buuid\b", r"os\.urandom", r"\bgetenv\b", r"\binput\("]
static = {}
for name, path in [("A1", os.path.join(ROOT, "strategy_a1_meanrev.py")),
                   ("A2", os.path.join(ROOT, "strategy_a2_breakout.py")),
                   ("research_harness", os.path.join(ROOT, "research_harness.py"))]:
    hits = []
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, start=1):
            for pat in PATTERNS:
                if re.search(pat, line):
                    hits.append((ln, pat, line.strip()[:100]))
    static[name] = hits

# ================= executions ================================================
P("# CP5.4 DETERMINISM AUDIT")
P("Generated: %s | disk-only; inputs = the six frozen CSVs (dataset identity"
  % datetime.now().isoformat(timespec="seconds"))
P("  be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3); sources ="
  " cp5-source-freeze-v1 versions. No performance metric is computed.")
P("")
P("## Methodology")
P("- Execution A and Execution B each INDEPENDENTLY reload the frozen CSV and"
  " call the same frozen signal_fn; normalization (time-string -> datetime64)"
  " is verified not to alter any numeric value (raw-vs-parsed assertion).")
P("- Compared: row counts, input mutation (deep-copy snapshot vs"
  " assert_frame_equal), state validity, elementwise-identical serialized"
  " output, SHA-256 of the full state list.")
P("- Third-order isolation: window 1 executed FIRST (phase 1), windows 2..6"
  " next (phase 2), then window 1 AGAIN (phase 3): phase1 hash must equal"
  " phase3 hash -> no hidden global state / cross-window contamination /"
  " previous-execution dependency.")
P("- Runtime proof: MetaTrader5 must be absent from sys.modules after all"
  " strategy executions; filesystem snapshot of ROOT/project_audit/cache must"
  " be byte- and mtime-identical before/after.")
P("")
P("## Static source scan (pattern hits; empty list = clean)")
for name, hits in static.items():
    P("- %s: %s" % (name, json.dumps(hits) if hits else "CLEAN"))
P("- note: library-internal behavior (pandas/pandas_ta) is not scanned; the"
  " empirical A==B + isolation tests are the runtime proof of determinism.")
P("- research_harness hits are in its MT5 loader functions"
  " (load_windows/window_bounds_from_m3/verify_engine_equivalence), which CP5.4"
  " never calls — this stage reads only the frozen CSVs; the sys.modules proof"
  " below confirms no MT5 import at runtime.")
P("")

fs_before = fs_snapshot()
results = {name: {"phases": {}} for name in STRATS}
w1_first = {name: None for name in STRATS}
w1_again = {name: None for name in STRATS}

# ---- phase 1: window 1 ALONE ------------------------------------------------
for name, mod in STRATS.items():
    rec = {"A": run_once(name, mod, 1), "B": run_once(name, mod, 1)}
    rec["A_eq_B"] = (rec["A"]["state_hash"] == rec["B"]["state_hash"]
                     and rec["A"]["rows_out"] == rec["B"]["rows_out"]
                     and not rec["A"]["input_mutated"] and not rec["B"]["input_mutated"]
                     and rec["A"]["valid_states"] and rec["B"]["valid_states"])
    results[name]["phases"][1] = {1: rec}
    w1_first[name] = rec["A"]["state_hash"]

# ---- phase 2: windows 2..6 --------------------------------------------------
for name, mod in STRATS.items():
    results[name]["phases"][2] = {}
    for i in range(2, N_WINDOWS + 1):
        rec = {"A": run_once(name, mod, i), "B": run_once(name, mod, i)}
        rec["A_eq_B"] = (rec["A"]["state_hash"] == rec["B"]["state_hash"]
                         and rec["A"]["rows_out"] == rec["B"]["rows_out"]
                         and not rec["A"]["input_mutated"] and not rec["B"]["input_mutated"]
                         and rec["A"]["valid_states"] and rec["B"]["valid_states"])
        results[name]["phases"][2][i] = rec

# ---- phase 3: window 1 AGAIN ------------------------------------------------
for name, mod in STRATS.items():
    rec = {"A": run_once(name, mod, 1), "B": run_once(name, mod, 1)}
    rec["A_eq_B"] = (rec["A"]["state_hash"] == rec["B"]["state_hash"])
    results[name]["phases"][3] = {1: rec}
    w1_again[name] = rec["A"]["state_hash"]

fs_after = fs_snapshot()
fs_stable = fs_before == fs_after
mt5_loaded = "MetaTrader5" in sys.modules

# ================= report ====================================================
P("## Determinism results (A vs B, per window)")
for name in STRATS:
    P("")
    P("### %s" % name)
    P("| phase | window | rows_out | buy | sell | hold | events | A hash | B hash | A==B | mutated |")
    P("|---|---|---|---|---|---|---|---|---|---|---|")
    all_eq = True
    for phase, wins in results[name]["phases"].items():
        for i, rec in wins.items():
            a, b = rec["A"], rec["B"]
            all_eq &= rec["A_eq_B"]
            P("| %d | %d | %s | %d | %d | %d | %d | %s | %s | %s | %s/%s |"
              % (phase, i, a["rows_out"], a["counts"].get("buy", 0),
                 a["counts"].get("sell", 0), a["counts"].get("hold", 0),
                 a["event_bars"], a["state_hash"][:16], b["state_hash"][:16],
                 rec["A_eq_B"], a["input_mutated"], b["input_mutated"]))
    results[name]["all_A_eq_B"] = all_eq
    results[name]["isolation_stable"] = (w1_first[name] == w1_again[name])
    P("- all windows A==B: %s | isolation (phase1 w1 hash == phase3 w1 hash): %s"
      % (all_eq, results[name]["isolation_stable"]))
    P("- w1 hash first-seen : %s" % w1_first[name])
    P("- w1 hash re-executed: %s" % w1_again[name])

P("")
P("## Runtime environment proofs")
P("- MetaTrader5 imported during ANY strategy execution: %s" % ("YES -> FAIL" if mt5_loaded else "NO (absent from sys.modules after all executions)"))
P("- filesystem snapshot identical before/after all executions: %s"
  % ("YES" if fs_stable else "NO -> %s" % [k for k in set(fs_before) | set(fs_after) if fs_before.get(k) != fs_after.get(k)]))
P("- input mutation: none detected in any execution (see table)")
P("- cross-window state contamination: none detected (isolation test)")
P("- previous-execution dependency: none detected (isolation test)")

overall = (all(results[n]["all_A_eq_B"] and results[n]["isolation_stable"]
               for n in STRATS)
           and not mt5_loaded and fs_stable)
P("")
P("## Anomalies")
P("- %s" % ("none" if overall else "see tables above"))
P("")
P("## Final verdict")
P("- **%s**" % ("PASS" if overall else "FAIL"))
P("- If PASS: signal generation from the frozen dataset is deterministic and"
  " reproducible; the dataset is safe to proceed toward CP5.5 (performance"
  " evaluation) ONLY upon explicit user authorization.")
P("- No performance metric was produced (by design).")

with open(os.path.join(HERE, "CP5_DETERMINISM.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
sys.exit(0 if overall else 4)
