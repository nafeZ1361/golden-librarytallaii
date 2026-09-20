# PHASE 1 ROOT-CAUSE AUDIT — Backtest Instability

Mode: READ-ONLY / static code trace only. Nothing was executed, modified, or fetched during this phase.
Scope: why the same strategy/parameters on "the same" 30-day periods produce dramatically different ROI under tiny data-window shifts.

---

## A. EXECUTIVE SUMMARY

The instability is **not primarily a strategy property** — it is an **architecture property of the data pipeline**.

Root cause chain (all CONFIRMED at code level):

1. `backtest_supertrend()` and `backtest_trend_ali()` **ignore the price DataFrame** they are supposed to score. Internally each calls `backtest_candle(symbol, tf, limit)`, which always fetches **the most recent N bars from MT5** (`copy_rates_from_pos(..., start_pos=0, ...)`).
2. Therefore a signal series always describes **"the latest N bars at the moment of the call"** — never the window of the `df` it will be paired with, unless that df *is* the latest N bars and all fetches happen within the same 3-minute bar.
3. Alignment between signals and prices is **purely positional** (tail-slicing + `"hold"` padding + index reset). **No timestamp join exists anywhere.**
4. Consequence: whenever `df` comes from a cache, a bulk fetch, a different `start_pos`, or a later fetch time, the pipeline silently pairs **signals of period X with prices of period Y**. Tiny fetch-timing differences (minutes) change the pairing → different entries → different trades → dramatically different ROI.

This explains the observed flips (same calendar month: **+42% → +142%** and **-56% → -26%**) and reclassifies the 6-window "instability": windows 1–5 of `stability_windows_test.py` were scored against signals belonging to a **different month** entirely. The 6-window table therefore does **not** measure strategy stability. **True per-month stability is currently UNKNOWN** (see M — required tests).

Secondary confirmed contributors: same-bar zero-latency entry, same-bar TP-priority-over-SL, no gap/spread/slippage handling, HA recursive seeding + ATR/supertrend warm-up, head-padding artifacts in `backtest_trend_ali`, and forming-candle inclusion (`start_pos=0`).

Correction of the previous turn's conclusion: "نوسان مداوم است" was **premature** — the 6-window spread is largely the misalignment artifact described above.

---

## B. DATA WINDOW DEPENDENCY

FINDING B1 — Signal functions fetch their own, always-newest data
```
FILE:       backtest/indicators.py
FUNCTION:   backtest_supertrend()
LINE/RANGE: ≈51–60 (def; required_limit = max(limit, atr_period*5); df = backtest_candle(symbol, tf, required_limit).copy())
OBSERVATION: The function signature accepts only symbol/tf/limit — it never receives the window df. It re-fetches the most recent `required_limit` bars itself.
IMPACT:      Signal series always describes the newest N bars at call time. Any df from cache/bulk/different start_pos is paired with foreign signals.
CONFIDENCE:  CONFIRMED
```

```
FILE:       backtest/indicators.py
FUNCTION:   backtest_trend_ali()
LINE/RANGE: ≈566–585 (final_length = int(length*length_mult) = 360; required_limit = max(limit, 1800); ohlc = backtest_candle(...))
OBSERVATION: Same self-fetching pattern. Then `hull_values[-limit:]` positional tail slice.
IMPACT:      Same as B1, plus warm-up/padding behavior (see E).
CONFIDENCE:  CONFIRMED
```

```
FILE:       backtest/hashem_backtest.py
FUNCTION:   backtest_candle()
LINE/RANGE: ≈1290–1320 (mt5.initialize(); rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, limit))
OBSERVATION: start_pos = 0 → the most recent returned bar is the currently forming candle; every call returns "latest N", never an arbitrary historical window.
IMPACT:      Makes "latest N" the only addressable window; combined with B1/B2 it fixes signal timing to wall-clock call time.
CONFIDENCE:  CONFIRMED
```

