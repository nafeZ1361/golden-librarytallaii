# cp6_oos_validation.py — CP6 INDEPENDENT OOS VALIDATION (one-shot)
# Registered constants (UNCHANGED from CP5.6): SEED=55056, N_BOOT=10000,
# BLOCK_LEN=h, NW_LAG=h, Bonferroni m=4 (family = the 4 registered cells),
# cell rule: CANDIDATE iff HAC-Bonf LB > 50% AND bootstrap-Bonf LB > 50%.
# Replication framing (registered before results):
#   - the CP5.6 surviving candidate cell was A1-h5;
#   - CP6 replication PASS for a cell iff it keeps CANDIDATE status on OOS;
#   - A2 had no surviving candidate -> any OOS positive is reported but no
#     replication claim is manufactured;
#   - FAILED REPLICATION is recorded honestly if the cell collapses.
# Economic context: C0/C1 per window with the frozen engine (informational only).
# Disk-only after acquisition. No MT5. No tuning. One-shot.

import os, sys, json, hashlib
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

SEED, N_BOOT = 55056, 10000
BONF_M, ALPHA = 4, 0.05
STRATS = {"A1": a1, "A2": a2}
HORIZONS = [5, 20]
USD_PER_PIP, C1_PIPS = 1.0, 3.5
PIP, PV = 0.1, 10.0

lines = []


def P(s):
    print(s)
    lines.append(s)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def sha_txt(s):
    return hashlib.sha256(s.encode()).hexdigest()


def load_oos(i):
    df = pd.read_csv(os.path.join(CACHE, "cp6_window_%d_df.csv" % i))
    df["time"] = pd.to_datetime(df["time"])
    return df


def event_outcomes(states, closes, h):
    ys, ev_idx = [], []
    for i in range(1, len(states)):
        s_cur, s_prev = states[i], states[i - 1]
        if s_cur in ("buy", "sell") and s_cur != s_prev:
            if i + h >= len(closes):
                continue
            fwd = closes[i + h]
            win = (s_cur == "buy" and fwd > closes[i]) or (s_cur == "sell" and fwd < closes[i])
            ys.append(1 if win else -1)
            ev_idx.append(i)
    return np.array(ys, dtype=float), ev_idx


def acf(y, k):
    yc = y - y.mean()
    return float(np.sum(yc[:-k] * yc[k:]) / np.sum(yc * yc))


rng = np.random.default_rng(SEED)


def block_bootstrap_lb(y, block_len, lo_pct):
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


P("# CP6 — INDEPENDENT OOS VALIDATION (one-shot, frozen parameters)")
P("Generated: %s | OOS dataset identity:" % datetime.now().isoformat(timespec="seconds"))
P("  3d615ad8d241b70e566050535e0889380e1869b85a26830e5fbd08f48e2f1a3c")
P("  (6 x 14,400 M3 bars 2025-03-20..2025-12-10 21:36, preceding the frozen CP5"
  " boundary — never used in design/selection; + 128-bar forward fragment"
  " reported separately). Registered constants unchanged: SEED=55056,")
P("  N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h, Bonferroni m=4. NO tuning occurred.")
P("")

# pre-flight: hashes
man = json.load(open(os.path.join(HERE, "CP6_OOS_DATA_FREEZE_manifest.json"), encoding="utf-8"))
ok = all(sha256_file(os.path.join(CACHE, m["file"])) == m["sha256"] for m in man["windows"])
P("- pre-flight: OOS CSV hashes == manifest: %s | verdict: %s | anomalies: %s"
  % (ok, man["verdict"], man["anomalies"]))
if not ok:
    sys.exit(3)

# determinism gate
P("")
P("## Determinism gate (A/B, frozen functions, OOS windows)")
det_ok = True
oos_states = {}
for name, mod in STRATS.items():
    for i in range(1, 7):
        df = load_oos(i)
        sA = mod.signal_fn(df.copy(), "3m")
        sB = mod.signal_fn(load_oos(i), "3m")
        eq = sha_txt(json.dumps(sA)) == sha_txt(json.dumps(sB))
        det_ok &= eq
        oos_states[(name, i)] = sA
        if not eq:
            P("- %s w%d: A!=B -> DETERMINISM FAILURE" % (name, i))
P("- determinism: %s" % ("PASS (all A==B byte-identical)" if det_ok else "FAIL"))
if not det_ok:
    sys.exit(3)

