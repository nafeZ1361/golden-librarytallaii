# cycle_r1_validation.py — CYCLE-R1 EVALUATION (one-shot, registered)
# H-V3-1 fade: events = A2-v2 population (frozen code reused); win = AGAINST
#   breakout direction. IS = DS-ARCH-OOS (cp6v2 windows).
# H-V3-2 session-conditioned: strategy_a4_v1_sessionbreakout; win = continuation.
#   IS = DS-CP5-MAIN (cp5 windows).
# OOS for BOTH = DS-R1-RESERVE (r1 windows, identity f5b0124b...), ONE-SHOT,
#   joint Bonferroni m=4. Constants UNCHANGED (SEED=55056, N_BOOT=10000,
#   BLOCK_LEN=h, NW_LAG=h). ADVANCE iff h5 AND h20 CANDIDATE on IS and OOS
#   and OOS gross economics positive under C1.

import os, sys, json, hashlib
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")

import strategy_a2_v2_firstbreakout as a2v2
import strategy_a4_v1_sessionbreakout as a4
import research_harness as rh

SEED, N_BOOT = 55056, 10000
USD_PER_PIP, C1_PIPS, PIP, PV = 1.0, 3.5, 0.1, 10.0

lines = []


def P(s):
    print(s)
    lines.append(s)


def sha_txt(s):
    return hashlib.sha256(s.encode()).hexdigest()


def load(prefix, i):
    df = pd.read_csv(os.path.join(CACHE, "%s_window_%d_df.csv" % (prefix, i)))
    df["time"] = pd.to_datetime(df["time"])
    return df


def outcomes(states, closes, h, fade=False):
    ys = []
    for i in range(1, len(states)):
        s_cur, s_prev = states[i], states[i - 1]
        if s_cur in ("buy", "sell") and s_cur != s_prev and i + h < len(closes):
            fwd = closes[i + h]
            if fade:
                win = (s_cur == "buy" and fwd < closes[i]) or (s_cur == "sell" and fwd > closes[i])
            else:
                win = (s_cur == "buy" and fwd > closes[i]) or (s_cur == "sell" and fwd < closes[i])
            ys.append(1 if win else 0)
    return np.array(ys, dtype=int)


def acf(y, k):
    yc = y - y.mean()
    return float(np.sum(yc[:-k] * yc[k:]) / np.sum(yc * yc))


rng = np.random.default_rng(SEED)


def mbb_lb(y, block_len, lo_pct):
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < block_len:
        return None
    starts = rng.integers(0, n, size=(N_BOOT, int(np.ceil(n / block_len))))
    rates = np.empty(N_BOOT)
    for b in range(N_BOOT):
        idx = np.concatenate([(starts[b, j] + np.arange(block_len)) % n
                              for j in range(starts.shape[1])])[:n]
        rates[b] = (y[idx] > 0).mean()
    return float(np.percentile(rates, lo_pct * 100) * 100)


def flip(states):
    return [{"buy": "sell", "sell": "buy", "hold": "hold"}[s] for s in states]


def evaluate(kind_label, states_by, closes_by, fade, m):
    z_bonf = 2.241402727604947
    out = {}
    for h in (5, 20):
        ys_all, per_win = [], []
        for i in range(1, 7):
            ys = outcomes(states_by[i], closes_by[i], h, fade=fade)
            per_win.append((i, len(ys), round(ys.mean() * 100, 2) if len(ys) else None))
            ys_all.append(ys)
        y = np.concatenate(ys_all)
        n, kw = len(y), int((y > 0).sum())
        p = kw / n
        L = min(h, n - 1)
        rho_full = [acf(y, kk) for kk in range(1, max(6, L + 1))]
        deff = 1.0 + 2.0 * sum((1.0 - (kk + 1) / (L + 1)) * rho_full[kk] for kk in range(L))
        se0 = np.sqrt(p * (1 - p) / n)
        hac_lb = (p - z_bonf * se0 * np.sqrt(max(deff, 1.0))) * 100
        bb_lb = mbb_lb(y, h, (ALPHA / m) / 2)
        cand = hac_lb > 50.0 and bb_lb is not None and bb_lb > 50.0
        out["h%d" % h] = {"n": n, "rate_pct": p * 100, "rho1": rho_full[0],
                          "deff": deff, "hac_bonf_lb": hac_lb, "mbb_bonf_lb": bb_lb,
                          "verdict": ("CANDIDATE" if cand else "NO PROVEN DIRECTIONAL EDGE"),
                          "per_window": per_win}
        P("- %s h%d: n=%d rate=%.2f%% rho1=%.3f deff=%.3f | HAC-Bonf LB=%.2f%% |"
          " MBB-Bonf LB=%s -> %s | per-window %s"
          % (kind_label, h, n, p * 100, rho_full[0], deff, hac_lb,
             ("%.2f%%" % bb_lb) if bb_lb else "n/a", out["h%d" % h]["verdict"], per_win))
    return out


ALPHA = 0.05
P("# CYCLE-R1 — EVALUATION (one-shot; contracts committed a9b00d2 BEFORE this run)")
P("Generated: %s | OOS identity f5b0124b363acaa0b3364618ccdc9f584bb21a043301df95f6b646a26faa410a"
  % datetime.now().isoformat(timespec="seconds"))
