# CP11 — RISK VALIDATION

Generated: 2026-09-05. Risk evidence from the frozen artifacts (per-window
standalone runs, $5,000 initial, 2% = $100 risk/trade, 0.1 lot).

## Measured risk profile (fixed geometry SL100/TP200)

| Metric | A1 | A2 |
|---|---|---|
| Max drawdown (worst window, in-sample era) | 24.53% | 33.87% |
| Mean per-window drawdown | 17.22% | 22.41% |
| Max consecutive losses (hit-rate sequences, h5) | 9 (CP5) / 9 (OOS) | 7 / 10 |
| Max consecutive losses (h20) | 8 / 9 | 14 / 18 |
| OOS gross expectancy | **-$4.33/trade** | +$4.01 -> +$0.51 (C1) |
| Loss-stress at fixed $100 risk | a 9-loss streak = -$900 (9% of equity) | 10-18 streaks = -$1,000..-$1,800 |

## Assessment

- Even during the favorable in-sample era, single-window drawdowns reached
  24-34% at the registered 2% risk — with NO edge on independent data, these
  figures represent uncompensated risk (negative expectancy on OOS for A1).
- A2-h20 loss clustering (streaks up to 18, rho1=0.394) materially raises
  tail risk beyond the naive 2%-per-trade model.
- Monte Carlo/ruin analysis is MOOT: with zero proven edge, ruin probability
  tends to 1 in the long run (negative-drift random walk). Computing
  distributional ruin numbers would decorate a settled conclusion.
- **RISK VERDICT: UNACCEPTABLE FOR LIVE — there is no edge to compensate the
  measured drawdown/clustering profile. NO LIVE AUTHORIZATION** (also the
  formal CP18 outcome).
