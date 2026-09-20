# HYPOTHESIS GENERATOR POLICY (R3) — how new hypotheses may be created

## Mandatory properties of every generated hypothesis

1. **Economic rationale** — a mechanism with a plausible counterpart
   (who loses money to this edge, and why does the mispricing persist?).
2. **Testable & falsifiable** — a directional prediction with a horizon and a
   registered rejection rule.
3. **Bounded complexity** — MAX_FEATURES=3, MAX_PARAMETERS=4, NO parameter
   grids, MAX_SEARCH_SPACE=0 (one configuration per hypothesis).
4. **Registered before any run** — via RESEARCH_CONTRACT_TEMPLATE.md.
5. **Structural novelty** — not a parameter re-take of a retired hypothesis
   (check HYPOTHESIS_REGISTRY.md first); not derived from OOS results of
   retired variants.

## Allowed hypothesis sources (non-exhaustive)

Market structure (OR/session), momentum, mean-reversion, volatility regimes,
trend persistence, session effects, tick-activity/volume proxies, price-action
patterns, cross-timeframe relationships, statistical anomalies.

## Forbidden generation methods

Brute-force combination search; selecting the best CP5.7 grid cell as a "new"
hypothesis; mining the burned datasets for patterns; post-hoc horizon/threshold
changes; survivorship-filtered idea lists; anything justified only by backtest
profit.

## Complexity budget (program level)

- MAX_HYPOTHESIS_VARIANTS = 10 total program-wide (3 consumed: A1-v1, A2-v1,
  A2-v2 — remaining: 7, of which at most 3 may share a family).
- MAX_TECHNICAL_REPAIR_LOOPS = 5 per hypothesis.
- Every retirement is final for that variant; the slot is consumed.

## Next-cycle queue (proposals — NOT yet registered, no priority order)

1. **Session-conditioned volatility breakout** — rationale: breakout failure
   in A2-v1/v2 was measured across the FULL day; the Asian-session range is
   structurally different (lower liquidity, mean-reverting); restricting
   breakout windows to London/NY overlap changes the traded population
   structurally (different mechanism, not a parameter tweak).
2. **Volatility-regime gate on A1-style mean reversion** — rationale: A1-v1
   edge was period-specific; an ATR-percentile regime filter is the direct
   structural answer IF motivated by in-sample diagnostics only.
3. **Failed-breakout (fade) hypothesis** — rationale: A2-v2 OOS h5 = 40.74%
   (significantly BELOW 50) is itself a directional finding registered in the
   evidence base: first-breakouts in that archive period REVERSED. A fade
   variant inverts the prediction; NOTE: this reuses the same event population
   — requires a contract that declares the inversion and consumes a NEW OOS
   reserve.
