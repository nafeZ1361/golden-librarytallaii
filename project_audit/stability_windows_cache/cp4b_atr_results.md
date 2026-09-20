CP4b B0 DIAGNOSTIC - ATR-BASED EXITS (SL=2xATR14, TP=3xATR14) - 2026-09-04 12:42:50.692462
harness equivalence (fixed mode vs run_backtest): True
folds=5 | IS-only selection | min 10 IS trades

Fold  Sel(ST/TA)       IS_ROI   OOS_ROI    OOS_TR    OOS_PF    Degrad.
Fold  Sel(ST/TA)       IS_ROI   OOS_ROI    OOS_TR    OOS_PF    Degrad.
----------------------------------------------------------------------
1     10/80            -19.52    -64.06        95      0.54     -44.54
2     10/60             -2.58     23.54       103      1.20      26.13
3     10/80             36.76     -5.24        80      0.95     -42.00
4     14/60             22.88    -36.68        76      0.65     -59.56
5     10/80             22.57     43.53        93      1.46      20.96

folds with POSITIVE best-IS ROI: 3/5
OOS: profitable=2 losing=3 avg=-7.78
OOS expectancy avg=-5.26 $/trade

BRANCH VERDICT: EXIT-GEOMETRY WAS THE PROBLEM -> rerun CP4 with ATR exits + fuller grid