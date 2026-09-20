# BASELINE LOCK — Golden Library Research Project

Locked: 2026-09-04 | Tag: `baseline-lock-v1`
Precondition: Evidence Preservation commit `d3524bb` (pushed, local == origin).

WHAT THIS LOCKS: the FAILED baseline, as the **immutable control group**.
This is NOT a claim of edge. The locked conclusion is NO PROVEN EDGE.

---

## 1. Control Strategy (verbatim definition)

- Symbol: `XAUUSD.` (broker symbol, trailing dot) | Timeframe: M3 | Candles: Heikin-Ashi
- Trigger: Supertrend flip event, `atr_period=10`, `multiplier=3.0`
- Confirmation: trend_ali state, `length=60`, `length_mult=6.0`, `mode='Hma'`
- Entry: trigger AND confirmation agree on the SAME bar, entry at that bar's close,
  signals computed from the SAME window df (coherent `df=` pipeline — no self-fetch)
- Exits: fixed SL = 100 pips ($10) / TP = 200 pips ($20); same-candle conflict
  resolves TP-first (documented optimistic bias, CP2 S3)
- Risk: 2% of INITIAL balance ($5,000) → $100 risk/trade, constant; lot clamped ≥ 0.01
- Engine: `backtest()` in `backtest/hashem_backtest.py`
  (CP2: 12/12 PASS, deterministic on frozen inputs)
- Reference entry point: `backtest/backtester.py` (run as `python -m backtest.backtester`)

## 2. Validation Methodology (locked — successors must reuse it unchanged)

- Data: MT5 M3, 6 windows × 14,400 bars, fetched with `start_pos=1`
  (forming candle excluded; CP1: 13/13 PASS)
- Window boundaries: bar-count from the M3 bulk fetch (method of CP4c/CP4d;
  `research_harness.load_windows` / `window_bounds_from_m3`)
- Walk-forward: fold i → IS = window i, OOS = window i+1 (5 folds);
  IS-ONLY parameter selection; min 10 IS trades; OOS run ONCE with frozen params
- Diagnostic metric: directional hit-rate (state-flip events, close[i+h] vs close[i],
  horizons 5/20), reported with Wald95 CI
- Known, documented biases (part of the control's identity, CP2): zero costs,
  same-candle TP-priority, gap fills at SL/TP price, end-of-data position dropped.
  Successors must report the same biases and, where possible, a cost-injected variant.

## 3. Locked Control Results (the numbers a successor must beat)

| Checkpoint | Result |
|---|---|
| CP4 WFO (fixed 100/200 exits) | avg OOS ROI **−3.60%**, 2/5 profitable, expectancy **−$4.12**/trade → NO PROVEN EDGE |
| CP4b (ATR exits 2×/3×ATR14) | avg OOS ROI **−7.78%**, 2/5 profitable, expectancy **−$5.26**/trade → no improvement |
| CP4c hit-rate (M3) | supertrend_h5 **47.33%** [44.81–49.84] (entirely below 50% — evidence AGAINST direction); supertrend_h20 48.25% [45.73–50.77]; trend_ali_h5 48.99% [45.80–52.18]; trend_ali_h20 49.68% [46.49–52.87] |
| CP4d hit-rate (M15/H1) | no Wald95 CI above 50% in any cell |
| CP4e (A1/A2) | attempted 2026-09-04; result evidence not preserved; **no scientific conclusion may be attributed to CP4e** |

CURRENT CONTROL/BASELINE CONCLUSION: **NO PROVEN EDGE.**
No claim of a positive edge is recorded from CP4 through CP4e.

## 4. Successor Rule (binding for every future strategy, including A1/A2)

A new strategy supersedes this control ONLY if all of the following hold:

1. **Pre-registration BEFORE any run:** hypothesis, parameter set, metric,
   horizon, pass/fail thresholds, and minimum sample size written down first.
2. **Identical methodology:** same window/boundary method, same 5-fold WFO with
   IS-only selection, same hit-rate metric + CI reporting, same documented biases.
3. **Statistical pass (pre-registered thresholds):** OOS expectancy positive
   across folds AND directional hit-rate 95% CI lower bound > 50%.
4. **Comparison target:** the locked numbers in §3 — not intuition, not a
   cherry-picked window, not an unvalidated notebook strategy.

## 5. Immutability

- Control code and parameters are NOT to be modified. Improvements must be NEW
  strategy files; the control stays reproducible as-is.
- Tag `baseline-lock-v1` marks this lock; the control definition above is the
  single source of truth for "the baseline".

## 6. What this lock does NOT mean

- It does NOT validate the baseline (it failed validation — that is why it is
  preserved as control).
- It does NOT authorize live trading, dry-run deployment, or any order placement.
- It does NOT transfer any CP4e status to CP5 (no CP4e result exists).

Supersedes: the "BASELINE LOCK NOT YET PERFORMED" statement in
`EVIDENCE_STATUS.md` §7 (true at its recording time, before this lock).
