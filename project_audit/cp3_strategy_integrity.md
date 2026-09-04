# CP3 — STRATEGY INTEGRITY REPORT

Checkpoint: CP3 | Status: **PASS WITH RISKS** | Date: 2026-09-04
Evidence: `project_audit/cp3_verification.json` (7/7 PASS), `cp3_strategy_integrity_test.py`, Phase 0/1 audit trail.

## 1. Scope
Strategy decision logic only (no optimization, no parameters changed): tested baseline (Supertrend flip + trend_ali agreement), the 8 notebook strategies, ABCD (module/stg.py), and risk-response logic.

## 2. Verified (dynamic, 7/7 PASS)
1. `Trend_change_signal` closed-bar flip semantics (buy/sell/hold) — 3 cases.
2. `_safe_swings` anti-repaint guard drops unconfirmed swings (ABCD) — crafted proof.
3. Baseline agreement rule (ST-flip bar + TA state, same bar) — proven; consumption mechanics already proven in CP2 (S1/S6).
4. ABCD risk response: risk **halves** after consecutive losses (anti-martingale); no escalation anywhere in stg.py (source-inspected).

## 3. Verified (static)
5. Notebook confirm-indicators (adx/ichimoku/sar/macd/keltner/trendmagic/vidya/trendali): decision paths consume closed-bar values ([-2]/[-3]) — no future-shift consumption. Exception: `sar_signal` reads `candles[-1]` close → forming-bar exposure in LIVE use (documented → CP7 dry-run will quantify).
6. ichimoku lagging span `shift(-26)` is computed but NOT consumed by the strategy decision (future-data isolation confirmed).
7. `risk_corrector_comment` escalation (toward max_risk=100) applies to ALL notebook live strategies — CONFIRMED HIGH-RISK (Phase 0 finding); **excluded by design from bot_runner.py**.

## 4. Strategy-level integrity findings
- Only the baseline (ST+TA) has coherent performance evidence: 6-window avg **-13.3%**, 2/6 positive (T1+v2). Notebook strategies and ABCD have NO coherent validation yet (pre-fix numbers invalid).
- Live-vs-backtest timing divergence: backtest enters same-bar; live [-2] discipline = one-bar lag — measured once (window-1: lag IMPROVED ROI +6%); single window → risk documented for CP7.
- Gartley/Butterfly strategy code: MISSING (only state keys in bot_state.json) — cannot be validated.
- Notebook management layer (tp1_save_profit/smartTP/smartSL) alters effective RR vs the tested fixed 100/200 geometry — coherent validation of that combination does not exist.

## 5. Verdict
**PASS WITH RISKS** — decision logic is internally consistent, matches its claimed design, contains no lookahead in decision paths, and the anti-martingale response is verified. Risks: unproven coherent performance (except negative-for-baseline), live timing divergence, notebook live-path risk escalation (unresolved until CP6 runner replaces notebook execution).

## 6. Next
CP4 — Honest Optimization / Walk-Forward (design ready; only on the coherent df= pipeline; baseline strategy only).
