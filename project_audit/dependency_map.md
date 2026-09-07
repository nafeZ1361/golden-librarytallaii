# DEPENDENCY_MAP.md — Phase 0 Static Dependency Map

Static import/reference analysis only. No package was installed, imported, executed, or tested.

## 1. External (third-party) dependencies

| Package | Import sites | Used for | Version pin |
|---|---|---|---|
| `MetaTrader5` | `module/mt5.py`, `module/indicators.py`, `module/stg.py`, `bot.ipynb` (cells 3, 4), `backtest/hashem_backtest.py`, `backtest/backtester.py`, `backtest/optimizer.py` (via `backtest_opt`), implied by `backtest/indicators.py` (through `backtest_candle`) | Terminal connection, market data, order execution | UNKNOWN (no requirements file exists) |
| `pandas` | `module/mt5.py`, `module/indicators.py`, `module/stg.py`, `backtest/hashem_backtest.py`, `backtest/indicators.py`, `backtest/optimizer.py` | DataFrames, resampling | UNKNOWN |
| `numpy` | `module/mt5.py`, `module/indicators.py`, `module/state_io.py`, root `state_io.py`, `module/stg.py`, `backtest/indicators.py`, `backtest/hashem_backtest.py` | Numeric arrays | UNKNOWN |
| `ta` | `module/mt5.py`, `module/indicators.py`, `backtest/indicators.py` | RSI/SMA/WMA/MFI indicators | UNKNOWN |
| `pandas_ta` | `module/indicators.py`, `backtest/indicators.py` | MACD, ATR, StochRSI | UNKNOWN |
| `pytz` | `module/mt5.py` | Session timezones, broker offset | UNKNOWN |
| `requests` | `module/mt5.py` | **Outbound HTTP** news calendar fetch (`https://nfs.faireconomy.media/ff_calendar_thisweek.json`) | UNKNOWN |
| `telebot` (pyTelegramBotAPI) | `module/telegram.py` | Telegram bot API (send messages/photos, message handlers) | UNKNOWN |
| `mplfinance` | `module/telegram.py` | Candlestick chart image generation | UNKNOWN |
| `plotly` | `backtest/hashem_backtest.py` | Backtest HTML reports | UNKNOWN |
| `yfinance` | `backtest/hashem_backtest.py` (top-level import) | **No usage found anywhere in the file body** — suspicious/unused import | UNKNOWN |
| `tqdm` | `backtest/optimizer.py` (hard import — will raise ImportError if missing); `module/Optimizer walkforward.py` (optional, try/except fallback) | Progress bars | UNKNOWN |

Standard library only: `datetime`, `time`, `json`, `os`, `re`, `math`, `statistics`, `itertools`, `concurrent.futures`, `multiprocessing`, `warnings`, `sys`, `io`, `dataclasses`, `typing`.

**No `requirements.txt` / lock file exists** → all versions are UNKNOWN; runtime compatibility cannot be verified statically.

## 2. Internal module-to-module dependencies

```
bot.ipynb ──> module.mt5 (*)          bot.ipynb ──> module.indicators (*)
         ──> module.modifyPosition (*)             ──> module.stg (*)
         ──> module.state_io (save_state, load_state)

module.indicators ──> module.mt5 (*)                 [relative: from .mt5 import *]
module.stg        ──> module.mt5 (*), module.indicators (*)   [BOTH relative (top) and absolute (mid-file) — duplicate import styles]
module.modifyPosition ──> module.mt5 (*), module.indicators (*)  [absolute]
module.telegram   ──> module.mt5 (*), module.indicators (*)      [relative]
module.state_io   ──> (no project deps)

backtest.backtester ──> backtest.hashem_backtest (*), backtest.indicators (*)
backtest.optimizer  ──> backtest.hashem_backtest (*), backtest.indicators (*)
backtest.indicators ──> backtest.hashem_backtest (backtest_candle only)
backtest.hashem_backtest ──> (no project imports)

module/Optimizer walkforward.py ──> backtest.hashem_backtest (*), backtest.indicators (*),
                                    backtest.optimizer (DEFAULT_PARAMS, get_indicator_signals, backtest_opt)
                                    [via RELATIVE imports `.hashem_backtest` etc. — BROKEN at current location,
                                     CONFIRMED: no module/hashem_backtest.py, module/optimizer.py, or
                                     matching module/indicators-for-backtest exist; file was written for backtest/]
```

### Star-import side effects (CONFIRMED, fragile)
- `module/mt5.py` defines no `__all__`; `from .mt5 import *` therefore re-exports **everything** in its namespace, including `pd`, `np`, `mt5`, `requests`, `pytz`, and all order functions (`create_order`, `close_order`, `modify_stop`, …).
- `module/telegram.py` uses `pd.to_datetime` **without importing pandas directly** — it works only through the `from .mt5 import *` side effect. CONFIRMED fragile dependency.
- `bot.ipynb` cell 3 depends on `buy`/`sell` constants and `create_order`, `lot_calculator`, `risk_corrector_comment`, `total_position_comment` — all via star-imports from `module.mt5`. CONFIRMED.

### Circular dependencies
- No import cycle found statically in `module/` (mt5 ← indicators ← stg/modifyPosition/telegram; mt5 imports no project module). CONFIRMED.
- No import cycle found statically in `backtest/` (hashem_backtest ← indicators ← optimizer/backtester). CONFIRMED.

### Duplicate components (CONFIRMED)
- `state_io.py` (root) duplicates `module/state_io.py` (near-identical logic, different formatting). Only `module.state_io` is imported by `bot.ipynb`. Root copy is orphaned.
- `supertrend_stg` is defined BOTH in `module/stg.py` and re-defined in `bot.ipynb` cell 2. CONFIRMED duplicate definition.
- Live vs backtest indicator libraries are parallel implementations (`module/indicators.py` vs `backtest/indicators.py`) — logic is similar but not identical (e.g., padding/alignment behavior differs). CONFIRMED.

## 3. Unclear / missing / suspicious dependencies

1. `module/Optimizer walkforward.py` relative imports are **broken at its current location** (CONFIRMED missing target modules inside `module/`). Runtime behavior: would raise `ModuleNotFoundError` (INFERRED with high confidence; not executed per rules).
2. `yfinance` imported but unused in `backtest/hashem_backtest.py` (CONFIRMED no reference in file body).
3. `tqdm` hard dependency in `backtest/optimizer.py` without fallback (CONFIRMED); optional in walkforward variant (CONFIRMED).
4. No `__init__.py` in `module/` or `backtest/` (CONFIRMED absent). They rely on Python 3 namespace packages; the refactoring summary even lists creating `__init__.py` as an unfinished TODO. This makes package resolution dependent on the launch directory (UNKNOWN at runtime without execution).
5. `module/telegram.py` registers `@bot.message_handler` twice with the same function name `echo_all` (second registration shadows/stacks — telebot registers both decorators; behavior would need runtime verification) and never calls `bot.polling()`/`infinity_polling()` (CONFIRMED absent) → handlers are inert unless invoked externally (UNKNOWN whether any runner does).
6. `requests` network dependency is dormant in current entry points (no caller of `is_news` found — see ENTRY_POINTS/TRADING_SAFETY_AUDIT) but the code path exists and performs outbound HTTP (CONFIRMED code, INFERRED dormant).
7. Secrets/config: Telegram bot TOKEN and CHANNEL_ID are hardcoded in `module/telegram.py` (values NOT reproduced here — sensitive data may be present). No `.env` mechanism exists despite the refactoring summary recommending one. CONFIRMED hardcoded credential presence.