```
FILE:       backtest/hashem_backtest.py
FUNCTION:   backtest()
LINE/RANGE: ≈21–40 (def; mt5.initialize(); symbol_info → digits; bare except → digits = 5)
OBSERVATION: backtest() itself also touches MT5 for symbol digits; silent fallback to 5 changes pip size (0.1 → 0.001?) — with digits=2 observed, pip=0.1; SL_PIPS=100 → $10 SL, TP_PIPS=200 → $20 TP on gold.
IMPACT:      Tight SL/TP ($10/$20 on a ~$4400 instrument) makes results extremely sensitive to which exact bars get paired with signals.
CONFIDENCE:  CONFIRMED (code); digits value at runtime observed = 2 in prior authorized runs.
```

Per-context consequence table:

| Context | df source | signal source | coherent? |
|---|---|---|---|
| `backtest/backtester.py` (original) | backtest_candle @ T1 | backtest_candle @ T2,T3 (seconds later) | Yes if no new 3m bar formed between fetches; else 1–2 bar shift |
| `determinism_test.py` freeze | backtest_candle @ T1 | backtest_candle @ T2,T3 (seconds later) | Yes (coherent; this is why baseline reproduced exactly) |
| `lag_bias_test.py` (reuses frozen cache) | frozen @ T1 | frozen @ T1-T3 | Yes (coherent) |
| `lag_bias_test_window2.py` | `copy_rates_from_pos(start_pos=14400)` → June 8–Jul 22 | backtest_supertrend/trend_ali internal fetches → **latest** month (Jul 22–Sep 3) | **NO — prices of June/July paired with signals of Aug/Sep** |
| `stability_windows_test.py` windows 1–5 | one bulk fetch (Dec 9 → Sep 3), sliced | internal fetches at compute time → **latest month each time** | **NO — windows 1–5 scored against latest-month signals** |
| `stability_windows_test.py` window 6 | bulk-fetch slice ending 16:30 | internal fetch ending ~16:40+ | Near-coherent; ~5–20 bar boundary shift |

```
FILE:       stability_windows_test.py
FUNCTION:   main()/generate_signals()
LINE/RANGE: bulk fetch with start_pos=1; per-window generate_signals(df) → backtest_supertrend/backtest_trend_ali (self-fetching)
OBSERVATION: For the oldest window (Dec 9 → Jan 26), the signal series was computed on ≈ Aug 4 → Sep 3 data. Windows 1–5 shared nearly the same latest-month signal series (each successive compute a few bars later), each laid positionally onto a different month's prices.
IMPACT:      The 6-window ROI table (50/0/8/-42/-26/142) is not a strategy-stability measurement; it is a pairing artifact. Only window 6 is near-coherent, and even it differs from the coherent baseline (+42%) because of a ~35-candle boundary shift + residual inter-fetch drift.
CONFIDENCE:  CONFIRMED (mechanism from code); exact per-window drift magnitudes = NOT PROVEN without instrumented run (see M).
```

Answer to the mission's B-question: **YES** — a 30-day window computed standalone vs. as part of a larger dataset produces different signals, because the signal is never computed *from the supplied window* at all; it is recomputed from "latest N bars".

## C. HEIKIN-ASHI DEPENDENCY

```
FILE:       backtest/hashem_backtest.py
FUNCTION:   backtest_candle(heikin_ashi=True)
LINE/RANGE: ≈1322–1345
OBSERVATION: HA close[0] = (o+h+l+c)/4 of the first fetched bar; HA open[i] = (HA open[i-1] + HA close[i-1])/2 (recursive); HA high/low combine with raw high/low.
IMPACT:      Changing the first bar of the fetch changes the seed → the entire HA series shifts slightly → indicator flip points move. The dependency never fully decays (infinite impulse response of the recursion), but practically diminishes over bars; magnitude UNKNOWN without instrumented comparison.
CONFIDENCE:  CONFIRMED (recursion in code); decay length = NOT PROVEN
```
- HA Open depends on previous candles: **YES — CONFIRMED** (formula above).
- New window start changes early-window HA values: **YES — CONFIRMED** (new seed).
- Can move indicator flip points: **YES — CONFIRMED as possible mechanism** (supertrend/trend_ali consume HA closes); measured effect = NOT PROVEN.

