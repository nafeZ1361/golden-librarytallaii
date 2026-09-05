# RESEARCH CONTRACT — CYCLE-R2 (fade h5-only, third-period confirmatory check)

Date registered: 2026-09-05 (BEFORE the DS-CP5 fade evaluation — this specific
measurement has never been made: DS-CP5-MAIN was consumed by continuation
hypotheses, never by the fade prediction).

## Multiplicity disclosure (declared up-front)

This is the THIRD look at the fade pattern across periods (DS-ARCH derivation,
DS-R1 confirmation-attempt, now DS-CP5). Cumulative Bonferroni for the fade
h5 hypothesis family: **m=3** (z = norm.ppf(1 - 0.05/3/2) = 2.39398). No
threshold was chosen after seeing any CP5 fade number.

## Structural basis for the h5-only primary (registered before running)

Across BOTH prior datasets the fade pattern was h5-concentrated and h20-dead:
- DS-ARCH (derivation): h5 59.26% CANDIDATE / h20 50.79% failed.
- DS-R1 (confirmation attempt): h5 57.30% / h20 54.59%, both failed gate.
The reversal half-life of first-breakouts is therefore structurally short.
Declaring h5 as the SOLE primary horizon is a structural decision, not a
result-driven rescue; h20 is explicitly retired for the fade family.

## One-shot evaluation (registered)

- Data: DS-CP5-MAIN (be4fa581...) — the A2-v2 event population on cp5 windows.
- Metric: fade h5 hit-rate (win = close[i+5] AGAINST breakout direction).
- n expected ~161 (A2-v2 CP5 events).
- ACCEPTED (statistically): HAC-Bonf(m=3) LB > 50% AND MBB-Bonf(m=3) LB > 50%.
- Underpowered outcome is an ALLOWED result: if LB <= 50%, the fade pattern is
  RETIRED permanently (three looks exhausted; only forward accumulation could
  ever revisit it, per the Forward Monitoring Contract).

## Non-acceptance consequence

Fade RETIRED permanently for live purposes regardless of the point estimate;
a point estimate above 50% with LB <= 50% records "directionally consistent,
statistically unconfirmed — forward monitoring only".
