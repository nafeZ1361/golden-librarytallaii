# cp5_9_v2_validation.py — A2-v2 EVALUATION (in-sample + OOS one-shot)
# Registered constants UNCHANGED: SEED=55056, N_BOOT=10000, BLOCK_LEN=h,
# NW_LAG=h, family m=2 (v2 x {h5,h20}), cell rule: CANDIDATE iff
# HAC-Bonf LB > 50% AND MBB-Bonf LB > 50%. Datasets: CP5 frozen (in-sample)
# and CP5.9 archive OOS (060ba244..., never seen by any design step).
# Integrity relations: determinism A/B; v2-event subset check vs A2-v1
# (every v2 event must be a v1 run-start event, same direction).
# Economic context: C0/C1 with the frozen engine and registered geometry.

import os, sys, json, hashlib
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")

import strategy_a2_breakout as a2v1
import strategy_a2_v2_firstbreakout as a2v2
import research_harness as rh

SEED, N_BOOT, BONF_M, ALPHA = 55056, 10000, 2, 0.05
USD_PER_PIP, C1_PIPS, PIP, PV = 1.0, 3.5, 0.1, 10.0

lines = []


def P(s):
    print(s)
    lines.append(s)


def sha_txt(s):
    return hashlib.sha256(s.encode()).hexdigest()


def load(kind, i):
    prefix = "cp5" if kind == "cp5" else "cp6v2"
    df = pd.read_csv(os.path.join(CACHE, "%s_window_%d_df.csv" % (prefix, i)))
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


z_bonf = 2.241402727604947  # norm.ppf(1 - 0.0125)

P("# CP5.9 — A2-v2 EVALUATION (in-sample + independent OOS, one-shot)")
P("Generated: %s | registered: family m=2, SEED=55056, N_BOOT=10000, BLOCK_LEN=h." % datetime.now().isoformat(timespec="seconds"))
P("  Datasets: in-sample = CP5 frozen (be4fa581...); OOS = archive (060ba244...).")
P("")

DET = {"cp5": {}, "oosv2": {}}
states = {"cp5": {}, "oosv2": {}}
subset_ok = True
for kind, files in (("cp5", 6), ("oosv2", 6)):
    for i in range(1, files + 1):
        df = load(kind, i)
        sA = a2v2.signal_fn(df.copy(), "3m")
        sB = a2v2.signal_fn(load(kind, i), "3m")
        det_ok = sha_txt(json.dumps(sA)) == sha_txt(json.dumps(sB))
        DET[kind][i] = det_ok
        states[kind][i] = sA
        s1 = a2v1.signal_fn(df.copy(), "3m")
        v1ev = {k: s1[k] for k in range(1, len(s1))
                if s1[k] in ("buy", "sell") and s1[k] != s1[k - 1]}
        bad = [k for k in range(1, len(sA))
               if sA[k] in ("buy", "sell") and v1ev.get(k) != sA[k]]
        if bad:
            subset_ok = False
            P("- %s w%d SUBSET VIOLATION at bars %s" % (kind, i, bad[:5]))
det_all = all(DET[k][i] for k in DET for i in DET[k])
P("- determinism A/B (12 windows): %s | v2-events subset-of-v1-events: %s"
  % ("PASS" if det_all else "FAIL", "PASS" if subset_ok else "FAIL"))
if not (det_all and subset_ok):
    with open(os.path.join(HERE, "CP5_9_V2_VALIDATION.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(3)

z_wald = 1.959963984540054
results = {}
for kind in ("cp5", "oosv2"):
    for h in (5, 20):
        ys_all, per_win = [], []
        for i in range(1, 7):
            closes = load(kind, i)["close"].to_numpy(dtype=float)
            ys = outcomes(states[kind][i], closes, h)
            per_win.append((i, len(ys), round(ys.mean() * 100, 2) if len(ys) else None))
            ys_all.append(ys)
        y = np.concatenate(ys_all)
        n, k_ = len(y), int((y > 0).sum())
        p = k_ / n
        L = min(h, n - 1)
        rho_full = [acf(y, kk) for kk in range(1, max(6, L + 1))]
        deff = 1.0 + 2.0 * sum((1.0 - (kk + 1) / (L + 1)) * rho_full[kk] for kk in range(L))
        se0 = np.sqrt(p * (1 - p) / n)
        hac_bonf_lb = (p - z_bonf * se0 * np.sqrt(max(deff, 1.0))) * 100
        bb_lb = mbb_lb(y, h, (ALPHA / BONF_M) / 2)
        passes = hac_bonf_lb > 50.0 and bb_lb is not None and bb_lb > 50.0
        key = "%s_h%d" % (kind, h)
        results[key] = {"n": n, "rate_pct": p * 100, "rho1": rho_full[0], "deff": deff,
                        "hac_bonf_lb": hac_bonf_lb, "boot_bonf_lb": bb_lb,
                        "verdict": ("CANDIDATE" if passes else "NO PROVEN DIRECTIONAL EDGE"),
                        "per_window": per_win}
        P("- %s: n=%d rate=%.2f%% rho1=%.3f deff=%.3f | HAC-Bonf LB=%.2f%% |"
          " MBB-Bonf LB=%s -> %s | per-window %s"
          % (key, n, p * 100, rho_full[0], deff, hac_bonf_lb,
             ("%.2f%%" % bb_lb) if bb_lb else "n/a", results[key]["verdict"], per_win))

# economic context
P("")
P("## Economic context (informational — frozen engine, registered geometry)")
for kind in ("cp5", "oosv2"):
    for label, mult in (("C0", 0.0), ("C1", C1_PIPS)):
        T = net = 0
        for i in range(1, 7):
            st = states[kind][i]
            ev = ["hold"] * len(st)
            for k in range(1, len(st)):
                if st[k] in ("buy", "sell") and st[k] != st[k - 1]:
                    ev[k] = st[k]
            r = rh.harness_backtest(load(kind, i), ev, ev, PIP, PV, mode="fixed",
                                    fixed_sl_pips=100.0, fixed_tp_pips=200.0,
                                    initial_balance=5000.0, risk_pct=2.0)
            T += r["total_trades"]
            net += r["total_profit"]
        P("- %s %s: trades=%d net=$%.0f expectancy=$%.2f"
          % (kind, label, T, net, net / T if T else 0.0))
        if label == "C1":
            P("    (C1 expectancy after %.1f-pip cost: $%.2f/trade)"
              % (C1_PIPS, net / T - C1_PIPS * USD_PER_PIP if T else 0.0))

P("")
P("## CP5.9 verdicts (registered rule: advance iff BOTH datasets CANDIDATE same horizon)")
for h in (5, 20):
    ins = results["cp5_h%d" % h]["verdict"] == "CANDIDATE"
    oos = results["oosv2_h%d" % h]["verdict"] == "CANDIDATE"
    v = "ADVANCE (both datasets CANDIDATE)" if (ins and oos) else \
        "RETIRED (failure to confirm on independent data)" if ins else \
        "RETIRED (failed already in-sample)"
    results["final_h%d" % h] = v
    P("- v2 h%d: in-sample=%s | OOS=%s -> %s" % (h, ins, oos, v))

out = {"experiment": "CP5.9-A2v2", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "oos_identity": "060ba2440aa495ab28097d9ed810a5e3bcdf09b00ffba1d15b2e536cea2ea1d7",
       "determinism": det_all, "subset_relation": subset_ok, "results": results}
with open(os.path.join(HERE, "CP5_9_V2_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CP5_9_V2_VALIDATION.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CP5_9_V2_VALIDATION.md | CP5_9_V2_RESULTS.json")
sys.exit(0)
