# CODEBASE_MAP.md — Phase 0 Static Codebase Map

Project root: `C:\Users\icFixer.ir\Desktop\کتابخونه بخش طلایی`
Audit mode: READ-ONLY, static plain-text inspection only. No code was executed, imported, or tested.
Evidence rule: every statement classified as CONFIRMED / INFERRED / UNKNOWN.

## 1. Directory / file structure (CONFIRMED via non-executing recursive file enumeration of the working tree, incl. hidden files; `.git` internal object store excluded — it cannot contain working-tree source files)

```
C:\Users\icFixer.ir\Desktop\کتابخونه بخش طلایی\
├── .agents\                      (agent/skill infrastructure — NOT project code)
├── .git\                         (version control metadata)
├── .openclaw\                    (agent workspace state — NOT project code)
├── .openclaw-attachments\        (chat attachments — NOT project code)
├── backtest\
│   ├── backtester.py             (2,094 B)
│   ├── hashem_backtest.py        (62,057 B)
│   ├── indicators.py             (37,773 B)
│   └── optimizer.py              (25,536 B)
├── module\
│   ├── __pycache__\              (5 × .pyc, cpython-312 compiled artifacts)
│   ├── indicators.py             (93,813 B)
│   ├── modifyPosition.py         (4,164 B)
│   ├── mt5.py                    (39,007 B)
│   ├── Optimizer walkforward.py  (17,544 B)
│   ├── state_io.py               (1,133 B)
│   ├── stg.py                    (29,385 B)
│   └── telegram.py               (3,766 B)
├── projects\                     (EMPTY — CONFIRMED)
├── .gitignore                    (594 B)
├── AGENTS.md / AGENTS.old.md (0 B) / SOUL.md / USER.md / IDENTITY.md / TOOLS.md / HEARTBEAT.md
├── bot.ipynb                     (56,869 B — main notebook, 4 cells)
├── bot_state.json                (68 B)
├── DESIGN.old.md (0 B)
├── README.md                     (224 B)
├── REFACTORING_SUMMARY.md        (3,344 B)
├── skills-lock.json              (495 B — agent skill lockfile, NOT project code)
├── smart money indicator.txt     (23,341 B — TradingView Pine Script v5 source, reference only)
├── state_io.py                   (2,562 B — root-level duplicate)
└── TelegramSignal.png            (40,244 B — output artifact image of telegram.py plotting)
```

## 2. Component groups and per-file purpose

### Live trading / execution
| File | Purpose | Classification |
|---|---|---|
| `bot.ipynb` cell 3 | Live multi-strategy loop (`while True`, 8 strategies, XAUUSD 1m) calling `create_order`, `tp1_save_profit`, `smartTP`, `risk_corrector_comment`, `lot_calculator` | CONFIRMED live execution entry code |
| `bot.ipynb` cell 4 | "XAUUSD Hedge Grid Basket EA": self-contained grid EA (`main()`, `strategy_loop()`, `place_buy_stop`, `place_sell_stop`, `close_position`, `delete_pending_order`, `cleanup_cycle`), MAGIC=26080901; contains stored execution OUTPUT dated 2026-08-10 (order attempts, retcode=10018) | CONFIRMED live execution entry code; CONFIRMED prior execution attempt evidence |
| `module/mt5.py` | MT5 wrapper: order send/close/modify/remove functions, candle/Heikin-Ashi data functions, account/history stats, news filter (outbound HTTP), risk/lot calculators | CONFIRMED broker API layer |
| `module/modifyPosition.py` | Trade-management helpers: SL→breakeven ("risk free"), partial close, RSI/candle-based `smartTP`, ATR-based `smartSL` | CONFIRMED position-management layer |
| `module/telegram.py` | Telegram bot (telebot): signal chart images to hardcoded channel; `echo_all` message relay (defined twice); NO polling loop present | CONFIRMED notifications; trading commands NOT found |

### Strategies
| File | Purpose | Classification |
|---|---|---|
| `module/stg.py` | `supertrend_stg` (market orders), `abcd_strategy` (ABCD pattern, pending limit orders, scoring, anti-repaint swing filter), `manage_pending_orders` (TTL/invalidation cancel), `lot_calculator_universal`, `consecutive_loss_since_last_win` (risk halving after losses) | CONFIRMED strategy code; call-wiring see ENTRY_POINTS.md |
| `bot.ipynb` cell 3 strategy functions | `adx_super_stg`, `ichimoku_super_stg`, `super_sar_stg`, `super_macd_stg`, `super_keltner_stg`, `super_trendmagic_stg`, `super_vidya_stg`, `super_trendali_stg` (all market orders via `create_order`) | CONFIRMED |
| `bot.ipynb` cell 4 | Grid/hedge basket strategy (5 BUY STOP + 5 SELL STOP per cycle, basket $ target, close-all-on-full-side) | CONFIRMED |
| `module/stg peleh.py` | **DOES NOT EXIST** — CONFIRMED MISSING FROM CURRENT PROJECT ROOT AT AUDIT TIME (see BLOCKING_ISSUES.md §1) | CONFIRMED MISSING |