## D. SUPERTREND DEPENDENCY

```
FILE:       backtest/indicators.py
FUNCTION:   backtest_supertrend()
LINE/RANGE: ≈60–135
OBSERVATION:
  - ATR: custom rma() seeded with result[0] = series.iloc[0] (first TR of fetched window) — warm-up dependent on window start.
  - Loop state: prev_up = 0, prev_dn = 0, prev_trend = 1 — arbitrary initialization; early trend state is arbitrary until first genuine flip.
  - Uses the HA df (candle_type='ha' → internal fetch with heikin_ashi=True).
  - No lookahead inside the loop (each bar uses bar i and i-1 data only).
IMPACT:      Flip indices depend on fetch start (seed + warm-up + HA recursion). With the self-fetching design (B1) this multiplies the positional-misalignment effect.
CONFIDENCE:  Initialization/warm-up dependency = CONFIRMED (code). Current-bar contamination inside supertrend itself = NOT FOUND beyond the start_pos=0 inclusion of the forming bar in its fetched df (the last signal element can change when that bar closes — CONFIRMED as tail repaint risk).
```

## E. TREND ALI DEPENDENCY

```
FILE:       backtest/indicators.py
FUNCTION:   backtest_trend_ali()
LINE/RANGE: ≈566–660
OBSERVATION:
  - final_length = 60×6 = 360; required_limit = max(limit, 1800) → 14,400.
  - Internal self-fetch (B2).
  - calc_hma consumes ≈360+18 bars for warm-up; hull_values then tail-sliced to `limit`.
  - If len(hull_values) < limit: HEAD-PADDING with hull_values[0] (np.full) → the first ≈17 position values of every window are computed from a constant seed (arbitrary 'buy'/'sell' from hull[i] vs hull[i-2] at i<2 branch).
  - Positions: hull[i] > hull[i-2] → 'buy' else 'sell' — depends on warm-up region.
IMPACT:      Head ≈17 bars of the confirmation series carry initialization artifacts; combined with positional alignment they land on the first bars of whatever df is being scored.
CONFIDENCE:  Padding path = CONFIRMED (code branch present, len(hull)≈14,383 < 14,400 for limit=14,400). Practical effect size on ROI = NOT PROVEN.
```

## F. SIGNAL ALIGNMENT

```
FILE:       backtest/backtester.py (lines ≈40–54) ; stability_windows_test.py align_signals() ; determinism_test.py freeze_inputs() ; lag_bias_test.py
FUNCTION:   align block
OBSERVATION: Everywhere the same pattern: trim tails (`signal[-len(df):]`), pad heads with 'hold', reset_index. There is NO timestamp join; `signal[i]` is paired with `df.iloc[i]` purely by position.
IMPACT:      Any boundary/timing difference between the df fetch and the signal fetches silently shifts which timestamp each signal refers to. Length equality (always 14,400 here) masks the problem completely — no error, no warning.
CONFIDENCE:  CONFIRMED
```

## G. ENTRY LOGIC

