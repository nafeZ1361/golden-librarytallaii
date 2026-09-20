# CP5.6 — MAIN STATISTICAL SECTION (dependence-corrected evaluation)
Generated: 2026-09-05T15:54:01 | disk-only, no MT5, frozen dataset be4fa581...,
  frozen sources cp5-source-freeze-v1. Registered constants BEFORE computation:
  SEED=55056, N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h, Bonferroni over 4 primary cells (alpha 0.05 -> 0.0125). No parameter/metric change; verdicts per the unchanged registered rules.

- integrity gate A1 h5: recomputed events=1376 wins=765 vs frozen 1376/765 -> MATCH
- integrity gate A1 h20: recomputed events=1374 wins=714 vs frozen 1374/714 -> MATCH
- integrity gate A2 h5: recomputed events=1855 wins=975 vs frozen 1855/975 -> MATCH
- integrity gate A2 h20: recomputed events=1851 wins=956 vs frozen 1851/956 -> MATCH

## 1. Event-overlap forensics (addendum note — numeric)
- A1 h5: consecutive-event bar-gaps: median=47, share < h (5 bars) = 8.5%
- A1 h20: consecutive-event bar-gaps: median=47, share < h (20 bars) = 23.0%
- A2 h5: consecutive-event bar-gaps: median=9, share < h (5 bars) = 26.7%
- A2 h20: consecutive-event bar-gaps: median=9, share < h (20 bars) = 71.9%

## 2. Serial dependence (win/loss sequence autocorrelation)
- A1 h5: n=1376 rate=55.60% | rho1..5=['0.028', '-0.031', '0.073', '-0.017', '-0.020'] | rho1 significant: False | within-window rho1 mean: 0.028
    design effect (HAC, L=5): 1.061 | HAC-adjusted Wald LB: 52.89% | Bonferroni HAC LB: 52.50%
    block-bootstrap CI (len=5): [52.83%, 58.36%] | Bonferroni bootstrap CI: [52.18%, 59.01%]
- A1 h20: n=1374 rate=51.97% | rho1..5=['0.062', '-0.051', '0.021', '-0.000', '0.028'] | rho1 significant: True | within-window rho1 mean: 0.061
    design effect (HAC, L=20): 0.989 | HAC-adjusted Wald LB: 49.32% | Bonferroni HAC LB: 48.94%
    block-bootstrap CI (len=20): [49.27%, 54.59%] | Bonferroni bootstrap CI: [48.54%, 55.28%]
- A2 h5: n=1855 rate=52.56% | rho1..5=['0.001', '-0.055', '-0.021', '-0.011', '-0.014'] | rho1 significant: False | within-window rho1 mean: 0.005
    design effect (HAC, L=5): 0.895 | HAC-adjusted Wald LB: 50.29% | Bonferroni HAC LB: 49.96%
    block-bootstrap CI (len=5): [50.40%, 54.77%] | Bonferroni bootstrap CI: [49.87%, 55.31%]
- A2 h20: n=1851 rate=51.65% | rho1..5=['0.328', '0.131', '0.024', '-0.021', '0.019'] | rho1 significant: True | within-window rho1 mean: 0.267
    design effect (HAC, L=20): 2.056 | HAC-adjusted Wald LB: 48.38% | Bonferroni HAC LB: 47.91%
    block-bootstrap CI (len=20): [48.35%, 54.89%] | Bonferroni bootstrap CI: [47.38%, 55.86%]

## 3. Cell verdicts AFTER dependence + multiple-testing correction
- Decision rule (fixed): a cell keeps CANDIDATE status only if ALL corrected lower bounds (HAC-Bonferroni AND bootstrap-Bonferroni) stay above 50%.
- A1_h5: HAC-Bonf LB=52.50% | Boot-Bonf LB=52.18% -> CANDIDATE (survives Bonferroni+dependence correction)
- A1_h20: HAC-Bonf LB=48.94% | Boot-Bonf LB=48.54% -> NO PROVEN DIRECTIONAL EDGE (fails after correction)
- A2_h5: HAC-Bonf LB=49.96% | Boot-Bonf LB=49.87% -> NO PROVEN DIRECTIONAL EDGE (fails after correction)
- A2_h20: HAC-Bonf LB=47.91% | Boot-Bonf LB=47.38% -> NO PROVEN DIRECTIONAL EDGE (fails after correction)

## 4. Strategy verdicts (registered rules UNCHANGED — both horizons required)
- A1: h5=CANDIDATE (survives Bonferroni+dependence correction) | h20=NO PROVEN DIRECTIONAL EDGE (fails after correction) => NO PROVEN EDGE
  (h20 CI already included 50%% pre-correction; registered both-horizons rule governs; no rule change after results.)
- A2: h5=NO PROVEN DIRECTIONAL EDGE (fails after correction) | h20=NO PROVEN DIRECTIONAL EDGE (fails after correction) => NO PROVEN EDGE
  (h20 CI already included 50%% pre-correction; registered both-horizons rule governs; no rule change after results.)

## 5. Honest reading (per user directive 3)
- A1 h5 after Bonferroni+dependence: HAC LB=52.50%, bootstrap LB=52.18%.
- If that lower bound includes 50%, A1-h5 is reported as NO PROVEN EDGE even though the uncorrected interval looked promising. No rescue edits applied.
