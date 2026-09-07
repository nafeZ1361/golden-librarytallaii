# cp5_source_validation.py
# CP5 Methodology Finalization - source-change validation for F1 (NaN guard)
# and F4 (OR eligibility). Uses the Sep-3 frozen control windows as REGRESSION
# FIXTURES only (NOT CP5 data). Reports STRUCTURAL facts exclusively: state
# hashes, event counts, day attribution. NO hit-rate, NO PnL, NO performance -
# performance measurement is forbidden until the data-freeze gate passes.
# Usage:  python cp5_source_validation.py PRE   (before source edits)
#         python cp5_source_validation.py POST  (after source edits)

import sys, os, json, hashlib, glob
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
TAG = sys.argv[1] if len(sys.argv) > 1 else "RUN"

import strategy_a1_meanrev as a1
import strategy_a2_breakout as a2


def h(states):
    return hashlib.sha256(json.dumps(states).encode()).hexdigest()[:16]


def events(states):
    return [i for i, s in enumerate(states) if s in ("buy", "sell")]


# ---- independent re-implementation of the REGISTERED OR-eligibility rule
# (verification oracle - does not import strategy internals) ---------------
OR_BARS = {"3m": 40, "15m": 8, "1h": 2}
TF_MIN = {"3m": 3, "15m": 15, "1h": 60}
BREAK_SEC = 30 * 60  # registered threshold; empirical day-start gap ~63 min


def eligible_days(df, tf="3m"):
    t = pd.to_datetime(df["time"])
    tsec = (t.astype("int64") // 10**9).tolist()
    days = t.dt.date.tolist()
    out, i, n = set(), 0, len(df)
    ob = OR_BARS[tf]
    while i < n:
        j = i
        while j < n and days[j] == days[i]:
            j += 1
        or_end = i + ob
        ok = (i > 0
              and days[i - 1] != days[i]
              and (tsec[i] - tsec[i - 1]) >= BREAK_SEC
              and or_end <= j
              and (tsec[or_end - 1] - tsec[i]) == (ob - 1) * TF_MIN[tf] * 60)
        if ok:
            out.add(days[i])
        i = j
    return out


lines = []


def P(s):
    print(s)
    lines.append(s)


P("# CP5 SOURCE VALIDATION - %s run" % TAG)
P("Fixtures: frozen Sep-3 control windows (regression fixtures only, NOT CP5 data).")
P("Structural facts only: hashes / counts / day attribution. No performance metrics.")

files = sorted(glob.glob(os.path.join(ROOT, "project_audit",
                                      "stability_windows_cache", "window_*_df.csv")))
res = {"tag": TAG, "windows": []}
for f in files:
    df = pd.read_csv(f)
    df["time"] = pd.to_datetime(df["time"])
    wname = os.path.basename(f)
    s1 = a1.signal_fn(df, "3m")
    s2 = a2.signal_fn(df, "3m")
    e1, e2 = events(s1), events(s2)
    days = df["time"].dt.date.tolist()
    e2_days = sorted({days[i] for i in e2})
    elig = eligible_days(df)
    bad_days = [str(d) for d in e2_days if d not in elig]
    rec = {"window": wname, "rows": len(df),
           "a1_hash": h(s1), "a1_events": len(e1),
           "a2_hash": h(s2), "a2_event_bars": len(e2),
           "a2_event_days": len(e2_days),
           "total_days": int(df["time"].dt.date.nunique()),
           "eligible_days": len(elig),
           "a2_event_days_on_ineligible": bad_days}
    res["windows"].append(rec)
    P("%s: A1 hash=%s events=%d | A2 hash=%s event_bars=%d event_days=%d "
      "(days: %d/%d eligible) ineligible_event_days=%d"
      % (wname, rec["a1_hash"], rec["a1_events"], rec["a2_hash"],
         rec["a2_event_bars"], rec["a2_event_days"], rec["eligible_days"],
         rec["total_days"], len(bad_days)))

# ---- F1 synthetic NaN robustness (window 1 head set to NaN) ---------------
df1 = pd.read_csv(files[0])
df1["time"] = pd.to_datetime(df1["time"])
dfn = df1.copy()
dfn.loc[0:24, "close"] = float("nan")
try:
    sn = a1.signal_fn(dfn, "3m")
    first30_hold = all(s == "hold" for s in sn[:30])
    len_ok = len(sn) == len(dfn)
    P("A1 NaN synthetic: no_crash=True first30_all_hold=%s len_ok=%s hash=%s"
      % (first30_hold, len_ok, h(sn)))
    res["a1_nan_test"] = {"no_crash": True, "first30_all_hold": first30_hold,
                          "len_ok": len_ok, "hash": h(sn)}
except Exception as ex:  # noqa: BLE001 - the whole point is to observe crashes
    P("A1 NaN synthetic: CRASH: %r" % (ex,))
    res["a1_nan_test"] = {"no_crash": False, "error": repr(ex)}

out = os.path.join(ROOT, "project_audit", "CP5_source_validation_%s.md" % TAG)
with open(out, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n\n```json\n"
             + json.dumps(res, indent=1, default=str) + "\n```\n")
P("[saved] %s" % out)
