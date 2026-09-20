# CP8 — MULTIPLE-TESTING INVENTORY (complete, nothing deleted)

Generated: 2026-09-05. Method already applied pre-results where applicable
(Bonferroni m=4 + dependence-aware HAC/MBB at CP5.6 and CP6); this file is the
full inventory required by the master prompt.

## Complete inventory of statistical tests ever executed

| Stage | Tests | Family/correction applied | Status |
|---|---|---|---|
| CP4 walk-forward | 11-combo grid x 5 folds = 55 IS evaluations + 5 OOS runs | IS-only selection (structural) | superseded-era, preserved |
| CP4b ATR exits | same grid, ATR geometry | IS-only selection | superseded-era, preserved |
| CP4c hit-rate | 4 aggregates (2 indicators x h5/h20) M3 | none (diagnostic era; superseded by CP5) | preserved |
| CP4d timeframe | 8 cells M15/H1 (+ TZ-bounds defect documented at CP6) | none (diagnostic era) | preserved |
| CP5.5 primary | 4 cells (A1/A2 x h5/h20), 6 windows, aggregates | none at measurement (registered rules governed verdicts) | preserved |
| CP5.6 corrected | same 4 cells | **Bonferroni m=4 + HAC + MBB (seed=55056)** | A1-h5 survived in-sample |
| CP5.7 robustness | 12 A1 + 9 A2 variants x 2 horizons = 42 screening cells + 18 SL/TP economic cells | SCREENING ONLY — explicitly not edge claims | preserved |
| CP6 OOS one-shot | same 4 registered cells on independent data | **Bonferroni m=4 + HAC + MBB** | decisive |

## Dependent/independent structure

- The 4 primary cells share windows and indicators (dependent family) ->
  family-wise correction (Bonferroni) + dependence correction (HAC/MBB) applied.
- CP6 is the only truly independent test family (fresh period, frozen params).
- CP5.7 variants are sensitivity screens about registered points, not
  hypotheses; they never entered edge claims.

## Post-correction outcome

- In-sample (CP5.6): A1-h5 survived Bonferroni+dependence (LB 52.50/52.18).
- Independent (CP6): A1-h5 = 49.29% (LB 46.16/45.85) -> the in-sample survivor
  was period-specific; empirical confirmation that the multiple-testing control
  was necessary and that the pipeline's honest gate worked end-to-end.
- **NO cell retains a corrected positive edge across independent data.**
