# FINAL PROJECT VERDICT — کتابخونه بخش طلایی

Date: 2026-09-05 | Chain: CP0 → CP5.8 → CP18 (complete) | LIVE: **DENIED**

## The answer to the project's core question

> Do A1/A2 (or the locked baseline) have a genuine, reproducible, statistically
> defensible, economically viable trading edge?

**NO PROVEN EDGE — now confirmed on independent out-of-sample data.**

## The decisive evidence chain

1. **Infrastructure proven first** (CP0–CP3, 32 checks): pipeline coherent,
   engine deterministic, strategy logic sound. The Phase-1 defect (self-fetch
   signals) was found and fixed BEFORE any trusted measurement.
2. **Control baseline locked** (ST+trend_ali): walk-forward → NO PROVEN EDGE
   (avg OOS −3.6%, 2/5) — preserved as the immutable control (tag
   `baseline-lock-v1`).
3. **A1/A2 pre-registered** before any result (commit `fcf71cb`): 2 hypotheses,
   4 primary cells, ZERO parameter variants, acceptance rules fixed.
4. **Methodology finalized & source frozen** (Amendment 1, tag
   `cp5-source-freeze-v1`, commit `9184e5b`): F1 NaN-guard (proven
   behavior-identical), F4 OR-eligibility rule (registered pre-results).
5. **Frozen dataset** (identity `be4fa581…`), integrity PASS WITH CONDITIONS
   (6 documented flagged gaps), determinism PASS (A==B, isolated, MT5-free),
   provenance **CONFIRMED CLEAN** (static + supply-chain + two-sided purity).
6. **In-sample**: A1-h5 = 55.60% [52.97–58.22] — survived Bonferroni +
   dependence correction (LB 52.50/52.18) + parameter-robustness (10/12) +
   positive gross economics (6/6 windows). A2-h5 marginal, failed correction.
7. **Independent OOS (CP6)** — the decisive step: A1-h5 collapsed to
   **49.29%** (corrected LBs 46.16/45.85; per-window 43–57, unstable); A1
   gross expectancy **negative** (−$4.33/trade); A2-h5 failed correction
   (LB 49.27/49.07), clustering heavy at h20 (ρ₁=0.394).
8. **Verdicts**: A1 = FAILED REPLICATION / NO PROVEN EDGE; A2 = NO PROVEN EDGE;
   economic: FAILED (A1) / fragile-zero (A2); risk: uncompensated drawdown
   profile (24–34% window drawdowns with no edge).

## What this project proved beyond the verdict

- A complete, reusable, leakage-resistant research infrastructure: frozen-data
  discipline, pre-registration, anchor-gated perturbation, dependence-aware
  correction, one-shot OOS — all artifacts hashed and reproducible.
- The 950/2040 historical discrepancy: **unverifiable** — neither number exists
  in any repository artifact (documented with full search evidence, CP5.8).
- Two real engineering defect classes caught by the gates themselves:
  self-fetch signals (Phase 1) and timezone-misinterpreted API bounds (CP6 v1)
  — both root-caused, fixed in audit scope, preserved as v1/superseded.
- An in-sample "edge" (55.6% hit-rate, 6/6 profitable windows, cost-robust)
  that would have looked convincing — and was destroyed by one honest OOS test.
  This is precisely the failure mode the methodology exists to expose.

## Future research (if ever resumed)

Any new hypothesis must: pre-register BEFORE running; beat the locked controls
(`baseline-lock-v1`) under the identical methodology; survive the CP6-style
one-shot independent OOS; and pass CP10/CP11 before any operational stage.
The controls, harness, and all frozen datasets remain in place for that purpose.

## Live authorization

```
LIVE AUTHORIZATION = DENIED (CP18)
No order was ever placed. No order may be placed on this evidence base.
```
