# cp5_statistical_validation.py — CP5.6 MAIN STATISTICAL SECTION
# (approved: DATA PROVENANCE = CONFIRMED CLEAN)
# Registered BEFORE computation (constants fixed; no post-hoc invention):
#   SEED = 55056 | N_BOOT = 10000 | BLOCK_LEN = h (event blocks; rationale:
#   forward-window overlap spans <= h bars, so dependence is confined to
#   ~h consecutive events) | NW_LAG = h (Bartlett kernel) | BONFERRONI_M = 4
#   (the 4 primary cells) | ALPHA = 0.05 -> corrected alpha = 0.0125.
# Steps:
#   1. Recompute per-event outcome sequences with the EXACT registered hit-rate
#      logic; assert event/hit counts == frozen CP5.5 statistics (integrity gate).
#   2. Serial dependence: lag-1..5 autocorrelation of win/loss (+1/-1) sequence;
#      SE = 1/sqrt(n); pooled and within-window-only variants.
#   3. Dependence-corrected CIs: block-bootstrap percentile CI + HAC (Bartlett)
#      adjusted Wald CI; both at alpha and at Bonferroni alpha.
#   4. Event-overlap forensics: bar-distance between consecutive events vs h.
#   5. Cell verdicts + strategy verdicts per the UNCHANGED registered rules.
# NO source/parameter/metric change. Disk-only. No MT5.

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

lines = []


def P(s):
    print(s)
    lines.append(s)


def load_window(i):
    df = pd.read_csv(os.path.join(CACHE, "cp5_window_%d_df.csv" % i))
    df["time"] = pd.to_datetime(df["time"])
    return df


def event_outcomes(states, closes, h):
    """EXACT registered hit-rate event logic (rh.hit_rate) + per-event outcome."""
    ys, gaps, ev_idx = [], [], []
    for i in range(1, len(states)):
        s_cur, s_prev = states[i], states[i - 1]
        if s_cur in ("buy", "sell") and s_cur != s_prev:
            if i + h >= len(closes):
                continue
            fwd = closes[i + h]
            win = (s_cur == "buy" and fwd > closes[i]) or (s_cur == "sell" and fwd < closes[i])
            ys.append(1 if win else -1)
            ev_idx.append(i)
    for a, b in zip(ev_idx[:-1], ev_idx[1:]):
        gaps.append(b - a)
    return np.array(ys, dtype=float), ev_idx, gaps


def acf(y, k):
    y = np.asarray(y, dtype=float)
    if len(y) <= k or np.std(y) == 0:
        return 0.0
    yc = y - y.mean()
    return float(np.sum(yc[:-k] * yc[k:]) / np.sum(yc * yc))


rng = np.random.default_rng(SEED)


