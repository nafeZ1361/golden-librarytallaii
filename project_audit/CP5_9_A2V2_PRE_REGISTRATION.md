# CP5.9 — A2-v2 PRE-REGISTRATION (Adaptive Research Loop, variant #1)

Registered: 2026-09-05 | BEFORE any v2 evaluation on any dataset.
Parent: CP_R0_FAILURE_DIAGNOSIS.md | Budget: variant 1 of max 10.

## Hypothesis (falsifiable)

H-A2v2: IF the first post-Opening-Range breakout bar of an eligible day (volume
≥ 1.5× OR mean) carries genuine continuation information on XAUUSD M3, THEN
close[i+h] continues in the breakout direction in MORE THAN 50% of such first-
breakout events, for h=5 and h=20, with dependence+Bonferroni-corrected 95% CI
lower bounds above 50% on BOTH the in-sample (CP5 frozen) and the independent
OOS (archive period) datasets, evaluated ONE-SHOT.

Falsification: failure of the corrected rule on either dataset -> variant
RETIRED (no tuning, no re-registration on the same data).

## Definition (exactly as implemented — strategy_a2_v2_firstbreakout.py)

- OR eligibility: IDENTICAL to A2-v1 (interior day; previous bar = previous
  calendar day; session break >= 30 min; exactly 40 M3 OR bars; gap-free span
  117 min). Parameters IDENTICAL to v1 (OR 120 min, VOL_MULT 1.5) — the ONLY
  change is the event rule.
- Event rule: per eligible day, AFTER the OR closes, the FIRST bar k with
  (vol[k] >= 1.5*avg_or_vol) AND (close[k] > or_high OR close[k] < or_low)
  emits 'buy' (if above) or 'sell' (if below); ALL other bars of that day are
  'hold'. At most ONE event per day. This de-clusters v1's state runs
  (diagnosed defect) without touching any parameter.
- Direction prediction: continuation of the first breakout over h bars.

## Data plan (purity-ordered)

1. IN-SAMPLE: the CP5 frozen dataset (be4fa581...) — same data that failed for
   v1; used for the initial (non-confirmatory) measurement.
2. OOS: archive period BEFORE the CP6 OOS start (CP6 w1 first bar = 2025-03-20
   03:54) -> 6 x 14,400 M3 bars ending 2025-03-20 03:51, fetched ONCE with the
   TZ-corrected API bounds (CP6 v2 fix), frozen with manifest, evaluated
   ONE-SHOT. This period was never fetched or analyzed by any phase.

## Acceptance / failure (registered)

- Statistical: per dataset, CANDIDATE iff HAC-Bonferroni LB > 50% AND
  block-bootstrap Bonferroni LB > 50% (family = v2 x {h5, h20}, m=2; constants
  SEED=55056, N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h — unchanged).
- Confirmation: v2 advances ONLY if BOTH datasets yield CANDIDATE for the same
  horizon (h5 primary; h20 reported). Any failure -> RETIRED.
- Economic (context, informational): C0/C1 expectancy with the frozen engine
  and the registered baseline geometry (SL100/TP200, 2%, $5,000).

## Budget

- Technical repair loops for v2: max 5. Variants: this is #1 of max 10.
- No threshold/parameter/metric may change after any result is seen.
