# DATA_FLOW.md — Phase 0 Static Data-Flow Trace

Static analysis only. This report flags data-availability locations ONLY; final lookahead/repainting severity judgments are explicitly deferred to Phase 1 per the audit scope.

## 1. Market data ingestion

### Live path — CONFIRMED STATIC PATH
- `module/mt5.py :: candle(symbol, tf, limit)` → `mt5.copy_rates_from_pos(symbol, TIMEFRAME_M1, 0, tf_minutes*limit*2)` → pandas DataFrame → `aligned_time = floor(M1 timestamp to TF bucket)` → groupby/agg (open=first, high=max, low=min, close=last, volume=sum) → last `limit` buckets sorted ascending. Returns `result.iloc` (an indexer object whose `.obj` attribute exposes the DataFrame — undocumented API convention used throughout the codebase, CONFIRMED).
- `module/mt5.py :: heikin_ashi(...)` → same pipeline + Heikin-Ashi transformation (recursive HA open/close calculation).
- Source: local MetaTrader 5 terminal (no credentials in code; relies on an already-logged-in terminal). CONFIRMED code; account/terminal state UNKNOWN.

### Backtest path — CONFIRMED STATIC PATH
- `backtest/hashem_backtest.py :: backtest_candle(symbol, tf, limit, heikin_ashi=False)` → `mt5.initialize()` (called on every invocation) → `mt5.copy_rates_from_pos(symbol, <direct TF map>, 0, limit)` → DataFrame; optional HA transform. NOTE: unlike the live path, this pulls the target TF directly (M3 exists as a native MT5 timeframe) rather than resampling M1.
- Both paths return the most recent bars **including bar at position 0 (the current, possibly still-forming bar)** — CONFIRMED by `copy_rates_from_pos(..., 0, ...)` start position.

## 2. Transformation / preprocessing — CONFIRMED STATIC PATH
- Resampling (live), HA smoothing, alignment/padding of signal lists to df length (backtest variants pad with 'sell'/'hold' head-padding — CONFIRMED in `backtest_kalman_trend_levels`, `backtest_half_trend`, `backtest_trend_ali`, `backtest_deviation_trend_signals`, `backtest_volumatic_vidya`).

## 3. Indicator calculation path — CONFIRMED STATIC PATH
- Live: `module/indicators.py` (supertrend, kalman_trend_levels, trend_ali, macd, adx, ichimoku, keltner_channels, trend_magic, volumatic_vidya, sar/sar_signal, zigzag, detect_ob/detect_bos/detect_choch/detect_idm/detect_fvg, Atr, rsi, ut_bot, ssl_hybrid, half_trend, nadaraya_watson, winRate, …). All read via `candle()/heikin_ashi()`.
- Backtest: `backtest/indicators.py` parallel implementations reading via `backtest_candle()`.

## 4. Strategy signal path — CONFIRMED STATIC PATH
- Live loop (bot.ipynb cell 3): indicator output → `Trend_change_signal(position_list)` (compares `[-2]` vs `[-3]`) or direct `[-2]` checks → strategy function → `sl = price.ask - smartSL(...)` / `tp = price.ask + (ask-sl)*rr` → `lot_calculator(...)` sized from `risk_corrector_comment(...)` → `create_order(...)`.
- ABCD strategy (module/stg.py): `candle(500)` → `zigzag(depth=12)` → `_safe_swings` anti-repaint filter (drops swings within `confirm_bars` of the last bar) → pattern pick → scoring (HTF trend_ali + detect_ob zones + RSI/MACD momentum) → `pending_order(BUY_LIMIT/SELL_LIMIT at D_price)`; `manage_pending_orders` cancels via `remove_order` on TTL/invalidation. — CONFIRMED code; **no live caller exists in the current tree** (see ENTRY_POINTS.md §5).

## 5. Possible order/execution path — CONFIRMED STATIC PATH (code), execution status UNKNOWN
- Live market orders: strategy → `create_order` (TRADE_ACTION_DEAL) → `mt5.order_send`.
- Grid EA (bot.ipynb cell 4): `strategy_loop` → `create_cycle` → `place_buy_stop`/`place_sell_stop` (TRADE_ACTION_PENDING) → `mt5.order_send`; exits via `close_position` (TRADE_ACTION_DEAL) / `delete_pending_order` (TRADE_ACTION_REMOVE) / `cleanup_cycle`.
- Trade management: `tp1_save_profit`/`smartTP` → `modify_stop` (TRADE_ACTION_SLTP) / `close_half_vol_order` / `close_order`.
- Whether any of this runs at audit time (terminal connected? schedule?) is UNKNOWN / REQUIRES RUNTIME VERIFICATION. Stored notebook OUTPUT in cell 4 (timestamps 2026-08-10, retcode=10018 "Market closed", MAGIC=26080901) is CONFIRMED evidence that this cell was executed against a real MT5 terminal in the past; it is NOT evidence of current activity.