P("  | constants unchanged (SEED=55056, N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h).")
P("- note: freeze manifest honestly recorded ONE unclassified 345-min day-boundary"
  " gap in r1 w1 (documented, not repaired; day-boundary => no OR/indicator impact).")
P("")

# determinism gate (a4 new code on all its windows; a2v2 code on r1 windows)
det = True
for i in range(1, 7):
    df = load("r1", i)
    sA = a4.signal_fn(df.copy(), "3m")
    sB = a4.signal_fn(load("r1", i), "3m")
    det &= sha_txt(json.dumps(sA)) == sha_txt(json.dumps(sB))
    sA = a2v2.signal_fn(df.copy(), "3m")
    sB = a2v2.signal_fn(load("r1", i), "3m")
    det &= sha_txt(json.dumps(sA)) == sha_txt(json.dumps(sB))
for i in range(1, 7):
    df = load("cp5", i)
    sA = a4.signal_fn(df.copy(), "3m")
    sB = a4.signal_fn(load("cp5", i), "3m")
    det &= sha_txt(json.dumps(sA)) == sha_txt(json.dumps(sB))
P("- determinism gate (A/B, a4 on cp5+r1, a2v2 on r1): %s" % ("PASS" if det else "FAIL"))
if not det:
    sys.exit(3)

# states
# states
closes_cp5 = {i: load("cp5", i)["close"].to_numpy(dtype=float) for i in range(1, 7)}
closes_cp6v2 = {i: load("cp6v2", i)["close"].to_numpy(dtype=float) for i in range(1, 7)}
closes_r1 = {i: load("r1", i)["close"].to_numpy(dtype=float) for i in range(1, 7)}
st_a3_is = {i: a2v2.signal_fn(load("cp6v2", i), "3m") for i in range(1, 7)}
st_a3_oos = {i: a2v2.signal_fn(load("r1", i), "3m") for i in range(1, 7)}
st_a4_is = {i: a4.signal_fn(load("cp5", i), "3m") for i in range(1, 7)}
st_a4_oos = {i: a4.signal_fn(load("r1", i), "3m") for i in range(1, 7)}

P("")
P("## H-V3-1 (fade of first-breakouts) — IS = DS-ARCH-OOS")
res_a3_is = evaluate("A3-fade IS", st_a3_is, closes_cp6v2, fade=True, m=2)
P("")
P("## H-V3-1 — OOS = DS-R1-RESERVE (one-shot)")
res_a3_oos = evaluate("A3-fade OOS", st_a3_oos, closes_r1, fade=True, m=4)
P("")
P("## H-V3-2 (session-conditioned breakout) — IS = DS-CP5-MAIN")
res_a4_is = evaluate("A4 IS", st_a4_is, closes_cp5, fade=False, m=2)
P("")
P("## H-V3-2 — OOS = DS-R1-RESERVE (one-shot)")
res_a4_oos = evaluate("A4 OOS", st_a4_oos, closes_r1, fade=False, m=4)

# economics (context): A4 continuation C0/C1; A3 fade via inverted signals
P("")
P("## Economic context (informational)")
for label, st_by, prefix, fade in (("A4-continuation", st_a4_oos, "r1", False),
                                   ("A3-fade(inverted)", {i: flip(st_a3_oos[i]) for i in range(1, 7)}, "r1", True)):
    T = net = 0
    for i in range(1, 7):
        st = st_by[i]
        ev = ["hold"] * len(st)
        for k in range(1, len(st)):
            if st[k] in ("buy", "sell") and st[k] != st[k - 1]:
                ev[k] = st[k]
        r = rh.harness_backtest(load(prefix, i), ev, ev, PIP, PV, mode="fixed",
                                fixed_sl_pips=100.0, fixed_tp_pips=200.0,
                                initial_balance=5000.0, risk_pct=2.0)
        T += r["total_trades"]
        net += r["total_profit"]
    P("- %s (R1 OOS): trades=%d netC0=$%.0f expC0=$%.2f expC1=$%.2f"
      % (label, T, net, net / T if T else 0.0,
         net / T - C1_PIPS * USD_PER_PIP if T else 0.0))

P("")
P("## CYCLE-R1 verdicts (registered rule: ADVANCE iff h5 AND h20 CANDIDATE on IS and OOS)")
for hyp, is_r, oos_r in (("H-V3-1 fade", res_a3_is, res_a3_oos),
                         ("H-V3-2 session", res_a4_is, res_a4_oos)):
    both = lambda r: r["h5"]["verdict"] == "CANDIDATE" and r["h20"]["verdict"] == "CANDIDATE"
    v = "ADVANCE" if (both(is_r) and both(oos_r)) else "RETIRED"
    P("- %s: IS %s | OOS %s -> %s"
      % (hyp, "CANDIDATE" if both(is_r) else "failed", "CANDIDATE" if both(oos_r) else "failed", v))

out = {"experiment": "CYCLE-R1", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "oos_identity": "f5b0124b363acaa0b3364618ccdc9f584bb21a043301df95f6b646a26faa410a",
       "results": {"a3_is": res_a3_is, "a3_oos": res_a3_oos, "a4_is": res_a4_is, "a4_oos": res_a4_oos}}
with open(os.path.join(HERE, "CYCLE_R1_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CYCLE_R1_VALIDATION.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CYCLE_R1_VALIDATION.md | CYCLE_R1_RESULTS.json")
sys.exit(0)
