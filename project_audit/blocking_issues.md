# BLOCKING_ISSUES.md — Phase 0 Static Inspection Blockers & Limitations

## 1. `module/stg peleh.py` — MISSING (REQUIRED DOCUMENTATION)
- **Classification: CONFIRMED MISSING FROM CURRENT PROJECT ROOT AT AUDIT TIME.**
- Verification performed (non-executing): (a) full recursive working-tree file enumeration (metadata-only listing, hidden files included, `.git` internal object store excluded — it cannot contain working-tree source files); (b) direct plain read attempt of `module\stg peleh.py` → ENOENT ("no such file or directory").
- The audit brief stated the project "contains at least two strategy files: module/stg.py and module/stg peleh.py". Only `module/stg.py` exists. No substitute content was invented and no relocation was speculated.
- Impact: the wiring/grid-martingale characteristics of this file are UNKNOWN. `bot_state.json` references `Gartley_Stg` and `Butterfly_Stg`, whose code exists nowhere in the tree — INFERRED to have lived in the missing file. Documented in CODEBASE_MAP.md, ENTRY_POINTS.md §10, TRADING_SAFETY_AUDIT.md §4.2.

## 2. Misplaced module with broken relative imports
- `module/Optimizer walkforward.py` uses `from .hashem_backtest import *`, `from .indicators import *`, `from .optimizer import ...` — none of these exist inside `module/` (they exist in `backtest/`). As located, the file cannot be imported or run (INFERRED ImportError; not executed per rules). CONFIRMED statically that the import targets are absent from its package.

## 3. Large-file inspection status
- `backtest/hashem_backtest.py` (62,057 B): read in a single pass that returned the complete file content (imports → backtest → optimize_strategy → run_backtest → analyze_results → generate_optimization_report → backtest_candle → extract_number, continuous, no truncation marker); a verification read at offset 1500 returned no further content (consistent with EOF before that line). Treated as FULLY INSPECTED. Conclusions about it: CONFIRMED at source level; runtime behavior remains unverified.
- `module/indicators.py` (93,813 B, 2,600 lines): read in 3 chunks (1–1200, 1201–2563, 2564–2600) — FULLY INSPECTED.
- `bot.ipynb` (56,869 B): read fully as JSON text — all 4 code cells inspected, including stored outputs.
- No other file exceeded single-pass limits. No file was silently omitted.
- Tool quirk note: a verification read of `hashem_backtest.py` at offset 1500 returned an anomalous "(see attached image)" placeholder instead of explicit EOF — judged to be a reader artifact beyond EOF, not file content (the full content was already captured in the main pass).

## 4. Compiled-only artifacts
- `module/__pycache__/*.pyc` (5 files, cpython-312): binary compiled bytecode; NOT decompiled or inspected (out of scope for plain-text static audit). Source-of-truth `.py` files were inspected instead; whether bytecode matches current sources is UNKNOWN.
- `TelegramSignal.png`: binary image; not analyzed (content not relevant to code audit).

## 5. Things statically underivable (execution required) — REQUIRES RUNTIME VERIFICATION
- Whether an MT5 terminal is attached, and whether the attached account is DEMO or LIVE.
- Whether any of the notebook loops is currently running anywhere (no scheduler exists; notebook cells only run when manually executed).
- Actual installed dependency versions (no requirements file exists at all).
- Telegram handler behavior (no polling loop found — inbound path appears inert, but an external runner cannot be excluded).
- Whether `candle()` bucket alignment yields complete-bar semantics at `[-2]` in all market conditions (Phase 1 subject).
- Python package resolution without `__init__.py` files given the actual launch working directory.

## 6. Configuration-dependent / ambiguous paths
- No config file system: all live parameters are hardcoded in notebook cells (symbol, timeframe, risk, rr, grid constants, MAGIC). Risk class of the whole system depends on these hand-edited values (CONFIRMED hardcoded).
- Duplicate `state_io.py` (root vs module/) — which copy a runner uses depends on import style/location; `bot.ipynb` uses `module.state_io` (CONFIRMED). Root copy orphaned.
- Duplicate `supertrend_stg` definition (module/stg.py vs bot.ipynb cell 2) — divergence risk if one is edited.
- `module/telegram.py` registers the `echo_all` handler twice and has no polling call — behavior only determinable at runtime.

## 7. Inspections deliberately stopped (would have required execution)
- Running any backtest/optimizer/notebook cell to "see what happens" — NOT done (prohibited).
- Importing any module to resolve star-import contents — NOT done (prohibited); star-import analysis was done by reading source only.
- Decompiling `.pyc` files — NOT done.
- Any network/terminal probe (MT5 attach, Telegram token validation, news endpoint check) — NOT done (prohibited).

## 8. Other noteworthy gaps (not blocking, but material)
- No `requirements.txt`/lockfile, no `__init__.py` files, no tests, no CI, no `.env` mechanism; Telegram TOKEN + CHANNEL_ID hardcoded (sensitive data may be present — value not reproduced; see module/telegram.py).
- `yfinance` imported but unused in backtest/hashem_backtest.py.
- Latent crash bugs identified statically: `close_all_positions`, `close_all_pending_orders`, `close_all_pending_orders_with_type` iterate `positions` after a `None` check that only `pass`es (INFERRED TypeError when terminal returns None).
- `state.json`-style runner absent: nothing calls `save_state`/`load_state` despite imports in bot.ipynb — the state-driven architecture (ABCD/Gartley/Butterfly keys) is incomplete in the current tree.

## Bottom line
**No blocking issue prevented the Phase 0 static inspection itself: every project source file was fully read and analyzed.** The material blockers are the missing strategy file (§1), the misplaced walk-forward module (§2), and the class of facts that only runtime verification can establish (§5). Runtime behavior remains unverified.
