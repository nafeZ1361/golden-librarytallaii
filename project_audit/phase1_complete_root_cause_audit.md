# PHASE 1 — COMPLETE ROOT-CAUSE AUDIT (v2, full-scope)

Mode: READ-ONLY / static trace. No code/parameter/strategy/config change, no optimization, no new backtest, no order, no install. All listed files found and fully read in this session; nothing NOT FOUND. Line numbers "≈" verified by function content.

---

## 1. EXECUTIVE SUMMARY

The 6-window instability (+50/0/+8/-42/-26/+142) is **NOT a valid measurement of strategy stability**. Root cause (CONFIRMED, code-level):

**The signal generators never compute from the supplied window data.** `backtest_supertrend()` and `backtest_trend_ali()` internally call `backtest_candle(symbol, tf, limit)`, which always fetches **the most recent N bars from MT5** (`copy_rates_from_pos(..., start_pos=0)`). Signals are then joined to prices **by position only** (tail-slice + `"hold"` padding; no timestamp join). Therefore:

- `stability_windows_test.py` windows 1–5: prices = Dec 9 → Jul 22 slices, signals = **the latest month at compute time (≈ Aug/Sep)** → contaminated pairing. **INVALID as a stability test.**
- Window 6: near-coherent but boundary-shifted (~5–20 bars) → +142% vs the coherent baseline +42% (determinism cache, same calendar month) — the gap is explained by misalignment + boundary shift, exact split NOT PROVEN.
- `lag_bias_test_window2.py`: prices June/July × signals Aug/Sep → **INVALID**.
- `determinism_test.py` and `lag_bias_test.py` (window 1, frozen coherent cache): **VALID** for their claims.
- True per-month strategy stability: **never coherently measured → UNKNOWN**.

Secondary confirmed optimism/fragility sources: same-bar zero-latency entry, same-bar TP-priority-over-SL, no gap/spread/slippage handling, silent drop of the still-open end-of-data position, HA recursive seeding, ATR/supertrend warm-up, trend_ali head padding, forming-candle inclusion.

## 2. CURRENT BASELINE STRATEGY

Symbol XAUUSD. | TF 3m | HA candles | Supertrend(10, 3.0) | trend_ali(60, 6.0, Hma) | agreement same-bar | SL 100 pips ($10) | TP 200 pips ($20) | risk 2% of initial balance | lag OFF | optimization OFF. Entry = same-bar close. Engine = `backtest()` in `backtest/hashem_backtest.py`. Params source = `backtest/backtester.py` (verbatim; also auto-read by stability script via regex+eval — matched).

## 3. DATA PIPELINE (per stage: FILE / FUNCTION / LINE / INPUT / OUTPUT)

1. Fetch prices — `hashem_backtest.py` / `backtest_candle()` / ≈1290–1320 / symbol,tf,limit / latest `limit` M3 bars (start_pos=0, includes forming bar), optional recursive HA transform (≈1322–1345).
2. Bulk variant — `stability_windows_test.py` / `main()` / one `copy_rates_from_pos(start_pos=1, 86400)` → sorted ascending → sliced into 6×14,400-bar windows.
3. Fetch signals — `backtest/indicators.py` / `backtest_supertrend()` ≈51–135 and `backtest_trend_ali()` ≈566–660 / symbol,tf,limit / **own fresh MT5 fetch each** (latest N bars at call time), HA-transformed, indicator computed, tail-sliced to `limit`.
4. Align — `backtester.py` ≈40–54; `stability_windows_test.py align_signals()`; `determinism_test.py freeze_inputs()` / tail-trim + head-pad 'hold' / positional only.
5. Simulate — `hashem_backtest.py` / `backtest()` ≈21–300 / df+signal+confirmation+params / trades, stats print (≈304–325), HTML report (≈668, 725–732).

## 4. MT5 DATA AUDIT

| Item | Status | Evidence |
|---|---|---|
| Current/incomplete candle included | CONFIRMED | `backtest_candle` start_pos=0 (≈1316). Stability bulk df uses start_pos=1 (excludes) → df/signal boundary inconsistency. |
| Exact-timestamp windows | NOT FOUND | Windows are bar-count slices (14,400 bars), not timestamp-defined; boundaries drift run-to-run. |
| Expected candle count | CONFIRMED correct | Requested 86,400, received 86,400 (run log). |
| Gap handling | NOT FOUND (no code) | No gap checks anywhere; weekend/holiday time gaps simply absent (bar-based windows ≈ 30 *trading* days ≈ 36+ calendar days — observed Dec 9→Jan 26). Price gaps between adjacent bars are not handled in exits. |
| Duplicate timestamps | NOT PROVEN | No dedup/check anywhere; stability script sorts by time; no duplicates observed. |
| Timezone | CONFIRMED absent | `pd.to_datetime(unit='s')` → naive broker-server-time rendered as if UTC; no conversion anywhere in the backtest path (`get_broker_offset` exists only in the live module, unused here). |
| Different fetches → different datasets | CONFIRMED | Each `backtest_candle` call returns latest-N at its own wall-clock moment (core root cause, §5). |
| Array order assumption | CONFIRMED (by consistent behavior + API semantics) | `backtest_candle` never sorts; HA recursion treats iloc[0] as oldest. Stability script sorts defensively. |