# evaluation
z_wald = 1.959963984540054
z_bonf = 2.241402727604947
results = {}
P("")
P("## One-shot evaluation (h5/h20, per window and aggregate)")
for name, mod in STRATS.items():
    for h in HORIZONS:
        per_win, ys_all, bounds = [], [], [0]
        for i in range(1, 7):
            closes = load_oos(i)["close"].to_numpy(dtype=float)
            ys, _ = event_outcomes(oos_states[(name, i)], closes, h)
            e = len(ys)
            w = int((ys > 0).sum())
            rate = w / e * 100 if e else None
            per_win.append({"window": i, "events": e, "wins": w, "rate_pct": rate})
            ys_all.append(ys)
            bounds.append(bounds[-1] + e)
        y = np.concatenate(ys_all)
        n, k = len(y), int((y > 0).sum())
        p = k / n
        L = min(h, n - 1)
        rho_full = [acf(y, kk) for kk in range(1, max(6, L + 1))]
        deff = 1.0 + 2.0 * sum((1.0 - (kk + 1) / (L + 1)) * rho_full[kk] for kk in range(L))
        se0 = np.sqrt(p * (1 - p) / n)
        hac_bonf_lb = (p - z_bonf * se0 * np.sqrt(max(deff, 1.0))) * 100
        boot_bonf_lb = block_bootstrap_lb(y, h, (ALPHA / BONF_M) / 2)
        passes = hac_bonf_lb > 50.0 and boot_bonf_lb is not None and boot_bonf_lb > 50.0
        key = "%s_h%d" % (name, h)
        results[key] = {"n": n, "wins": k, "rate_pct": p * 100,
                        "rho1": rho_full[0], "deff": deff,
                        "hac_bonf_lb": hac_bonf_lb,
                        "boot_bonf_lb": boot_bonf_lb,
                        "verdict": ("REPLICATED CANDIDATE" if passes
                                    else "NO PROVEN DIRECTIONAL EDGE ON OOS"),
                        "per_window": per_win}
        P("- %s: n=%d rate=%.2f%% | rho1=%.3f deff=%.3f | HAC-Bonf LB=%.2f%% |"
          " Boot-Bonf LB=%s -> %s"
          % (key, n, p * 100, rho_full[0], deff, hac_bonf_lb,
             ("%.2f%%" % boot_bonf_lb) if boot_bonf_lb else "n/a",
             results[key]["verdict"]))
        P("    per-window rates: %s"
          % [("w%d: %.1f" % (r["window"], r["rate_pct"])) if r["rate_pct"] is not None
             else ("w%d: n/a" % r["window"]) for r in per_win])

# economic context (informational)
P("")
P("## Economic context (informational — C0/C1, frozen engine, event-mapping)")
for name, mod in STRATS.items():
    T = net = 0
    for i in range(1, 7):
        st = oos_states[(name, i)]
        ev = ["hold"] * len(st)
        for k in range(1, len(st)):
            if st[k] in ("buy", "sell") and st[k] != st[k - 1]:
                ev[k] = st[k]
        r = rh.harness_backtest(load_oos(i), ev, ev, PIP, PV, mode="fixed",
                                fixed_sl_pips=100.0, fixed_tp_pips=200.0,
                                initial_balance=5000.0, risk_pct=2.0)
        T += r["total_trades"]
        net += r["total_profit"]
    P("- %s: trades=%d netC0=$%.0f expC0=$%.2f expC1=$%.2f"
      % (name, T, net, net / T if T else 0.0,
         net / T - C1_PIPS * USD_PER_PIP if T else 0.0))

P("")
P("## CP6 verdicts (registered framing)")
a1h5 = results["A1_h5"]
P("- A1-h5 (the CP5.6 surviving candidate): OOS rate=%.2f%% (n=%d), corrected"
  " LBs: HAC-Bonf %.2f%%, Boot-Bonf %.2f%% -> %s"
  % (a1h5["rate_pct"], a1h5["n"], a1h5["hac_bonf_lb"], a1h5["boot_bonf_lb"],
     "REPLICATION PASS" if a1h5["verdict"].startswith("REPLICATED") else "FAILED REPLICATION"))
P("- A1-h20: %s" % results["A1_h20"]["verdict"])
P("- A2-h5: %s (no CP5.6 candidate existed; reported as measured)" % results["A2_h5"]["verdict"])
P("- A2-h20: %s" % results["A2_h20"]["verdict"])
P("- Forward fragment (128 bars): underpowered supplement — NOT used for any"
  " verdict; retained as evidence of strict-forward behavior.")

out = {"experiment": "CP6-OOS", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "oos_identity": man["dataset_sha256_combined"], "constants": {"seed": SEED, "n_boot": N_BOOT},
       "determinism": det_ok, "results": results}
with open(os.path.join(HERE, "CP6_OOS_VALIDATION_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CP6_OOS_VALIDATION.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CP6_OOS_VALIDATION.md | CP6_OOS_VALIDATION_RESULTS.json")
sys.exit(0)
