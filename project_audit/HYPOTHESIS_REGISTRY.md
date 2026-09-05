# HYPOTHESIS REGISTRY (R4) — nothing is ever deleted

Generated: 2026-09-05 | Allowed statuses: PROPOSED, PREREGISTERED, TESTING,
PASSED_IS, FAILED_IS, PASSED_OOS, FAILED_OOS, RETIRED, REPLICATED,
DEMO_ELIGIBLE, LIVE_ELIGIBLE.

| ID | Hypothesis (one line) | Family | Registered | Datasets used | Final status | Evidence |
|---|---|---|---|---|---|---|
| H-CTRL-BASELINE | Supertrend(10,3) flip + trend_ali(60,6,Hma) agreement, h=entry->SL/TP | trend-following | 2026-09-04 (baseline-lock-v1) | CP4 folds | **RETIRED** — NO PROVEN EDGE (WFO 2/5, avg OOS −3.6%) | CP4 results (committed) |
| H-A1-V1 | RSI14 fresh cross 30/70 + BB(20,2) penetration => mean-reversion at h5/h20 | mean-reversion | 2026-09-04 (fcf71cb) | DS-CP5-MAIN (IS), DS-CP6-OOS | **FAILED_OOS → RETIRED** | IS 55.60% [52.97-58.22] survived correction; OOS 49.29% (CP6) |
| H-A2-V1 | First-hours OR breakout w/ volume >= 1.5x => continuation at h5/h20 (state runs) | breakout | 2026-09-04 (fcf71cb) | DS-CP5-MAIN (IS), DS-CP6-OOS | **FAILED_IS-correction → RETIRED** | IS 52.56% [50.29-54.83] -> corrected LBs 49.96/49.87; OOS 50.96% LB 49.27 |
| H-A2-V2 | Same as V1 but FIRST breakout only per day (de-clustering) | breakout (structural revision) | 2026-09-05 (CP5.9) | DS-CP5-MAIN (IS), DS-ARCH-OOS | **FAILED_OOS → RETIRED** | IS h5 54.66% (n=161, underpowered); OOS h5 40.74% (evidence AGAINST) |

## Open slots

- Variant budget: 3 of 10 consumed (H-A1-V1, H-A2-V1, H-A2-V2).
- Unseen OOS reserves remaining: 2021-06-20→2024-06-26 archive (one family) +
  the forward stream (accumulates daily).
- Next hypotheses MUST be registered via RESEARCH_CONTRACT_TEMPLATE.md before
  any run and must carry an independent economic rationale (HYPOTHESIS_
  GENERATOR_POLICY.md).