## 5. CRITICAL TEST — SAME WINDOW / DIFFERENT DATASET

**Yes, Signal(A) ≠ Signal(B) is possible — and worse: the pipeline never even attempts Signal(A).**
- Because of §3-3, the signal series is always `f(latest N bars at call time)`; the "supplied window" is irrelevant. Dataset B (multi-month, sliced) gets the same newest-month signals as Dataset A would.
- Additional drift: fetch #1 (df) vs fetch #2 (supertrend) vs fetch #3 (trend_ali) happen seconds-to-minutes apart → 0–k new 3m bars → positional shift of the whole series by k bars.
- Warm-up sensitivity adds more: HA recursion seed (first bar), ATR rma seed (iloc[0]), supertrend init (prev_trend=1), trend_ali HMA warm-up (~378 bars) + head padding (~17 bars).
- Verdict: CONFIRMED mechanism. Magnitude of each contributor = NOT PROVEN (needs instrumented runs, §21).

## 6. HEIKIN-ASHI AUDIT

`hashem_backtest.py backtest_candle(heikin_ashi=True)` ≈1322–1345: HA_Close[i]=(O+H+L+C)/4; **HA_Open[i]=(HA_Open[i-1]+HA_Close[i-1])/2** (recursive, seeded at i=0); HA_High/Low = max/min with raw. Dependency on previous candles: CONFIRMED. Window start changes early HA: CONFIRMED. Decay length: NOT PROVEN. Can change signals: CONFIRMED as mechanism (flip points shift). Required test defined in §21 (T3).

## 7. SUPERTREND AUDIT

`backtest/indicators.py backtest_supertrend()` ≈51–135.
- Computed on its OWN fetched HA df — **not on the caller's df**: CONFIRMED.
- ATR: custom rma seeded with series.iloc[0]; warm-up ≈ atr_period (10) bars before stabilization (approx). CONFIRMED code; exact warm-up length NOT PROVEN.
- Bands/trend/flip: standard supertrend recursion with prev_up/prev_dn/prev_trend init (0/0/1) — initialization-dependent. CONFIRMED.
- Current-candle dependency: last element from forming bar (fetch pos 0) → tail repaint. CONFIRMED.
- Lookahead inside loop: NOT FOUND. Repainting: tail only (CONFIRMED).
- warm-up needed: ≈ atr_period + first flip distance; exact NOT PROVEN.

## 8. TREND ALI AUDIT

`backtest_trend_ali()` ≈566–660.
- Requests more than window? required_limit = max(limit, 1800) = 14,400 = window (equal here; for smaller windows it would over-fetch). CONFIRMED.
- Re-fetches from MT5 instead of using input df: CONFIRMED (B-finding).
- Result differs on larger dataset: YES — always recomputed from latest bars. CONFIRMED.
- Warm-up: ≈360+18 bars (HMA chain). CONFIRMED.
- Padding: head-pad with constant hull_values[0] when len(hull)<limit (≈17 bars for 14,400). CONFIRMED.
- Positional tail alignment: CONFIRMED (`hull_values[-limit:]`, `position_list[-limit:]`).

## 9. SIGNAL GENERATION

- `backtest_supertrend()['signal']` = **event** series: 'buy' only on flip bar (trend −1→1), 'sell' on (1→−1), else 'hold'; None in NaN warm-up rows.
- `backtest_trend_ali()['trend']` = **state** series: 'buy' iff hull[i] > hull[i−2], else 'sell' (per bar).
- Entry condition in `backtest()`: `trigger[i]=='buy' AND confirmation[i]=='buy'` (same bar i) → BUY; mirrored for SELL. So: Supertrend-FLIP-on-bar-i AND trend_ali-state-agrees-on-bar-i. Both are computed from data up to and including bar i (which includes close[i]).
- Signals relate to bar i (not i−1/i−2) in the baseline; the live path's [−2]/[−3] discipline is NOT applied here (lag OFF).

## 10. TIMESTAMP ALIGNMENT

All alignment occurrences: `backtester.py` ≈46–54 ([-len(df):] slices, 'hold' pads); `stability_windows_test.py align_signals()` (same); `determinism_test.py`/`lag_bias_test.py` freeze/align (same); `backtest_trend_ali` internal tail-slice + head-pad; `backtest_supertrend` internal tail-slice. Uses iloc/[-1]/[-2]/[-3]/min_len/padding — **no zip-on-time, no timestamp assertion anywhere**. `signal[i] == confirmation[i] == df.iloc[i]` same-timestamp guarantee: **NOT FOUND** (position-based only). CONFIRMED.

