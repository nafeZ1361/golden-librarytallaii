# RESEARCH CONTRACT — CYCLE-R1 (two independent hypotheses, shared one-shot OOS)

Date registered: 2026-09-05 (BEFORE any evaluation of either hypothesis)
Variant budget: H-V3-1 = variant #4, H-V3-2 = variant #5 (of max 10).
Commit of this contract precedes the commit containing any result.

## H-V3-1 — Fade of first-breakouts (variant #4)

- Derivation (declared honestly): A2-v2's OOS h5 = 40.74% (significantly BELOW
  50%, n=189) on DS-ARCH-OOS is a registered directional finding: first
  breakouts in that period REVERSED. This hypothesis inverts the prediction.
  Consequence: its derivation period is design-informing -> IS, and its OOS is
  the fresh archive reserve (never seen).
- Events: EXACTLY the A2-v2 event population (frozen code
  `strategy_a2_v2_firstbreakout.py` reused as-is; same OR eligibility/params).
- Prediction (inverted): close[i+h] moves AGAINST the breakout direction in
  MORE THAN 50% of first-breakout events, h=5 and h=20.
- IS: DS-ARCH-OOS windows (cp6v2, 2024-06-26..2025-03-20).
- OOS: DS-R1-RESERVE (2021-06-26..2024-06-26, 6x14,400 — frozen this cycle).
- Economics: fade = inverted signals (buy<->sell) with the same registered
  geometry — evaluated as inverted-direction trades (exact, no approximation).

## H-V3-2 — Session-conditioned first-breakout (variant #5)

- Derivation: structural liquidity argument — A2 full-day populations mix the
  Asian low-liquidity regime with London/NY; restricting first-breakout events
  to the London/NY overlap (broker-hour window [12, 20) = UTC approximation,
  2 parameters) changes the traded population structurally. Motivated by
  in-sample/CP6 clustering diagnostics only; NOT by any archive result.
- Events: A2-v2 event rule + event bar's broker-hour must be within [12, 20).
  Same OR eligibility/params (OR 120 min, vol 1.5x). Implemented in
  `strategy_a4_v1_sessionbreakout.py` (new file, v2 untouched).
- IS: DS-CP5-MAIN (cp5 windows).
- OOS: DS-R1-RESERVE (shared one-shot consumption with H-V3-1).

## Joint OOS rule (registered)

- OOS consumed ONCE by this cycle for both hypotheses.
- Joint family: 4 cells (V3-1 h5/h20, V3-2 h5/h20) -> Bonferroni m=4.
- Constants unchanged: SEED=55056, N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h.
- A cell is CANDIDATE iff HAC-Bonf LB > 50% AND MBB-Bonf LB > 50% (on IS and
  separately on OOS). A hypothesis ADVANCES iff its primary horizon (h5) AND
  h20 are CANDIDATE on both datasets (strict both-horizons rule, unchanged).

## Acceptance / rejection

- ADVANCE: both horizons CANDIDATE in-sample AND on OOS + OOS gross economics
  positive under C1 (fade evaluated on inverted trades).
- Otherwise: RETIRED (recorded per taxonomy; the OOS reserve is burned for
  this cycle's family regardless of outcome).

## Complexity budget

H-V3-1: 0 new parameters (pure inversion). H-V3-2: 2 parameters (session
window). MAX_TECHNICAL_REPAIR_LOOPS=5 each.
