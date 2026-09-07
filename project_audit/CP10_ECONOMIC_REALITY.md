# CP10 — ECONOMIC REALITY TEST

Generated: 2026-09-05. Costs pre-registered (C0/C1/C2, $1/pip at 0.1 lot);
applied identically on BOTH datasets.

| Strategy | Dataset | expC0 | expC1 (3.5p) | expC2 (6p) | Break-even |
|---|---|---|---|---|---|
| A1 | CP5 frozen (in-sample era) | +$11.03 | +$7.53 | +$5.03 | ~11.0 pips |
| A1 | CP6 OOS (independent) | **-$4.33** | -$7.83 | -$10.33 | n/a (negative) |
| A2 | CP5 frozen | +$10.66 | +$7.16 | +$4.66 | ~10.7 pips |
| A2 | CP6 OOS | +$4.01 | +$0.51 | -$1.99 | ~4.0 pips |

## Verdict

- A1: **FAILED ECONOMIC VALIDATION** — gross expectancy is negative on
  independent data; costs make it worse. The in-sample margin (~11 pips
  break-even vs 2-4 pips realistic costs) was an artifact of the period.
- A2: **FRAGILE ECONOMIC EDGE at best** — +$0.51/trade under C1 on OOS
  (effectively zero), negative under C2. Not deployable.
- Standing limitations: constant-cost arithmetic; same-bar-close + TP-first
  optimistic conventions (documented CP2/CP3); no slippage distribution.
- **NO ECONOMIC EDGE** survives for either strategy under honest evaluation.
