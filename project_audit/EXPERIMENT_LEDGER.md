# EXPERIMENT LEDGER (R4) — every experiment ever executed (nothing deleted)

Machine-readable twin: `EXPERIMENT_LEDGER.json`. Statuses follow the failure
taxonomy of the Master Research Protocol §29.

| Experiment ID | Date | Hypothesis | Dataset | Code version | Result | Status | Failure reason |
|---|---|---|---|---|---|---|---|
| EXP-CP4 | 2026-09-04 | H-CTRL-BASELINE (WFO, 11-combo IS-only grid) | CP4 coherent fold windows (pre-registry era) | pre-freeze (CP1 pipeline fix) | OOS 2/5, avg −3.6%, expectancy −$4.12 | NO_PROVEN_EDGE (control lock) | NO_EDGE |
| EXP-CP4B | 2026-09-04 | same, ATR exits (2x/3x ATR14) | same | pre-freeze | OOS 2/5, avg −7.78% | NO_PROVEN_EDGE | NO_EDGE |
| EXP-CP4C | 2026-09-04 | hit-rate diagnostics (ST/TA, h5/h20, M3) | latest-6-windows era | pre-freeze | 47.3–49.7% | NO_EDGE (diagnostic) | NO_EDGE |
| EXP-CP4D | 2026-09-04 | same on M15/H1 | M15/H1 (TZ-shifted bounds — documented defect, conclusion robust) | pre-freeze | 45.7–55.9%, no CI>50 | NO_EDGE (diagnostic) | NO_EDGE |
| EXP-CP5.5 | 2026-09-05 | H-A1-V1 + H-A2-V1 (IS measurement, frozen data be4fa581) | DS-CP5-MAIN | d3524bb | A1-h5 55.60% [52.97-58.22]; econ +$11.03 gross | PASSED_IS (A1-h5 candidate) | — |
| EXP-CP5.6 | 2026-09-05 | corrected statistics (HAC+MBB+Bonferroni m=4) | DS-CP5-MAIN | 9184e5b | A1-h5 survives (LB 52.50/52.18); A2 fails | PASSED_IS (A1-h5 only) | — |
| EXP-CP5.7 | 2026-09-05 | robustness screens (12+9 variants; 18 SL/TP cells) | DS-CP5-MAIN | 9184e5b | A1-h5 ROBUST (10/12) | screening, no claims | — |
| EXP-CP5.9 | 2026-09-05 | H-A2-V2 (first-breakout) | DS-CP5-MAIN (IS) + DS-ARCH-OOS | 9184e5b | IS underpowered (LB≈46); OOS h5 40.74% | FAILED_OOS → RETIRED | OOS_FAILURE / NO_EDGE |
| EXP-CP6 | 2026-09-05 | H-A1-V1 + H-A2-V1 OOS replication | DS-CP6-OOS | 9184e5b | A1-h5 49.29% (LB 46.16/45.85); A1 econ −$4.33; A2 LB 49.27 | FAILED_REPLICATION | OOS_FAILURE / OVERFITTING_SUSPECTED |
| EXP-CP7 | 2026-09-05 | stress battery (streaks/worst windows, both datasets) | DS-CP5 + DS-CP6 | 9184e5b | streaks up to 18; A1 4/6 OOS windows < 50% | documented | — |

## Engineering loops (not research experiments)

CP19 audit → LOOP1-4 fixes → CP20 integration (12/12) → CP21 entry-point →
CP22 regression (54/54). See CP21_22_FINAL_SAFETY_GATE.md.
