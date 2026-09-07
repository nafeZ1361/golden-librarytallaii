# CP-R0 — FAILURE ROOT-CAUSE DIAGNOSIS (post CP6 FAILED REPLICATION)

Generated: 2026-09-05 | Classification per master-prompt taxonomy.

## A1-v1 — h5 candidate collapse (55.60% in-sample -> 49.29% OOS)

| Hypothesized cause | Evidence-based assessment |
|---|---|
| Implementation bug | RULED OUT — determinism PASS, provenance CONFIRMED CLEAN, anchors byte-identical, same code measured both datasets |
| Data defect | RULED OUT — both datasets passed independent integrity batteries (CP5.3/CP6 freeze); no unexplained gaps |
| Look-ahead/leakage | RULED OUT — static + runtime + two-sided purity proofs |
| Statistics error | RULED OUT — counts reconciled; corrections applied identically |
| **Period-specific edge (regime/seasonality of the sample)** | **SUPPORTED** — the signal was h5-specific, horizon-fragile (h20 failed in-sample), and its economics flipped sign across periods; a 15-minute mean-reversion premium on gold is regime-dependent and the CP5 window (Dec2025-Sep2026) carried it while Mar-Dec 2025 did not |
| Hypothesis itself false | SUPPORTED — mean-reversion at these horizons is indistinguishable from noise once period variance is accounted for |

ROOT CAUSE (A1): **genuine strategy failure — period-specific in-sample artifact,
not repairable by structure without data mining.**
DECISION: **A1 RETIRED** (no motivated structural revision; any parameter tweak
would be selection across the same evidence). Failure recorded per rule.

## A2-v1 — h5 marginal (52.56% in-sample, 50.96% OOS; fails correction)

Diagnosed defect (mechanism, visible from registered metrics only):
**event clustering** — A2 emits STATE RUNS; consecutive same-direction bars
create overlapping forward windows (CP6 h20: rho1=0.394, deff=2.14; 71.9% of
gaps < h in-sample) and dilute the hypothesis ("the FIRST breakout carries the
information") with redundant follow-through bars.

ROOT CAUSE (A2): **structurally repairable** — the clustering is a property of
the event rule, not of the market.

## Consequence — Adaptive Research Loop (variant budget registered)

- MAX_TECHNICAL_REPAIR_LOOPS = 5 | MAX_HYPOTHESIS_VARIANTS = 10 (per master prompt §26)
- Variant counter: A1 = RETIRED (no variant). A2-v2 = **variant #1**.
- A2-v2 (structural revision, performance-neutral by construction):
  identical OR eligibility/volume filter/parameters as v1; the ONLY change is
  the event rule -> **one event per day: the FIRST qualifying breakout bar
  after the OR closes**. Rationale: tests the registered hypothesis in its
  de-clustered form; reduces events to at most one per eligible day.
- OOS purity for v2: v2's design used v1's diagnostics (including CP6
  aggregates) -> CP6 data is CONTAMINATED for v2. v2's OOS = the archive period
  BEFORE the CP6 OOS start (ending 2025-03-20 03:51), never fetched/analyzed
  by any phase. Freeze + one-shot evaluation with the SAME registered constants.
- Acceptance (registered, unchanged rule): CANDIDATE iff HAC-Bonf LB > 50% AND
  MBB-Bonf LB > 50%; family m=2 (v2 x {h5,h20}); in-sample first, then OOS
  one-shot; FAILED -> variant retired, no tuning.
