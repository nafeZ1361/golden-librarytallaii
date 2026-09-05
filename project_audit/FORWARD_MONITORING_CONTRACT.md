# FORWARD MONITORING CONTRACT — first-breakout fade (h5)

Registered: 2026-09-05 | Status: **DORMANT — monitoring only, no trading**

Context: CYCLE-R2 permanently RETIRED the fade hypothesis after the third
period (DS-CP5) measured 45.34% — below 50. Per the R2 contract's own
consequence clause, the three-look budget is exhausted for in-sample/frozen
evaluation. The ONLY statistically honest path that could ever revisit this
pattern is **prospective data accumulation** (no further lookback looks exist:
2021-06→2026-09-04 is fully burned across three registered datasets).

## Registered prospective protocol (fixed now, evaluated ONCE later)

- Population: first-breakout events of the FROZEN A2-v2 event rule
  (`strategy_a2_v2_firstbreakout.py`, params unchanged), occurring STRICTLY
  after 2026-09-04 23:54 (the last bar of any frozen dataset).
- Metric: fade h5 hit-rate (win = close[i+5] AGAINST the breakout direction).
- Trigger for the single evaluation: >= 300 accumulated events OR >= 180
  calendar days, whichever comes FIRST. ONE evaluation. No interim peeking for
  decisions (bookkeeping only).
- Acceptance: HAC-Bonf(m=4 cumulative family looks: 3 retrospective + 1
  prospective) LB > 50% AND MBB-Bonf(m=4) LB > 50%.
- Acceptance consequence: the pattern becomes a REGISTERED CANDIDATE eligible
  for the full pipeline (economics/risk/reproduction/demo) — NOT live.
- Non-acceptance: the pattern is dead permanently; no further contracts.

## Data collection mechanics

- Acquisition: read-only MT5, same integrity battery, same manifest/hash
  discipline (adapt `cycle_r1_oos_freeze.py` with the forward boundary
  2026-09-04 23:57). Accumulated in chunks (e.g., monthly) as
  `fwd_window_<n>_df.csv` — frozen on arrival, never rewritten.
- The event population is computed with the FROZEN A2-v2 code on arrival;
  running event counts are bookkeeping, NOT interim statistical tests.