### Indicators
| File | Purpose | Classification |
|---|---|---|
| `module/indicators.py` (2,600 lines) | Large live-indicator library: supertrend, kalman_trend_levels, trend_ali (Hull), volumatic_vidya, half_trend, trend_magic, ichimoku, ssl_hybrid, ut_bot, nadaraya_watson, zigzag, smart-money ports (`detect_bos`, `detect_choch`, `detect_fvg`, `detect_ob`, `detect_idm`), ATR/RSI/ADX/MACD/StochRSi/sar, session/volatility helpers | CONFIRMED |
| `backtest/indicators.py` | Backtest variants of the same indicators (signal/trend lists aligned to df length) | CONFIRMED |
| `smart money indicator.txt` | Original TradingView Pine Script v5 "hashem SMC" (BOS/CHoCH/IDM/OB/SCOB) — reference source for the Python smart-money ports; not executable by this project | CONFIRMED reference/doc |

### Backtesting / optimization
| File | Purpose | Classification |
|---|---|---|
| `backtest/hashem_backtest.py` | Core backtest engine: `backtest()` (balance/SL/TP/risk-free simulation + Plotly HTML report), `run_backtest()`, `optimize_strategy()`, `analyze_results()`, `backtest_candle()` (MT5 data), `extract_number()` | CONFIRMED backtest-only (no order_send anywhere in file) |
| `backtest/backtester.py` | Top-level script wiring supertrend+trend_ali into `backtest()`; module-level side effects: `mt5.initialize()` and immediate backtest run on import | CONFIRMED |
| `backtest/optimizer.py` | Parameter grid-search optimizer (ThreadPoolExecutor), writes `optimizer_results/*.json`; `__main__` block | CONFIRMED |
| `module/Optimizer walkforward.py` | Walk-forward optimizer variant (IS/OOS split, overfit warnings). **MISPLACED**: uses `from .hashem_backtest import *` etc., which do not exist inside `module/` — as located, imports are broken (CONFIRMED statically). Written for `backtest/` placement | CONFIRMED misplaced/broken at current path |

### State management
| File | Purpose | Classification |
|---|---|---|
| `module/state_io.py` | JSON state save/load with NumPy encoder (`bot_state.json`) | CONFIRMED |
| `state_io.py` (root) | Near-duplicate of the above with extra docstrings | CONFIRMED duplicate |
| `bot_state.json` | Current state: `{"ABCD_Stg": {}, "Gartley_Stg": {}, "Butterfly_Stg": {}}` | CONFIRMED content. Note: `Gartley_Stg` / `Butterfly_Stg` strategy code exists NOWHERE in the tree (INFERRED: belonged to the missing strategy file) |

### Data handling
`module/mt5.py` (`candle`, `heikin_ashi`: MT5 M1 → resample to target TF), `backtest/hashem_backtest.py` (`backtest_candle`: direct TF copy). See DATA_FLOW.md.

### Risk management (see TRADING_SAFETY_AUDIT.md for wiring status)
`lot_calculator`, `lot_calculator_universal`, `risk_corrector`, `risk_corrector_comment`, `smartSL`, `daily_draw_down_checker`, `total_draw_down`, `consecutive_loss_since_last_win`.

### Configuration
- No configuration file system found. Constants are hardcoded inside `bot.ipynb` cells (symbol/timeframe/risk/rr/grid params) and as function defaults. CONFIRMED.
- No `requirements.txt`, `pyproject.toml`, `setup.py`, `.env`, or Dockerfile present. CONFIRMED (absent from full enumeration).
- `.gitignore` — standard ignores (`.env`, `__pycache__`, etc.). CONFIRMED.
- `README.md` — Persian install note ("install the libraries in the notebooks except the Telegram part"). CONFIRMED.

### Utilities / other
- `module/state_io.py` (above), `get_broker_offset`, `get_trading_sessions`, `check_time`, `count_*` history stats (`module/mt5.py`) — CONFIRMED.
- `TelegramSignal.png` — output artifact (INFERRED: produced by `module/telegram.py` `mpf.savefig` at some prior run).
- `module/__pycache__/*.pyc` for indicators, modifyPosition, mt5, state_io, stg (cpython-312) — compiled-only artifacts; NOT decompiled per audit rules. INFERRED: those modules were imported by a Python 3.12 interpreter at some point. No `.pyc` for `telegram.py` (UNKNOWN reason).
- `AGENTS.old.md`, `DESIGN.old.md` — 0-byte empty files. CONFIRMED.
- `projects/` — empty directory. CONFIRMED.
- `skills-lock.json`, `.agents/`, `.openclaw/`, `.openclaw-attachments/`, agent workspace `*.md` — assistant/workspace infrastructure, NOT part of the trading system.

## 3. Missing-file note (required)

- `module/stg peleh.py` — **CONFIRMED MISSING FROM CURRENT PROJECT ROOT AT AUDIT TIME**. Verification: (1) full recursive working-tree file enumeration (metadata-only, no execution) lists no file named `stg peleh` anywhere; (2) direct read attempt of `module\stg peleh.py` returned ENOENT. No substitute content invented.