## 6. Output / result / state storage — CONFIRMED STATIC PATH
- `bot_state.json` ← `save_state/load_state` (module/state_io.py). **No current entry point calls save_state/load_state** (bot.ipynb imports them but never calls them — CONFIRMED). State file content shows empty dicts for ABCD_Stg/Gartley_Stg/Butterfly_Stg (likely written by a now-absent runner — INFERRED).
- `TelegramSignal.png` ← telegram.py plotting.
- `backtest/backtest_report_*.html` ← hashem_backtest.backtest().
- `optimizer_results/best_params_*.json` ← backtest/optimizer.py; `optimizer_results/wfo_*.json` ← walkforward variant.
- `optimize/optimize_report_*.html` ← hashem_backtest.analyze_results().
- None of these output files (other than bot_state.json and TelegramSignal.png) were present in the enumerated tree → those pipelines have not produced artifacts in this folder (INFERRED; outputs may have been produced from a different working directory — UNKNOWN).

## 7. External network data — CONFIRMED STATIC PATH (dormant)
- `module/mt5.py :: fetch_economic_news` → `requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json")` (ForexFactory weekly calendar), cached 30 min in a module-global `cache` dict. `is_news`/`get_news_status_details` consume it.
- **No caller of `is_news`/`get_news_status_details` exists in any entry point** (CONFIRMED) → dormant in the live loop; `news_filter = True` is assigned in bot.ipynb cell 1 but never consumed (CONFIRMED).
- `yfinance` import in hashem_backtest.py: no usage found (CONFIRMED).

## 8. Telegram data path — CONFIRMED STATIC PATH (receive side inert)
- Outbound: `send_message_to_channel` / `send_image_to_channel` → telebot → hardcoded channel id. Signal images built from `candle(symbol, tf, limit=60)`.
- Inbound: `@bot.message_handler` `echo_all` (defined twice) relays ANY incoming private message text to the channel. No `bot.polling()` call exists statically → receive path appears inert (UNKNOWN at runtime).

## 9. Data-availability flags (LOCATIONS ONLY — no severity verdict, Phase 1 scope)

Flagged as "data appears potentially usable before it would realistically be available" candidates:

1. `candle()`/`heikin_ashi()` include position-0 forming M1 data and the forming TF bucket (floor-grouping). All `[-1]`/`[-2]` index conventions downstream depend on whether the last bucket is complete. — CONFIRMED code pattern; effect UNKNOWN w/o runtime.
2. `sar_signal()` compares `candles[-1]['close']` (potentially forming bar) against SAR values — CONFIRMED usage of last-bar close.
3. `winRate()`, `smartTrend()`, `ravand()` use `[-1]` indicator values and `check_candle(..., -1)` — CONFIRMED last-bar usage.
4. `supertrend()`/`Trend_change_signal()` signal on `[-2]` vs `[-3]` — index alignment vs bucket completeness is the Phase 1 question. — CONFIRMED code, UNKNOWN causality.
5. `trend_alert()`/`backtest_trend_alert()` compute bar indices from wall-clock "forex open" — time-dependent indexing. — CONFIRMED.
6. Backtest engines enter at `current_bar['close']` and check SL/TP against the same and later bars' high/low (intrabar TP-vs-SL ordering ambiguity). — CONFIRMED code pattern; no verdict.
7. `nadaraya_watson()` envelope recomputes over a trailing window (inherently redraw-prone family of indicators). — CONFIRMED code; no verdict.
8. ZigZag (`module/indicators.py :: zigzag`) is repaint-prone by nature; `abcd_strategy` mitigates with `_safe_swings(confirm_bars)` — mitigation is CONFIRMED code; completeness UNKNOWN w/o runtime.
9. Live `candle()` resamples from M1 while backtest pulls native TF bars — the live and backtest data bases are NOT identical (CONFIRMED), so backtest results may not correspond bar-for-bar to live data (no verdict).
10. `daily_draw_down_checker`/`total_draw_down` rely on `pnl_today()`/equity reads — correct-by-construction data source, but see TRADING_SAFETY_AUDIT: they are not invoked by any entry point (CONFIRMED).