## 11. CRITICAL QUESTION — stability_windows_test.py

Did it do `Window1 Data → Window1 Indicators → Window1 Signals → Window1 Backtest`? **NO.**
Code chain: df = one bulk fetch (start_pos=1, Dec 9 → Sep 3) → per window: `generate_signals(df_slice)` → `backtest_supertrend(SYMBOL,TF,14400,…)` → internal `backtest_candle` → **latest 14,400 bars at compute time**. For windows 1–5 that is ≈ Aug 4 → Sep 3 (+ minutes of compute drift between windows), laid positionally onto Dec→Jul price slices. Additionally df used start_pos=1 vs signal fetches start_pos=0.
**VERDICT: INVALID (windows 1–5 contaminated by cross-month signal pairing). Window 6: PARTIALLY VALID (near-coherent, ~5–20 bar boundary shift).** The 6-window table must not be used as evidence of strategy instability or profitability.

## 12. ENTRY LOGIC

Conditions/price/current-candle/duplicates: see §9 + `backtest()` ≈95–140. Entry = same-bar close; no next-bar delay (lag OFF); duplicate entries impossible while a position is open (one position per engine run); opposite signal ignored for entry (a new signal while in position does nothing since `current_position is not None`).

## 13. EXIT LOGIC

TP: bar.high ≥ tp → exit at tp_price (gap-through still exits at tp, not open). SL: bar.low ≤ sl → exit at sl_price (same gap issue). **Same-candle TP&SL: TP first — code resolves the market ambiguity optimistically (CONFIRMED).** Risk-free OFF. Opposite-signal close OFF. Manual close OFF. End of dataset: open position silently dropped (not counted). No costs.

## 14. RISK / POSITION SIZE

