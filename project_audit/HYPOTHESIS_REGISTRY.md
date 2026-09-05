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

| H-A2-V2-FADE | Inverted (fade) prediction on the same first-breakout population, h5-only primary | breakout-inversion | 2026-09-05 (CYCLE_R2_CONTRACT) | DS-ARCH (derivation), DS-R1 (confirm attempt 57.30%), DS-CP5 (45.34%) | **RETIRED PERMANENTLY** (3-period record 59.26/57.30/45.34; m=3 corrected LB 35.95) | CYCLE_R1/R2 results |
| H-A4-V1 | Session-conditioned first-breakout (overlap window [12,20) broker) | breakout (population restriction) | 2026-09-05 (CYCLE_R1_CONTRACT) | DS-CP5 (IS), DS-R1 | **RETIRED** (IS 50.00%, OOS 47.54%) | CYCLE_R1 results |

## Open slots (updated)

- Variant budget: 5 of 10 consumed (A1-v1, A2-v1, A2-v2, A2-v2-fade, A4-v1).
- Unseen OOS reserves: **EXHAUSTED for retrospective cycles** (2021-06 onward
  burned). The only honest continuation is the registered FORWARD MONITORING
  CONTRACT (prospective accumulation; one evaluation at >=300 events or 180d).

