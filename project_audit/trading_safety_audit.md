# TRADING_SAFETY_AUDIT.md — Phase 0 STATIC Trading Safety Audit

Static inspection only. Nothing was executed, connected, or tested. Broker account stated as DEMO by the requester; this does not change the analysis. Secret values (Telegram token, channel/chat ids) are NOT reproduced.

## 1. Order-related and trade-management functions (all in `module/mt5.py` unless noted)

| Function | Action | Broker API | Static callers | Trigger condition | Class |
|---|---|---|---|---|---|
| `create_order(symbol, lot, order_type, sl, tp, comment)` | Place MARKET order (buy/sell) | `mt5.order_send` (TRADE_ACTION_DEAL) | bot.ipynb cell 3 (all 8 strategies); `module/stg.py :: supertrend_stg`; bot.ipynb cell 2 (same body) | Strategy signal conditions (e.g., `adx_val[-2] > 25 and super_pos_list[-2] == 'long' and signal_super == 'buy'`) | CONFIRMED |
| `pending_order(symbol, lot, order_type, price, sl, tp, comment)` | Place PENDING order (limit/stop) | `mt5.order_send` (TRADE_ACTION_PENDING) | `module/stg.py :: abcd_strategy` (BUY_LIMIT / SELL_LIMIT at D_price) | Pattern score ≥ min_score; but abcd_strategy itself has no live caller (see §4) | CONFIRMED (orphaned path) |
| `modify_stop(ticket, new_sl)` | Modify Stop Loss | `mt5.order_send` (TRADE_ACTION_SLTP) | `module/modifyPosition.py :: tp1_risk_free`, `tp1_risk_free_save_profit`, `tp1_save_profit`, `tp2_risk_free`, `tp2_risk_free_save_profit` | Price reached +1R (or +2R) vs SL → move SL to breakeven; **called from bot.ipynb cell 3 via `tp1_save_profit`** | CONFIRMED (active path) |
| `modify_tp(ticket, new_tp)` | Modify Take Profit | `mt5.order_send` (TRADE_ACTION_SLTP) | **No caller found anywhere** (CONFIRMED) | — | CONFIRMED (unused) |
| `close_order(ticket)` | Close position (full) | `mt5.order_send` (TRADE_ACTION_DEAL) | `smartTP` (modifyPosition), `close_all_positions`, `close_half_positions`, `close_all_with_comment`, `close_half_with_comment`; `smartTP` called from bot.ipynb cell 3 | `smartTP`: RSI>70 & short-candle (buy pos) or RSI<30 & long-candle (sell pos) | CONFIRMED (active via cell 3) |
| `close_half_vol_order(ticket)` | Partial close (volume/2) | `mt5.order_send` (TRADE_ACTION_DEAL) | `tp1_risk_free_save_profit`, `tp1_save_profit` (modifyPosition); `tp1_save_profit` called from bot.ipynb cell 3 | At +1R, if volume != 0.01 | CONFIRMED (active via cell 3) |
| `close_all_positions()` | Close ALL positions (all symbols) | `mt5.order_send` | **No caller found** (CONFIRMED) | — | CONFIRMED (unused); also has a latent bug: `positions is None → pass` then iterates None (INFERRED TypeError risk) |
| `close_half_positions()` | Close half of all positions | `mt5.order_send` | No caller found (CONFIRMED) | — | CONFIRMED (unused) |
| `close_all_with_comment(comment)` / `close_half_with_comment(comment)` | Close by comment | `mt5.order_send` | No caller found (CONFIRMED) | — | CONFIRMED (unused) |
| `remove_order(ticket)` | Delete pending order | `mt5.order_send` (TRADE_ACTION_REMOVE) | `module/stg.py :: manage_pending_orders` (TTL expiry / C-price invalidation) | No live caller of manage_pending_orders (CONFIRMED) | CONFIRMED (orphaned path) |
| `close_all_pending_orders()` / `close_all_pending_orders_with_type(type)` | Delete pendings (all / by type) | `mt5.order_send` | No caller found (CONFIRMED); both also have latent `None` iteration bugs (INFERRED) | — | CONFIRMED (unused) |
| `place_buy_stop(price)` / `place_sell_stop(price)` (bot.ipynb cell 4) | Place BUY/SELL STOP pending | `mt5.order_send` (TRADE_ACTION_PENDING) | `create_cycle()` ← `strategy_loop()` ← `main()` ← `if __name__ == "__main__"` / manual cell run | New grid cycle when no own positions/pendings exist | CONFIRMED |
| `close_position(position)` (bot.ipynb cell 4) | Close specific position | `mt5.order_send` (TRADE_ACTION_DEAL) | `cleanup_cycle()` | Basket target hit / one side fully triggered / incomplete cycle / startup leftover pendings | CONFIRMED |
| `delete_pending_order(order)` (bot.ipynb cell 4) | Delete pending | `mt5.order_send` (TRADE_ACTION_REMOVE) | `cleanup_cycle()`, `clean_old_orders()` | Same as above; startup cleanup of own-MAGIC pendings | CONFIRMED |
| `clean_old_orders()` (bot.ipynb cell 4) | Delete own-MAGIC pendings at startup (deliberately does NOT auto-close old positions) | `mt5.order_send` | `main()` | On start, `CLEAN_OLD_ORDERS_ON_START = True` | CONFIRMED |

