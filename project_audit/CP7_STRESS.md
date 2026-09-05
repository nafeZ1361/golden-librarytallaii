# CP7 — ROBUSTNESS / STRESS TESTING (closure after CP6 FAILED REPLICATION)
Generated: 2026-09-05T17:11:17 | stress battery registered before computation; both datasets
  evaluated: CP5 frozen (in-sample era) AND CP6 OOS (independent).

- A1 h5:
    cp5_h5: rate=55.6% max_loss_streak=9 | per-window (w, n, rate%, streak): [(1, 226, np.float64(56.19), 5), (2, 224, np.float64(59.82), 7), (3, 235, np.float64(56.6), 6), (4, 218, np.float64(55.05), 6), (5, 227, np.float64(51.1), 7), (6, 246, np.float64(54.88), 9)]
    cp6_h5: rate=49.29% max_loss_streak=9 | per-window (w, n, rate%, streak): [(1, 242, np.float64(43.39), 9), (2, 220, np.float64(49.09), 7), (3, 206, np.float64(46.12), 9), (4, 210, np.float64(56.19), 4), (5, 248, np.float64(45.16), 8), (6, 211, np.float64(57.35), 4)]
- A1 h20:
    cp5_h20: rate=51.97% max_loss_streak=8 | per-window (w, n, rate%, streak): [(1, 226, np.float64(52.21), 8), (2, 224, np.float64(51.34), 8), (3, 234, np.float64(54.27), 6), (4, 217, np.float64(53.46), 5), (5, 227, np.float64(48.9), 7), (6, 246, np.float64(51.63), 7)]
    cp6_h20: rate=51.46% max_loss_streak=9 | per-window (w, n, rate%, streak): [(1, 242, np.float64(47.11), 9), (2, 219, np.float64(48.86), 7), (3, 206, np.float64(59.22), 5), (4, 210, np.float64(57.62), 5), (5, 248, np.float64(43.95), 9), (6, 210, np.float64(54.29), 7)]
- A2 h5:
    cp5_h5: rate=52.56% max_loss_streak=7 | per-window (w, n, rate%, streak): [(1, 833, np.float64(54.26), 7), (2, 464, np.float64(52.16), 6), (3, 116, np.float64(47.41), 5), (4, 150, np.float64(51.33), 5), (5, 129, np.float64(52.71), 6), (6, 163, np.float64(49.69), 5)]
    cp6_h5: rate=50.96% max_loss_streak=10 | per-window (w, n, rate%, streak): [(1, 767, np.float64(51.89), 7), (2, 759, np.float64(50.2), 9), (3, 897, np.float64(52.29), 8), (4, 907, np.float64(52.15), 9), (5, 603, np.float64(50.91), 9), (6, 1024, np.float64(48.63), 10)]
- A2 h20:
    cp5_h20: rate=51.65% max_loss_streak=14 | per-window (w, n, rate%, streak): [(1, 833, np.float64(53.06), 14), (2, 464, np.float64(52.37), 10), (3, 116, np.float64(51.72), 7), (4, 149, np.float64(46.98), 7), (5, 129, np.float64(55.04), 5), (6, 160, np.float64(43.75), 8)]
    cp6_h20: rate=50.5% max_loss_streak=18 | per-window (w, n, rate%, streak): [(1, 765, np.float64(58.17), 17), (2, 759, np.float64(48.88), 17), (3, 897, np.float64(51.39), 13), (4, 907, np.float64(48.51), 18), (5, 600, np.float64(49.17), 13), (6, 1021, np.float64(47.7), 14)]

## S3 — cost stress recap (frozen economics, both datasets)
- CP5 frozen: A1 exp $11.03 -> $7.53 (C1) -> $5.03 (C2); A2 $10.66 -> $7.16 -> $4.66; break-even ~11 pips. (CP5_ECONOMIC_VALIDATION.md)
- CP6 OOS: A1 expC0 = -$4.33/trade (negative BEFORE costs); A2 expC0 = +$4.01 -> +$0.51 under C1 (effectively zero). FAILED ECONOMIC REPLICATION for A1; A2 economically marginal on OOS.

## S4/S5 — documented limitations (no computation invented)
- regime split: no regime labels exist in the frozen artifacts; a regime study would require a pre-registered labeling method — deferred to any future track.
- entry-timing (next-bar-open) variant: would require an unregistered engine change; the registered convention (same-bar close) and its live divergence are documented (CP2/CP3). Not invented post-hoc.
- gap sensitivity: CP5 had 6 flagged gaps (none inside OR windows); CP6 OOS had zero unclassified gaps; A2's registered gap-free-OR rule structurally guards.