```
FILE:       backtest/hashem_backtest.py
FUNCTION:   backtest()
LINE/RANGE: ≈95–140 (entry block)
OBSERVATION:
  - BUY opens iff trigger_signals[i]=='buy' AND confirmation_signals[i]=='buy' (same bar i) while no position is open.
  - Entry price = current_bar['close'] (exact bar close of bar i — the SAME bar whose data produced the signal; zero latency, baseline has NO lag).
  - SL/TP set at entry: close ∓/± sl_pips*pip / tp_pips*pip (pip = 10^(-digits)*10 = $0.1 → SL=$10, TP=$20).
  - Lot = risk% of balance / (sl_pips × pip_value) — constant (risk_based_on='initial').
  - If a position is already open, new signals are ignored (no averaging/grid in this engine).
  - Signals may be computed from a provisional (forming) HA bar when fetched live (start_pos=0) — in coherent same-minute runs both df and signals include the same forming bar, so entry at its "close" is actually the forming price, not a settled close.
IMPACT:      Same-bar signal→entry coupling + possible forming-bar usage = optimism and timing fragility.
CONFIDENCE:  CONFIRMED
```

## H. EXIT LOGIC

```
FILE:       backtest/hashem_backtest.py
FUNCTION:   backtest()
LINE/RANGE: ≈150–200 (in-position block)
OBSERVATION (per open buy; mirrored for sell):
  - Risk-free (OFF in baseline): would move SL to entry after high ≥ entry+RF distance.
  - TP: if bar.high ≥ tp_price → exit AT tp_price (even if the bar OPENED beyond TP — no gap-fill at open price).
  - SL: else if bar.low ≤ sl_price → exit AT sl_price (no gap handling either).
  - Same-bar TP and SL both touching → TP wins (checked first) — optimistic ordering = Phase-0 Finding #1, still unfixed.
  - close_opposite_position=False in baseline → opposite-signal exit inactive.
  - Manual Close only via that flag.
  - Position still open at dataset end: silently dropped (loop ends; position never appended) — last trade's P/L excluded from statistics.
  - No spread, slippage, or commission anywhere.
IMPACT:      Optimistic exit assumptions + boundary drop of open trade.
CONFIDENCE:  CONFIRMED (all points read directly in code)
```

## I. CURRENT-CANDLE / LOOKAHEAD RISK

- `copy_rates_from_pos(..., 0, ...)` includes the forming candle → both df and signal tails can repaint after fetch. CONFIRMED (backtest_candle).
- Signal at bar i is computed from data including close[i]; entry at close[i] — intra-bar simultaneity (feasible only with instant execution at bar close). CONFIRMED.
- No other lookahead found in backtest() exit logic (exits use bar i's high/low with positions opened at i' ≤ i). CONFIRMED absence.
- The stability script used start_pos=1 for its bulk df (forming bar excluded) while its signal path used start_pos=0 — an additional df-vs-signal boundary inconsistency. CONFIRMED.

## J. ROOT-CAUSE RANKING (most→least contribution to the observed instability)

1. Self-fetching signal functions + "always latest N bars" (B1/B2) — CONFIRMED
2. Positional-only alignment, no timestamp join (F) — CONFIRMED
3. Tight absolute SL/TP ($10/$20) amplifying misalignment into trade-set flips (D-context) — CONFIRMED (parameter fact; amplification magnitude NOT PROVEN)
4. Fetch-timing drift between the three fetches (df/supertrend/trend_ali) — CONFIRMED mechanism; magnitude NOT PROVEN
5. HA recursive seed + ATR/supertrend warm-up + trend_ali head padding (C/D/E) — CONFIRMED code paths; ROI effect NOT PROVEN
6. Forming-candle inclusion (start_pos=0) — CONFIRMED; effect small but real
7. Same-bar TP-priority / no gap-slippage / end-of-data drop (H) — CONFIRMED; affects absolute numbers, not window-to-window deltas primarily

## K. CONFIRMED vs LIKELY vs POSSIBLE (the 10 boundary suspects from the mission)