Broker/MT5 API usage summary: `mt5.initialize` (module/mt5.py import-time NOT present; called in bot.ipynb cells 1/3/4 and inside `backtest_candle`/`backtest_opt`), `mt5.order_send` (multiple, above), `mt5.positions_get`, `mt5.orders_get`, `mt5.history_deals_get`, `mt5.account_info`, `mt5.symbol_info(_tick)`, `mt5.copy_rates_from_pos`, `mt5.symbol_select`, `mt5.symbols_get`, `mt5.shutdown` (cell 4 finally-block). CONFIRMED. No login/password credentials are present in code (relies on pre-connected terminal) — CONFIRMED absence; account identity UNKNOWN.

## 2. Automated execution loops
- bot.ipynb cell 3: `while True:` … 8 strategies … `time.sleep(1)` — CONFIRMED automated loop, no time/session/news gate active inside it.
- bot.ipynb cell 4: `strategy_loop()` `while True:` with 0.2s cycle checks — CONFIRMED automated loop.
- Scheduler-based execution: none found (no cron/Task Scheduler/APScheduler) — CONFIRMED absence.

## 3. Remote commands capable of reaching trading functions
- Telegram (`module/telegram.py`): message handlers relay text to a channel; **no handler invokes any trading function** (CONFIRMED). No polling loop found → receive path inert statically (UNKNOWN at runtime).
- No other remote-control surface (HTTP server, socket, webhook) found — CONFIRMED absence.

## 4. SPECIAL REQUIRED CHECK — strategy files wiring, grid/martingale logic

### 4.1 `module/stg.py`
- Wiring: **NOT statically wired to any active execution entry point** (CONFIRMED — no caller of `supertrend_stg`/`abcd_strategy`/`manage_pending_orders` exists; bot.ipynb imports but never calls them).
- Grid logic: none. Averaging down/up: none. Martingale/lot multiplication: none — the opposite: `consecutive_loss_since_last_win` HALVES risk (`risk_effective = risk * 0.5`) after losses (anti-martingale). CONFIRMED.
- Reachability of such logic from execution entry points: N/A (orphaned).

### 4.2 `module/stg peleh.py`
- **CONFIRMED MISSING FROM CURRENT PROJECT ROOT AT AUDIT TIME** (full working-tree enumeration + direct ENOENT read; no speculation about relocation). Its contents/grid-martingale characteristics: UNKNOWN.
- Consequence: `bot_state.json` contains `Gartley_Stg` and `Butterfly_Stg` keys whose code exists nowhere in the tree (CONFIRMED absence of code; INFERRED they lived in the missing file). Any safety assessment of those strategies is IMPOSSIBLE statically — classified UNKNOWN.

### 4.3 bot.ipynb cell 3 (active path)
- Grid logic: none per se (one position per strategy-comment), but EIGHT strategies run concurrently on the SAME symbol (XAUUSD) and SAME account — aggregate exposure can stack up to 8 simultaneous positions (CONFIRMED structurally; net exposure UNKNOWN w/o runtime).
- Averaging down/up: none found (CONFIRMED — no re-entry averaging loop).
- Martingale/lot multiplication: **`risk_corrector_comment(comment, risk, Start_balance, rr)`** (module/mt5.py) computes a risk% that ESCALATES to recover profit deficits: `target_total_profit = initial_risk_amount * rr * total_trades`; `adjusted_risk = (deficit / rr) / balance`; floor at base `risk`, **ceiling `max_risk = 100` (i.e., up to 100% of balance risk per trade by default)**; result feeds `lot_calculator`. This is a loss-recovery / profit-target-chasing risk-escalation scheme (functionally akin to recovery-style money management). It is CONFIRMED in the active cell-3 path (`org_risk = risk_corrector_comment(...)` before every entry).
- **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED** (cell 3: automated multi-strategy execution with escalating risk sizing).