def block_bootstrap_ci(y, block_len, n_boot, lo_pct, hi_pct, h):
    """Moving-block bootstrap percentile CI for the hit rate."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < block_len:
        return None, None
    starts = rng.integers(0, n, size=(n_boot, int(np.ceil(n / block_len))))
    rates = np.empty(n_boot)
    for b in range(n_boot):
        idx = np.concatenate([(starts[b, j] + np.arange(block_len)) % n
                              for j in range(starts.shape[1])])[:n]
        rates[b] = (y[idx] > 0).mean()
    return float(np.percentile(rates, lo_pct * 100)), float(np.percentile(rates, hi_pct * 100))


# ============ integrity gate: counts must equal frozen CP5.5 statistics =====
with open(os.path.join(HERE, "CP5_STATISTICAL_RESULTS.json"), encoding="utf-8") as f:
    FROZEN = json.load(f)

P("# CP5.6 — MAIN STATISTICAL SECTION (dependence-corrected evaluation)")
P("Generated: %s | disk-only, no MT5, frozen dataset be4fa581...," % datetime.now().isoformat(timespec="seconds"))
P("  frozen sources cp5-source-freeze-v1. Registered constants BEFORE computation:")
P("  SEED=55056, N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h, Bonferroni over 4 primary"
  " cells (alpha 0.05 -> 0.0125). No parameter/metric change; verdicts per the"
  " unchanged registered rules.")
P("")

cells = {}
for name, mod in STRATS.items():
    for h in HORIZONS:
        ys_all, gap_all, win_idx_bounds = [], [], [0]
        for i in range(1, 7):
            df = load_window(i)
            st = mod.signal_fn(df, "3m")
            closes = df["close"].to_numpy(dtype=float)
            ys, ev_idx, gaps = event_outcomes(st, closes, h)
            ys_all.append(ys)
            gap_all += gaps
            win_idx_bounds.append(win_idx_bounds[-1] + len(ys))
        y = np.concatenate(ys_all) if ys_all else np.array([])
        n, k = int(len(y)), int((y > 0).sum())
        # integrity gate vs frozen CP5.5 numbers
        fz = FROZEN["statistical"][name]["h%d" % h]["aggregate"]
        gate = (n == fz["events"] and k == fz["wins"])
        P("- integrity gate %s h%d: recomputed events=%d wins=%d vs frozen %d/%d -> %s"
          % (name, h, n, k, fz["events"], fz["wins"], "MATCH" if gate else "MISMATCH -> ABORT"))
        if not gate:
            with open(os.path.join(HERE, "CP5_STATISTICAL_VALIDATION.md"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            sys.exit(3)
        cells[(name, h)] = {"y": y, "bounds": win_idx_bounds, "gaps": gap_all}

# ============ analysis per cell ==============================================
P("")
P("## 1. Event-overlap forensics (addendum note — numeric)")
for (name, h), c in cells.items():
    g = np.array(c["gaps"], dtype=float)
    if len(g):
        share = float((g < h).mean() * 100)
        P("- %s h%d: consecutive-event bar-gaps: median=%.0f, share < h (%d bars) = %.1f%%"
          % (name, h, np.median(g), h, share))

P("")
P("## 2. Serial dependence (win/loss sequence autocorrelation)")
z_wald = 1.959963984540054
z_bonf = 2.241402727604947   # norm.ppf(1 - 0.0125/2)
results = {}
for (name, h), c in cells.items():
    y = c["y"]
    n = len(y)
    p = (y > 0).mean()
    L = min(h, n - 1)
    rho_full = [acf(y, k) for k in range(1, max(6, L + 1))]
    rho = rho_full[:5]
    sig1 = abs(rho[0]) > z_wald / np.sqrt(n)
    # within-window-only lag-1 (exclude cross-window pairs)
    r_within = []
    for a, b in zip(c["bounds"][:-1], c["bounds"][1:]):
        seg = y[a:b]
        if len(seg) > 3:
            r_within.append(acf(seg, 1))
    # HAC (Bartlett, L=h) design effect on the mean
    deff = 1.0 + 2.0 * sum((1.0 - (k + 1) / (L + 1)) * rho_full[k] for k in range(L))
    se0 = np.sqrt(p * (1 - p) / n)
    se_hac = se0 * np.sqrt(max(deff, 1.0))
    lb_hac = (p - z_wald * se_hac) * 100
    lb_hac_bonf = (p - z_bonf * se_hac) * 100
    # block bootstrap
    bb_lo, bb_hi = block_bootstrap_ci(y, h, N_BOOT, ALPHA / 2, 1 - ALPHA / 2, h)
    bb_lo_bonf, bb_hi_bonf = block_bootstrap_ci(y, h, N_BOOT, (ALPHA / BONF_M) / 2,
                                                1 - (ALPHA / BONF_M) / 2, h)
    res = {"n": n, "rate_pct": p * 100, "acf1_5": rho,
           "acf1_significant": bool(sig1), "acf1_within_window_mean": float(np.mean(r_within)) if r_within else None,
           "deff_hac": deff, "wald_lb": (p - z_wald * se0) * 100,
           "hac_lb": lb_hac, "hac_lb_bonferroni": lb_hac_bonf,
           "boot_ci": [bb_lo * 100, bb_hi * 100],
           "boot_ci_bonferroni": [bb_lo_bonf * 100, bb_hi_bonf * 100]}
    results["%s_h%d" % (name, h)] = res
    P("- %s h%d: n=%d rate=%.2f%% | rho1..5=%s | rho1 significant: %s | within-window rho1 mean: %s"
      % (name, h, n, p * 100, ["%.3f" % r for r in rho], sig1,
         ("%.3f" % res["acf1_within_window_mean"]) if res["acf1_within_window_mean"] is not None else "n/a"))
    P("    design effect (HAC, L=%d): %.3f | HAC-adjusted Wald LB: %.2f%% | Bonferroni HAC LB: %.2f%%"
      % (L, deff, lb_hac, lb_hac_bonf))
    P("    block-bootstrap CI (len=%d): [%.2f%%, %.2f%%] | Bonferroni bootstrap CI: [%.2f%%, %.2f%%]"
      % (h, bb_lo * 100, bb_hi * 100, bb_lo_bonf * 100, bb_hi_bonf * 100))

P("")
P("## 3. Cell verdicts AFTER dependence + multiple-testing correction")
P("- Decision rule (fixed): a cell keeps CANDIDATE status only if ALL corrected"
  " lower bounds (HAC-Bonferroni AND bootstrap-Bonferroni) stay above 50%.")
cell_verdicts = {}
for (name, h), _ in cells.items():
    key = "%s_h%d" % (name, h)
    r = results[key]
    passes = (r["hac_lb_bonferroni"] > 50.0 and r["boot_ci_bonferroni"][0] > 50.0)
    v = "CANDIDATE (survives Bonferroni+dependence correction)" if passes else \
        "NO PROVEN DIRECTIONAL EDGE (fails after correction)"
    cell_verdicts[key] = {"verdict": v,
                          "hac_lb_bonferroni": r["hac_lb_bonferroni"],
                          "boot_lb_bonferroni": r["boot_ci_bonferroni"][0]}
    P("- %s: HAC-Bonf LB=%.2f%% | Boot-Bonf LB=%.2f%% -> %s"
      % (key, r["hac_lb_bonferroni"], r["boot_ci_bonferroni"][0], v))

P("")
P("## 4. Strategy verdicts (registered rules UNCHANGED — both horizons required)")
strat_verdicts = {}
for name in STRATS:
    v5 = cell_verdicts["%s_h5" % name]["verdict"]
    v20 = cell_verdicts["%s_h20" % name]["verdict"]
    both = v5.startswith("CANDIDATE") and v20.startswith("CANDIDATE")
    sv = "CANDIDATE — proceeds to economic/cost review per registered path" if both else "NO PROVEN EDGE"
    strat_verdicts[name] = sv
    P("- %s: h5=%s | h20=%s => %s" % (name, v5, v20, sv))
    if not both:
        P("  (h20 CI already included 50%% pre-correction; registered both-horizons rule governs; "
          "no rule change after results.)")

P("")
P("## 5. Honest reading (per user directive 3)")
a1h5 = results["A1_h5"]
P("- A1 h5 after Bonferroni+dependence: HAC LB=%.2f%%, bootstrap LB=%.2f%%."
  % (a1h5["hac_lb_bonferroni"], a1h5["boot_ci_bonferroni"][0]))
P("- If that lower bound includes 50%, A1-h5 is reported as NO PROVEN EDGE even"
  " though the uncorrected interval looked promising. No rescue edits applied.")

# ============ artifacts ======================================================
out = {"experiment": "CP5.6-statistical", "generated_local": datetime.now().isoformat(timespec="seconds"),
       "registered_constants": {"seed": SEED, "n_boot": N_BOOT, "block_len": "h (events)",
                                "nw_lag": "h", "bonferroni_m": BONF_M, "alpha": ALPHA},
       "integrity_gate": "recomputed event/win counts == frozen CP5.5 statistics (all 4 cells)",
       "results": results, "cell_verdicts": cell_verdicts, "strategy_verdicts": strat_verdicts}
with open(os.path.join(HERE, "CP5_CORRECTED_RESULTS.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, default=str)
with open(os.path.join(HERE, "CP5_STATISTICAL_VALIDATION.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
P("")
P("[artifacts saved] CP5_STATISTICAL_VALIDATION.md | CP5_CORRECTED_RESULTS.json")
sys.exit(0)