| # | Suspect | Status |
|---|---|---|
| 1 | Heikin-Ashi recursive initialization | CONFIRMED (code); effect size NOT PROVEN |
| 2 | ATR warm-up | CONFIRMED (rma seed); effect NOT PROVEN |
| 3 | Supertrend initialization (prev_trend=1 etc.) | CONFIRMED (code); effect NOT PROVEN |
| 4 | Trend ALI / HMA warm-up | CONFIRMED (code) |
| 5 | required_limit | CONFIRMED (14,400 for all three; no mismatch) |
| 6 | Tail alignment | CONFIRMED (positional, everywhere) |
| 7 | Padding | CONFIRMED ('hold' heads; hull head-padding ≈17 bars) |
| 8 | Independent MT5 data fetch per signal | CONFIRMED — **primary root cause** |
| 9 | Incomplete/current candle | CONFIRMED (start_pos=0 in backtest_candle; start_pos=1 vs 0 inconsistency between stability df and signals) |
| 10 | Timestamp misalignment | CONFIRMED as *possible-by-design* (no join exists); exact per-run offsets = NOT PROVEN without instrumented logging |

## L. EVIDENCE INDEX (exact anchors)

- `backtest/hashem_backtest.py` — `backtest()` def ≈ line 21; digits fallback ≈ 31–35; entry block ≈ 95–140; exit block ≈ 150–200; stats print ≈ 304–325; report timestamp ≈ 668; report write ≈ 725–732; `backtest_candle()` ≈ 1290–1345 (copy_rates start_pos=0 ≈ 1316; HA recursion ≈ 1325–1345).
- `backtest/indicators.py` — `backtest_supertrend()` ≈ 51–135 (self-fetch ≈ 57–60; rma seed ≈ 60–66; tail slice ≈ 130–134); `backtest_trend_ali()` ≈ 566–660 (self-fetch; required_limit; head padding; tail slice).
- `backtest/backtester.py` — module-level fetch sequence + align block (lines ≈ 1–60).
- `stability_windows_test.py` — bulk fetch start_pos=1; `generate_signals()`; `align_signals()`.
- `determinism_test.py` / `lag_bias_test.py` / `lag_bias_test_window2.py` — freeze/cache reuse; window-2 fetch start_pos=14400.
- Prior artifacts all present and reviewed: `project_audit/stability_windows_cache/` (stability_results.md/.json, window_1..6_df.csv, window_N_stdout.txt), determinism cache (df/signal/confirmation CSVs, run stdouts, result.md, lag_bias_result.md, lag_bias_window2_result.md), Phase 0 six reports. **Nothing missing.**

Note on line numbers: marked "≈" — verified by function content during full file reads; the deterministic anchor lines quoted in the test scripts' docstrings (e.g., 1316, 725–732) match this reading.

## M. REQUIRED TESTS (designed only — NOT executed, per mission rules)

1. **Coherent-pairing stability scan** — requires a small change (pass `df` into the signal functions or fetch df+signals in one atomic call and derive signals from the SAME array), then re-run the 6-window baseline. Purpose: measure TRUE strategy stability. This is the single decisive test.
2. **Signal-vs-df timestamp assertion** — log `df.time.iloc[0/-1]` and the signal fetch boundaries per call; proves the misalignment empirically (no strategy change).
3. **Boundary-shift sensitivity** — same coherent month, start shifted by {0, 1, 5, 35} candles → quantify HA-seed/warm-up effect alone.
4. **TP/SL ordering test** — same trades with SL-priority variant → upper bound of Finding #1 optimism.
(Each requires code change or instrumented copy; none executed here.)

## N. PHASE 1 CONCLUSION

The observed "dramatically different ROI for the same period" is **primarily caused by a data-pairing defect**: signals always describe the newest N bars at their fetch moment, while prices come from wherever the caller got them, and the two are joined only by position. The 6-window instability table is, for windows 1–5, an artifact of this defect; window 6 differs from the coherent baseline (+142% vs +42%) due to boundary shift on top of it. **True strategy stability across months is UNKNOWN** — it has never been coherently measured. Secondary optimism sources (same-bar entry, TP-priority, no costs, end-drop) are confirmed but secondary. Per the mission rule: no cause beyond the above is declared certain; effect magnitudes explicitly marked NOT PROVEN are listed under M.

STOP — no further phase started.
