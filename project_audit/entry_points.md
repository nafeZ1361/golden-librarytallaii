# ENTRY_POINTS.md — Phase 0 Static Entry-Point Inventory

Static analysis only. Risk classes: any path statically reaching `mt5.order_send` is classified HIGH or CRITICAL unless static evidence proves otherwise.

## 1. `bot.ipynb` — cell 1 (broken draft/config cell)
- File: `bot.ipynb`, cell 1
- Symbols: module-level statements only (`mt5.initialize()`, kalman/supertrend/tick reads, malformed assignments `sl = smartSL ,`, `tp = smartTP , tp1_save_profit`, call `risk_corrector(risk, total_balance, rr, 100)`)
- Trigger: manual Jupyter cell execution
- Order reachability: **No** — `create_order` is never called in this cell (CONFIRMED). `risk_corrector` is pure computation; kalman/supertrend/tick are data reads.
- Purpose: appears to be an abandoned/partial setup draft (malformed code — would raise or misbehave if run; INFERRED).
- Risk: **LOW–MEDIUM** (MT5 terminal connection + market-data reads; malformed logic).

## 2. `bot.ipynb` — cell 2 (function definition)
- Symbols: re-defines `supertrend_stg` (same body as `module/stg.py :: supertrend_stg`)
- Trigger: manual cell execution (defines only; **no invocation in the cell**, CONFIRMED)
- Order reachability: YES if a user manually calls the function afterwards → `create_order` → `mt5.order_send`
- Risk: **MEDIUM** (dormant definition; executable trade path one call away)

## 3. `bot.ipynb` — cell 3 (multi-strategy live loop) — CRITICAL
- Symbols: `adx_super_stg`, `ichimoku_super_stg`, `super_sar_stg`, `super_macd_stg`, `super_keltner_stg`, `super_trendmagic_stg`, `super_vidya_stg`, `super_trendali_stg` + module-level `while True:` loop (sleep 1s), config `symbol='XAUUSD'`, `tf='1m'`, `risk = 1`, `rr = 2`, `Start_balance = balance()`
- Trigger: manual execution of the cell → **infinite automated trading loop**
- Order reachability: **CONFIRMED** — each strategy calls `create_order` (market BUY/SELL) and the position-management helpers `tp1_save_profit(position)` (→ `modify_stop`, `close_half_vol_order`) and `smartTP(tf, position)` (→ `close_order`). Guard: `total_position_comment(comment) > 0 → return` (one position per strategy comment).
- Execution-risk: **CRITICAL** (automated, unattended, 8 independent strategies on one symbol/account, risk-escalating money management — see TRADING_SAFETY_AUDIT.md).

## 4. `bot.ipynb` — cell 4 (Hedge Grid Basket EA) — CRITICAL
- Symbols: `main()`, `strategy_loop()`, `create_cycle()`, `place_buy_stop()`, `place_sell_stop()`, `close_position()`, `delete_pending_order()`, `cleanup_cycle()`, `clean_old_orders()`, `check_exit_conditions()`
- Trigger: (a) manual cell execution then `main()`; (b) **`if __name__ == "__main__": main()`** present (CONFIRMED) — e.g., `jupyter nbconvert --execute` or notebook-as-script export would run it
- Order reachability: **CONFIRMED** — direct `mt5.order_send` calls for pending stops, position close, pending delete; MAGIC=26080901 scoping.
- Contains stored execution OUTPUT (2026-08-10 01:02, "BUY STOP failed | retcode=10018 | Market closed", cleanup cycles, "Bot stopped by user.") — CONFIRMED evidence of a prior real execution attempt.
- Execution-risk: **CRITICAL** (automated grid/hedge order placement loop).

## 5. `backtest/backtester.py` — script-style module
- Symbols: module-level `mt5.initialize()`, data load, single `backtest(...)` call (supertrend + trend_ali)
- Trigger: `python backtest/backtester.py` OR import (module-level code runs on import — CONFIRMED no `__main__` guard)
- Order reachability: **No** — `backtest()` is simulation-only; no `order_send` in `backtest/` package (CONFIRMED). However it connects to the MT5 terminal for data.
- Risk: **MEDIUM** (terminal connection, data reads; writes HTML report into `backtest/`).

