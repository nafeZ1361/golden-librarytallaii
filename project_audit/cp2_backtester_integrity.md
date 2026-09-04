# CP2 — BACKTESTER INTEGRITY REPORT

Checkpoint: CP2 | Status: **PASS WITH RISKS** | Date: 2026-09-04
Evidence: `project_audit/cp2_verification.json` (12/12 tests PASS), `cp2_backtester_integrity_test.py`

## 1. Executive Summary
The backtest engine (`backtest()` in `backtest/hashem_backtest.py`) is **correct in its core execution semantics**: entries occur at the signal bar's close with exact SL/TP arithmetic, profit math is dimensionally consistent and BUY/SELL symmetric, the engine is deterministic, single-position, and reproduces its locked baseline exactly on replay. Optimistic modeling characteristics exist and are now precisely measured (same-candle TP-priority, gap fills at SL/TP price, zero costs, end-of-data drop) — they bias absolute ROI **upward**, not randomly. Verdict: PASS WITH RISKS.

## 2. Scope
`backtest()` execution logic + sizing/costs/determinism, verified via 12 controlled synthetic scenarios + baseline replay. Production source unchanged.

## 3. Entry Audit — CONFIRMED
Entry = same bar `i` where `trigger[i]` AND `confirmation[i]` agree, at `close[i]`; forming candle cannot enter the coherent pipeline (CP1: start_pos proof); single position (S6: 2nd signal ignored); BUY/SELL mirrored (S8).
`CODE: backtest() ≈95–140 → TEST: S1,S6 → RESULT: PASS → VERDICT: entry semantics correct`

## 4. SL/TP Audit — CONFIRMED
pip = 10^(−digits)×10 = **$0.1** (digits=2, live terminal); SL=100 pips=$10, TP=200 pips=$20; buy: SL=entry−10/TP=entry+20; sell mirrored. Silent fallback digits=5 (if terminal down) would shrink distances to $0.01/$0.02 — guarded in all our runners by digits logging (cp1/coherent scripts) — RISK noted.

## 5. Same-Candle TP/SL — CONFIRMED (optimistic)
One candle touching both → engine exits at **TP** (checked first). Measured (S3): optimistic delta = **+$300 per 0.1-lot scenario** (=3R at 2% risk; TP +$200 vs SL −$100). Production unchanged; conservative switch deferred (recommendation recorded).

## 6. Gap Handling — CONFIRMED (optimistic)
Gap through TP → filled at TP price (S4: +$200; realistic open-fill ≈ +$300). Gap through SL → filled at SL price (S5: −$100; realistic loss larger). Engine never uses the open price for gapped exits.

## 7. End-of-Data — CONFIRMED
Open position at dataset end is **silently dropped** (S7: 0 trades recorded, P/L excluded). Minor negative bias to trade counts; no P/L distortion of recorded trades.

## 8. Costs — CONFIRMED ABSENCE
No spread, commission, slippage, or swap anywhere in the engine. Absolute ROIs are optimistic by the full cost load (XAUUSD spread typically 20-35 cents ≈ 2-3.5 pips per round trip → at 100-pip SL / 200-pip TP ≈ 1-1.75% of the SL distance per trade... measured impact deferred to CP5 cost-injection runs).

## 9. Position Sizing / Risk — CONFIRMED
risk_percent=2% of **initial** balance → $100 risk/trade constant; lot = 100/(100 pips × pip_value_per_lot≈$10) = 0.1 lot; min-lot clamp 0.01 applied; **broker lot-step rounding NOT enforced** (low risk at these sizes; flagged). Risk is genuinely constant across trades/windows.

## 10. BUY/SELL Symmetry — CONFIRMED
Mirrored entry/SL/TP/priority/profit verified numerically (S8a/S8b == S1/S2 exactly).

## 11. Determinism — CONFIRMED
Synthetic re-run identical (S10) + two prior real-data confirmations (determinism_test, lag baseline recheck, CP1 re-run). Trade count/WR/P&L/balance fully reproducible on frozen inputs.

## 12. Invariants — ALL PASS
No-signal→no-trade ✅ | single simultaneous position ✅ | SL/TP defined only at entry ✅ | profit math consistent with entry/exit/lot (2:1 RR exact ratio) ✅ | stats count == trade records ✅

## 13. Baseline Replay — CONFIRMED
Frozen determinism cache replay reproduces the locked artifact **exactly**: 75 trades / 42.67% / $2,100 / $7,100 / 42.00% — bit-for-bit expectations.

## 14. Confirmed Facts
Correct entry/exit math; deterministic; symmetric; single-position; optimistic same-candle & gap fills; zero costs; end-drop; constant risk; lot-step gap.

## 15. Unknowns
Real-market fill quality vs optimistic gap/TP assumptions (needs live dry-run comparison, CP7).

## 16. Risks
Optimistic biases (§5/§6/§8) inflate absolute ROI → treat backtest ROIs as upper bounds until CP5 cost/robustness passes. digits=5 silent fallback (guarded in our runners).

## 17. Blockers
None.

## 18. Evidence Files
`cp2_backtester_integrity_test.py`, `project_audit/cp2_verification.json`, baseline replay inputs in `project_audit/determinism_cache/`.

## 19. Final Verdict
**CP2 PASS WITH RISKS** — engine trustworthy as a measurement instrument; its absolute numbers carry documented optimistic biases to be neutralized/quantified at CP5.

## 20. Next Checkpoint
CP3 — Strategy Integrity (proceeding per master directive).
