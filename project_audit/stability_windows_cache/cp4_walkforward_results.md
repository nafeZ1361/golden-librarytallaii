CP4 WALK-FORWARD RESULTS (coherent df= pipeline) - 2026-09-04 11:15:56.591369
grid=11 combos | folds=5 | selection=IS-only ROI (min 10 trades) | SL/TP fixed 100/200
engine equivalence backtest()==run_backtest(): True

Fold  Sel(ST/TA)       IS_ROI   OOS_ROI    OOS_TR    OOS_PF    Degrad.
----------------------------------------------------------------------
1     14/60            -22.00    -26.00        67      0.73      -4.00
2     10/60            -24.00     -8.00        64      0.91      16.00
3     10/60             28.00     22.00        88      1.20      -6.00
4     14/60             32.00    -62.00        73      0.47     -94.00
5     10/80            -22.00     56.00        80      1.64      78.00

OOS windows: 5 | profitable=2 losing=3
OOS ROI avg=-3.60 min=-62.000000000000085 max=56.00000000000001
IS->OOS degradation avg=-2.00 (positive=OOS worse)
OOS expectancy avg=-4.12 $/trade

EDGE VERDICT: NO PROVEN EDGE