`position_size_mode='risk_percent'`, `risk_based_on='initial'` → risk $ = 5000×2% = $100 constant per trade across ALL windows; SL distance fixed 100 pips → constant lot per trade; pip value from live MT5 symbol info with hardcoded fallback table. **Comparable across windows: CONFIRMED.** (Fallback activates only if terminal unreachable; in our runs it didn't.)

## 15. DETERMINISM FINDINGS

`determinism_test.py` (2026-09-03 15:17): two runs on byte-identical frozen df/signals → **identical statistics** (75/32/43/42.67/2100/7100/42.00) and HTML identical after timestamp normalization; stdout differed only in the timestamped report filename. **CONFIRMED: `backtest()` is deterministic on identical inputs.** Signal *ingestion* layer is wall-clock dependent (self-fetch) → pipeline as a whole is deterministic only on frozen inputs. `lag_bias_test.py` baseline recheck reproduced the locked baseline exactly — second confirmation.

## 16. LAG TEST FINDINGS (existing evidence only; no new runs)

- Window 1 (coherent frozen pairing): baseline 75 trades / 42.67% / +42% → lagged-1: 81 / 43.21% / **+48%** (lag improved).
- Window 2 test: **INVALID** (June/July prices × Aug/Sep signals — see §11 logic); its numbers (-56%/-42%) must not be interpreted.

## 17. SIX-WINDOW TEST AUDIT (line-by-line)

Fetch: one `copy_rates_from_pos(start_pos=1, 86400)` — correct count, forming candle excluded for prices. Split: positional 6×14,400 slices — deterministic but bar-count-based. Signals: `generate_signals()` → **self-fetching functions** → latest-month data at each compute moment → **NOT window data**. Per-window independence: price-wise yes, signal-wise no. Params: verbatim baseline (auto-extracted, matched). Real `backtest()` output used: yes. **VERDICT: INVALID** (as a stability test), for the §11 reason. What it accidentally demonstrates: sensitivity of the *pipeline output* to data provenance — itself evidence of the root cause.

## 18. ROOT CAUSE RANKING

| # | ROOT CAUSE | STATUS | EVIDENCE | IMPACT | CONFIDENCE |
|---|---|---|---|---|---|
| 1 | Signal functions self-fetch latest-N bars, ignoring supplied df | **CRITICAL** | `backtest/indicators.py` ≈57–60, ≈573–577; `backtest_candle` ≈1316 | Invalidates cross-window/cached comparisons | CONFIRMED |
| 2 | Position-only alignment (no timestamp join) | **CRITICAL** | align blocks (§10) | Silent pairing of different timestamps | CONFIRMED |
| 3 | Tight SL/TP ($10/$20) amplifying misalignment into full trade-set flips | HIGH | params + pip math ≈45–50, ≈34–37 | Explains 42↔142 magnitude | CONFIRMED (param); amplification size NOT PROVEN |
| 4 | Inter-fetch timing drift (df vs supertrend vs trend_ali) | HIGH | three fetches at T1<T2<T3 | k-bar positional shift | CONFIRMED mechanism; k NOT PROVEN |
| 5 | HA recursive seed + ATR/supertrend warm-up + trend_ali head padding | MEDIUM | ≈1322–1345; ≈60–66; ≈566–660 | Boundary sensitivity of flip points | CONFIRMED code; ROI effect NOT PROVEN |
| 6 | Forming-candle inclusion (start_pos=0) + 0-vs-1 inconsistency | MEDIUM | ≈1316; stability bulk fetch | Tail repaint; boundary inconsistency | CONFIRMED |
| 7 | Same-bar entry + TP-priority + no costs + end-drop | MEDIUM (absolute-level optimism, not window-delta) | §12–13 | Inflates absolute ROI | CONFIRMED |
| 8 | No dedup/gap/tz checks | LOW | §4 | Hygiene risk | CONFIRMED absent |

## 19. CONFIRMED FACTS

1. Signal functions re-fetch latest-N bars from MT5 and never use supplied window data.
2. Alignment is positional everywhere; no timestamp join/assert exists.
3. `stability_windows_test.py` windows 1–5 paired old-month prices with new-month signals; window 6 near-coherent but shifted.
4. `backtest()` is deterministic on identical inputs (two independent confirmations).
5. Same-bar close entry; same-candle TP-priority; no gap/slippage/commission; open end position dropped.
6. HA_Open recursion; ATR rma seed; supertrend init; trend_ali ≈17-bar head padding; required_limit=14,400.
7. Risk sizing constant ($100/trade) across windows.
8. Bulk fetch used start_pos=1; signal fetches start_pos=0.
9. All parameters in the tests equal the declared baseline.

## 20. HYPOTHESES / NOT PROVEN

- Exact decay length of HA seed influence (bars). NOT PROVEN.
- Split of the +42%→+142% gap between boundary shift, inter-fetch drift, and HA/warm-up effects. NOT PROVEN.
- Whether a coherent per-month scan would show genuine strategy instability (plausible given W1-coherent +42% vs no coherent data for other months — but NOT PROVEN).
- Practical ROI size of the TP-priority optimism and end-position drop. NOT PROVEN.
- Duplicate/gap anomalies in MT5 history. NOT PROVEN (none observed).

## 21. REQUIRED CONTROLLED TESTS (defined only — NOT executed)

| Pri | NAME | PURPOSE | INPUT | EXPECTED OBSERVATION | PASS | FAIL |
|---|---|---|---|---|---|---|
| 1 | T1 Coherent re-scan | True 6-window stability | Signals computed from the SAME sliced df (df-parameterized functions) | 6 coherent ROIs | ROIs reproducible under re-run with identical slice boundaries | ROIs flip under tiny boundary shifts even with coherent pairing |
| 2 | T2 Provenance assertion | Prove misalignment empirically | Log df.time[0/-1] + signal-fetch boundary per call | Equal/different timestamp ranges printed | All three ranges identical per window | Ranges differ (confirms §5) |
| 3 | T3 Boundary-shift sensitivity | Isolate HA/warm-up effect | Coherent month, start shifted 0/1/5/35 candles | ROI drift curve | Drift negligible (<a few %) | Large drift → HA/warm-up material |
| 4 | T4 TP/SL ordering | Upper bound of same-candle optimism | Same inputs, SL-priority variant | Delta vs baseline | Delta small | Delta large → bias material |
| 5 | T5 Gap/open-price exits | Gap realism | Exits at open price when gapped through | Delta vs tp/sl-price exits | Small | Large |

## 22. MINIMUM REQUIRED FIXES (proposal only — nothing changed)

1. **df-parameterization**: add optional `df=None` to `backtest_supertrend()`/`backtest_trend_ali()`; when provided, skip internal fetch (smallest possible diff; default behavior unchanged).
2. **Timestamp join/assert**: align via `time` column (or assert equality) instead of position; warn on mismatch.
3. **start_pos=1** uniformly (exclude forming candle) everywhere.
4. (Later, after T4/T5): SL-priority option, open-price gap exits, spread/commission parameter.
Fix 1+2+3 together convert the pipeline from "latest-N + positional" to coherent pairing and are prerequisites for any trustworthy stability statement.

## 23(=final). FINAL PHASE 1 CONCLUSION

The six-window instability is **INVALID as strategy evidence** — it primarily measures a data-provenance defect (self-fetching signals + positional alignment). The engine itself is deterministic; the ingestion layer is wall-clock dependent. True cross-month stability has never been coherently measured and is UNKNOWN until T1 runs. No fix was applied; no controlled test was executed.

STOP — no further phase started.