## 6. `backtest/optimizer.py` — `__main__` block
- Symbols: `optimizer(...)` (grid search, ThreadPoolExecutor), `backtest_opt(...)`, `get_indicator_signals(...)`
- Trigger: direct run (`if __name__ == "__main__"` CONFIRMED) or import of functions
- Order reachability: **No** (simulation only). Calls `mt5.initialize()`/`symbol_info` for pip math (CONFIRMED).
- Risk: **MEDIUM** (heavy CPU, terminal connection; writes `optimizer_results/*.json`).

## 7. `module/Optimizer walkforward.py` — `__main__` block (BROKEN AS LOCATED)
- Symbols: `optimizer_walkforward(...)`
- Trigger: direct run or import
- Order reachability: **No** (simulation only)
- **Blocking note (CONFIRMED):** relative imports `from .hashem_backtest import *`, `from .indicators import *`, `from .optimizer import ...` cannot resolve inside `module/` (no such submodules there). As located, the entry point cannot start (INFERRED: immediate ImportError). Written for `backtest/` placement.
- Risk: **MEDIUM** intended / effectively non-functional at current path.

## 8. `module/telegram.py` — Telegram bot handlers
- Symbols: `bot = telebot.TeleBot(TOKEN)` at import; `echo_all` handler registered TWICE; `send_message_to_channel`, `send_image_to_channel`, `send_telegram_signal_3tp`, `send_telegram_signal_1tp`, plotting helpers
- Trigger: **No polling loop found** (`bot.polling()`/`infinity_polling()`/`bot.polling(none_stop=True)` absent — CONFIRMED). Handlers fire only if some external runner starts polling — none found (UNKNOWN if one exists outside the tree).
- Order reachability: **No** trading functions reachable from this file (CONFIRMED — it only sends messages/images and reads candles).
- Notes: `echo_all` relays ANY received message text to the hardcoded channel (message-forwarding surface); TOKEN hardcoded (sensitive — value not reproduced).
- Risk: **LOW–MEDIUM** (network + information relay; no trade reachability).

## 9. Scheduled tasks / cron / services / GUI / MT5 EA
- None found. No Windows Task Scheduler files, cron configs, APScheduler/celery imports, service wrappers, GUI frameworks, `.mq5/.ex5/.mq4/.ex4` EA files, or `.bat/.cmd` launchers exist in the tree (CONFIRMED by full file enumeration). The only automation loops are the notebook `while True` cells (#3, #4).

## 10. Strategy-file wiring (REQUIRED SPECIAL CHECK)

### `module/stg.py`
- `supertrend_stg`: defined in stg.py AND duplicated in bot.ipynb cell 2; **NOT called** by any stored entry point (CONFIRMED). Reachable only by a manual call in a notebook session (INFERRED possible, not stored).
- `abcd_strategy`, `manage_pending_orders`, `lot_calculator_universal`, `consecutive_loss_since_last_win`: **no caller anywhere in the tree** (CONFIRMED — bot.ipynb imports `module.stg *` but calls none of these). The state-driven runner that would use them (keys `ABCD_Stg` in `bot_state.json`) is not present. → stg.py is currently ORPHANED from execution.
- Wiring classification: **NOT WIRED to any stored entry point — CONFIRMED (static)**.

### `module/stg peleh.py`
- **CONFIRMED MISSING FROM CURRENT PROJECT ROOT AT AUDIT TIME** (full working-tree enumeration + ENOENT direct read). Wiring: UNDETERMINABLE — file absent. `bot_state.json` keys `Gartley_Stg`/`Butterfly_Stg` have no corresponding code anywhere (CONFIRMED absence; INFERRED that the missing file contained them).

### bot.ipynb cell-3 strategies + cell-4 grid EA
- These are the ONLY strategy code statically wired to live execution entry points (CONFIRMED). Both are self-contained in the notebook, not in `module/stg.py`.

## 11. Risk classification summary
| Entry point | Trading reach | Class |
|---|---|---|
| bot.ipynb cell 3 | market orders + SL modify + partial/full close | **CRITICAL** |
| bot.ipynb cell 4 | pending stop orders, close positions, delete pendings | **CRITICAL** |
| bot.ipynb cell 2 | reachable only via manual call | MEDIUM |
| bot.ipynb cell 1 | reads only (malformed) | LOW–MEDIUM |
| backtest/backtester.py | none (terminal/data only) | MEDIUM |
| backtest/optimizer.py __main__ | none (terminal/data only) | MEDIUM |
| module/Optimizer walkforward.py __main__ | none; broken imports at location | MEDIUM |
| module/telegram.py handlers | none (messaging only; no polling) | LOW–MEDIUM |
