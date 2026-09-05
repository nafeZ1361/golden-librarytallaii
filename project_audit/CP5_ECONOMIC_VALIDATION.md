# CP5.6 — STATISTICAL + ECONOMIC VALIDATION REVIEW (consolidated)
Generated: 2026-09-05T16:17:36 | disk-only; inputs = frozen artifacts + frozen CSVs; no MT5.

## Pre-flight
- HEAD=9184e5b4f5f1 (== cp5-source-freeze-v1) | baseline-lock-v1=dd526e588cdf
- source hashes: A1=85c1781a... A2=732d1eaa... harness=c5e7844a... (match Amendment 1)
- dataset identity: be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3 (manifest)
- prior frozen artifacts referenced: CP5_STATISTICAL_RESULTS.json, CP5_PERFORMANCE_RESULTS.json, CP5_CORRECTED_RESULTS.json (dependence+Bonferroni), CP5_PROVENANCE_CHECK.md (CONFIRMED CLEAN). Nothing overwritten (rule 7).

## Registered constants (unchanged)
- costs: C0=0 | C1=3.5 pips | C2=6.0 pips; lot=0.1 constant -> $1.00/pip/trade
- directed expansion: C1/C2 computed for BOTH strategies per new MASTER PROMPT CP5.6 definition (supersedes §13 deferral for this review; costs only worsen).

- trading days per window (frozen data): {1: 33, 2: 32, 3: 33, 4: 32, 5: 33, 6: 32}

## A1 — economic review (frozen C0 aggregates + registered cost scenarios)
- C0 (0.0 pips/trade = $0.00): net=$10700.00 expectancy=$11.03/trade -> POSITIVE
- C1 (3.5 pips/trade = $3.50): net=$7305.00 expectancy=$7.53/trade -> POSITIVE
- C2 (6.0 pips/trade = $6.00): net=$4880.00 expectancy=$5.03/trade -> POSITIVE
- break-even cost: 11.03 pips/trade (realistic gold round-trip ~2-4 pips; margin exists but under OPTIMISTIC engine conventions — see limitations)
- cost sensitivity (expectancy $/trade at pips): {"1.0": 10.03, "2.0": 9.03, "2.5": 8.53, "3.0": 8.03, "3.5": 7.53, "4.0": 7.03, "5.0": 6.03, "6.0": 5.03, "8.0": 3.03, "10.0": 1.03, "12.0": -0.97}
- win/loss distribution: two-point structure {+$200 TP, -$100 SL} — max deviation of per-window avg win/loss from (200,100): 0.0000 -> CONFIRMED (fixed-geometry artifact; every trade is exactly -$100 or +$200 gross)
- trade frequency: trades/day per window = [(1, 4.15), (2, 5.88), (3, 5.52), (4, 4.66), (5, 4.76), (6, 4.91)] | mean 4.98/day
- max drawdown per window (each window standalone from $5000): [11.86, 18.31, 24.53, 20.0, 19.7, 8.93] | mean 17.22% | max 24.53%
- effect sizes (statistical, from CP5_CORRECTED_RESULTS.json):
    A1_h5: rate=55.60% n=1376 z=4.15 Cohen's h=0.112 (small)
    A1_h20: rate=51.97% n=1374 z=1.46 Cohen's h=0.039 (small)

## A2 — economic review (frozen C0 aggregates + registered cost scenarios)
- C0 (0.0 pips/trade = $0.00): net=$8700.00 expectancy=$10.66/trade -> POSITIVE
- C1 (3.5 pips/trade = $3.50): net=$5844.00 expectancy=$7.16/trade -> POSITIVE
- C2 (6.0 pips/trade = $6.00): net=$3804.00 expectancy=$4.66/trade -> POSITIVE
- break-even cost: 10.66 pips/trade (realistic gold round-trip ~2-4 pips; margin exists but under OPTIMISTIC engine conventions — see limitations)
- cost sensitivity (expectancy $/trade at pips): {"1.0": 9.66, "2.0": 8.66, "2.5": 8.16, "3.0": 7.66, "3.5": 7.16, "4.0": 6.66, "5.0": 5.66, "6.0": 4.66, "8.0": 2.66, "10.0": 0.66, "12.0": -1.34}
- win/loss distribution: two-point structure {+$200 TP, -$100 SL} — max deviation of per-window avg win/loss from (200,100): 0.0000 -> CONFIRMED (fixed-geometry artifact; every trade is exactly -$100 or +$200 gross)
- trade frequency: trades/day per window = [(1, 6.15), (2, 7.91), (3, 2.79), (4, 2.81), (5, 2.39), (6, 3.09)] | mean 4.19/day
- max drawdown per window (each window standalone from $5000): [22.67, 17.31, 33.87, 23.21, 22.03, 15.38] | mean 22.41% | max 33.87%
- effect sizes (statistical, from CP5_CORRECTED_RESULTS.json):
    A2_h5: rate=52.56% n=1855 z=2.21 Cohen's h=0.051 (small)
    A2_h20: rate=51.65% n=1851 z=1.42 Cohen's h=0.033 (small)

## CP5.6 gate re-affirmation
- 'if edge appears in only ONE horizon, it is NOT proven edge' — A1 passes h5 (corrected LBs 52.50/52.18) but fails h20; A2 fails both after correction.
- economic expectancy is POSITIVE even under C2 for both strategies, but the statistical gate governs: economics alone never authorize edge claims.

## Consolidated CP5.6 verdicts (registered rules UNCHANGED)
- A1: NO PROVEN EDGE (statistical gate: h5 CANDIDATE survives correction, h20 FAILS).
  Economic (informational): expectancy $11.03 -> $7.53 (C1) -> $5.03 (C2); break-even ~11.0 pips.
- A2: NO PROVEN EDGE (h5 marginal fail after correction 49.96%, h20 fail with rho1=0.328 clustering).
  Economic (informational): expectancy $10.66 -> $7.16 (C1) -> $4.66 (C2); break-even ~10.7 pips.
- LIMITATIONS recorded: constant-cost arithmetic (no per-trade spread variation/slippage distribution); same-bar-close + TP-first optimistic conventions inflate gross AND cost margin; no per-cell minimum-N pre-registered; costs were computed for both strategies as a directed review expansion (documented above).