### 4.4 bot.ipynb cell 4 (active path)
- Grid logic: **CONFIRMED** — each cycle places a symmetric ladder of 5 BUY STOPs above Ask and 5 SELL STOPs below Bid (`GRID_LEVELS=5`, `GRID_STEP_PRICE=0.20`); exits: basket net profit ≥ `BASKET_TARGET_USD=1.0`, OR one side fully triggered (5 positions) → close-all (hedge-basket semantics). This is averaging-by-structure (multiple same-direction stop entries) even though lots are fixed.
- Martingale/lot multiplication: **not found** — `LOTS = 0.01` fixed, `normalize_volume` clamps to broker min/step (CONFIRMED).
- **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED** (cell 4: automated grid/hedge stop-order ladder).

## 5. Risk controls found — and whether they are actually invoked

| Control | Location | Invoked by any execution path? |
|---|---|---|
| `lot_calculator` (risk% → lot) | module/mt5.py | **YES — CONFIRMED** (cell 3 entry path) |
| `risk_corrector_comment` / `risk_corrector` (deficit-recovery risk escalation, cap 100%) | module/mt5.py | **YES — CONFIRMED** (cell 3). NOTE: this is risk-ESCALATION, not protection. **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED** |
| `smartSL` (ATR-based SL distance, clamped 4–7 price units) | module/modifyPosition.py | **YES — CONFIRMED** (cell 3) |
| `tp1_save_profit` / `smartTP` (breakeven move, partial close, RSI exit) | module/modifyPosition.py | **YES — CONFIRMED** (cell 3) |
| `daily_draw_down_checker(Start_balance, daily_drow_down)` | module/mt5.py | **NO — CONFIRMED no caller in any entry point.** Cell 1 defines `daily_drow_down = 5` but never calls the checker; cell 3 never calls it. **Dead protective control.** |
| `total_draw_down(total_bls, full_drow_down)` | module/mt5.py | **NO — CONFIRMED no caller.** `full_drow_down = 12` defined in cell 1, unused. **Dead protective control.** |
| `consecutive_loss_since_last_win` (risk halving) | module/stg.py | **NO — orphaned** (no caller; would apply only inside abcd_strategy) |
| `total_position_comment` (max-1-position-per-strategy guard) | module/mt5.py | **YES — CONFIRMED** (cell 3) |
| News filter (`is_news`/`get_news_status_details` + outbound HTTP) | module/mt5.py | **NO — CONFIRMED no caller.** `news_filter = True` in cell 1 is never consumed. **Dead protective control (and an unbudgeted network dependency).** |
| Basket profit / full-side exit (cell 4) | bot.ipynb cell 4 | **YES — CONFIRMED** (`check_exit_conditions` → `cleanup_cycle`) |
| Session/time filters (`check_time`, `get_trading_sessions`, count_*_in_session) | module/mt5.py | **NO — CONFIRMED no caller in live paths** (used only inside history-stat helpers that themselves are uncalled or only called by risk_corrector_comment) |

### Emergency stop / kill switch
- **None found.** There is no global stop flag, no drawdown-triggered halt wired anywhere, no admin "panic" command, no watchdog. The only stops are KeyboardInterrupt handling (cell 4) and manual user intervention. CONFIRMED absence (static). **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED** (automated loops with no automated circuit-breaker; the two drawdown functions exist but are unwired).

## 6. Account connectivity
- All MT5 access uses the default already-attached terminal (`mt5.initialize()` without server/login/password args) — CONFIRMED. Which account (demo/live) the attached terminal uses is UNKNOWN / REQUIRES RUNTIME VERIFICATION and cannot be determined statically.
- Outbound HTTP: only `requests.get` to the economic-calendar endpoint in module/mt5.py (dormant — see §5). No other network calls found — CONFIRMED.

## 7. Overall static risk statement
1. Two CRITICAL automated live-trading entry points exist (bot.ipynb cells 3 and 4), one of which (cell 4) has stored output proving a real prior execution attempt (2026-08-10). CONFIRMED.
2. The active cell-3 money management escalates risk after losses up to a 100%-of-balance ceiling by default. CONFIRMED code. **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED**.
3. The cell-4 grid/hedge ladder is structurally an averaging scheme with a $1 basket target and no per-trade SL/TP on pending orders (`sl: 0.0, tp: 0.0` — protection relies entirely on basket cleanup logic). CONFIRMED. **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED**.
4. Drawdown kill-switches, news filter, session filters exist as code but are NOT invoked by any entry point. CONFIRMED. **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED** (protective-control gap).
5. No emergency stop exists. CONFIRMED. **HIGH-RISK — EXPLICIT USER REVIEW REQUIRED**.
6. `module/stg.py` is currently unwired; `module/stg peleh.py` is missing; Gartley/Butterfly strategy code is absent. Safety properties of the missing strategies: UNKNOWN.
