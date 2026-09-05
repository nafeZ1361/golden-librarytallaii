# CP19 — ENGINEERING & SAFETY AUDIT (live-trading module)

Generated: 2026-09-05 | READ-ONLY audit; NO source changed, NO order, NO
backtest/optimization, NO research-freeze touch. Every finding has file:line
evidence. Fixes are PROPOSED and require authorization (source-change gate).

## Item-by-item findings

### 1. Position/pending close family
- `close_all_positions` (mt5.py L209-216) and `close_all_pending_orders`
  (L778-785): None-guard EXISTS but **silently returns** — in a terminal
  disconnect, the kill-switch path "succeeds" while closing NOTHING.
  **D3 (HIGH): silent no-op on failure.** Fix: log loudly + return a status
  the caller must check (and re-assert zero positions after close attempts).
- `close_half_with_comment` (L787-801), `close_all_with_comment` (L803-813):
  **NO None guard** -> `TypeError` when terminal returns None.
  `count_position_now` (L1033-1046), `total_position_comment` (L1101-1108):
  same missing guard. **D2 (HIGH).**
- `close_all_pending_orders_with_type` (L1153-1164): guard present, silent
  no-op same as D3.

### 2. risk_corrector / risk_corrector_comment (L1050-1098) — CONFIRMED UNSAFE
- Escalates risk toward `max_risk=100` (% of balance) to chase deficits;
  `max(adjusted, risk)` floor guarantees risk NEVER decreases. **D4 (CRITICAL
  by design).** ACTIVE in the notebook live path (see item 10).
- Proposed fix: hard ceiling (e.g., min(adjusted, 2 x base)) — or better,
  removal from any live path; the anti-martingale response already exists in
  stg.py (risk halves after losses).

### 3. Draw-down checkers
- `total_draw_down` (L1020-1028): `mt5.account_info().equity` — **no None
  check** -> AttributeError exactly when the terminal is down (the moment the
  kill-switch must work). **D1 (HIGH).**
- `pnl_today` (L971-1002): `history_deals_get` and `positions_get` results are
  iterated **without None guards** -> TypeError feeds straight into
  `daily_draw_down_checker` (L1007). **D1b (HIGH).**
- Logic itself (percentage vs start balance / equity) is sound; the defect is
  purely failure-mode handling.

### 4. is_news / check_time
- `fetch_economic_news` (L833-848): `requests.get(url)` with **no timeout, no
  try/except, no status-code check, no schema guard** -> any network failure or
  JSON change raises inside the trading loop. **D6 (MEDIUM).**
- `is_news` (L875-890) + module-global `cache` (L828-831): global mutable
  state; stale-cache fallback absent on fetch failure. **D13 (INFO).**
- `check_time` / `check_time_min` (L663-680): compare against **UTC wall
  clock** while the rest of the module computes a broker offset
  (`get_broker_offset`, L19) — session gating would be shifted vs broker time.
  **D7 (MEDIUM).** Also: is_news/check_time are NOT called by bot_runner.py;
  notebook usage = NONE found -> currently inert paths (see item 10).

### 5. manage_pending_orders (stg.py L727-813) / modify_tp (mt5.py L734-752)
- `manage_pending_orders`: state/None/tick guards present (good); BUT
  `remove_order` results are unchecked (L797/806/811) -> a rejected cancel
  (e.g., order already filled) fails silently and the position is never
  managed. **D8 (MEDIUM).**
- `modify_tp` (L734-752) and `modify_stop` (L714): fire-and-forget — no
  retcode verification, returns None on success path. **D8 (MEDIUM).**

### 6. abcd_strategy (stg.py L307-727, ~420 lines)
- Called by NOBODY in production paths (only the CP3 test inspects its source).
  **D9 (LOW): dead code.** Keep (it is integrity-tested) or quarantine behind
  an explicit `__main__`/docs note; no safety impact while uncalled.

### 7. Gartley_Stg / Butterfly_Stg
- Referenced ONLY by `bot_state.json` keys (empty dicts). Code MISSING from
  the repository entirely (the "stg peleh.py" file never recovered).
  **D10 (MEDIUM): orphan state keys — any future runner reading that state
  file would find strategies with no implementation.** Fix: remove the keys or
  recover the file; both require user decision.

### 8. Optimizer walkforward.py
- Relative imports (`from .hashem_backtest/.indicators/.optimizer`, L73-75) are
  now VALID — the file lives in `backtest/` where all three targets exist.
  **D11 (RESOLVED)** — `blocking_issues.md` §2 is stale on this point (it also
  still claims no requirements.txt exists). Recommend updating the stale audit
  doc at the next documentation pass.

### 9. telegram.py
- `TOKEN = 'yorToken'` placeholder (L6) — inert; deps (pyTelegramBotAPI)
  NOT installed; `echo_all` handler defined but no polling loop.
- `CHANNEL_ID = '337250342'` hardcoded (L11) — a real-looking numeric ID
  committed to history. **D12 (LOW): credential-hygiene risk pattern.** Fix:
  env-var pattern + never commit real tokens; keep the module out of any
  trading path.

### 10. bot.ipynb actual control path (cell 2 = live Hedge-Grid)
- Before EVERY `create_order`: `risk_corrector_comment(...)` is called
  (escalation input) — grep evidence: 16 pre-order call sites in cell 2.
- **ZERO calls** to `daily_draw_down_checker`, `total_draw_down`, `is_news`,
  `check_time`, `close_all_positions` in the notebook -> **D5 (CRITICAL): the
  notebook live path has NO kill-switch, NO news filter, NO session gating
  before orders — the only pre-order control is the risk ESCALATOR itself.**
- Contrast: `bot_runner.py` (the Phase-2 safe runner) DOES wire kill-switches
  and excludes the escalators — but the notebook remains the dangerous path.

## Defect register (summary)

| ID | Severity | Location | Defect |
|---|---|---|---|
| D1 | HIGH | mt5.py L1021, L985, L994 | None-crash inside kill-switch path |
| D2 | HIGH | mt5.py L787-813, L1033-1046, L1101-1108 | missing None guards -> TypeError |
| D3 | HIGH | mt5.py L209-216, L778-785, L1153-1164 | silent no-op close on disconnect |
| D4 | CRITICAL | mt5.py L1050-1098 | risk escalator to 100% (active in notebook) |
| D5 | CRITICAL | bot.ipynb cell2 | no kill-switch/news/time gating before orders |
| D6 | MEDIUM | mt5.py L833-848 | news fetch: no timeout/exception handling |
| D7 | MEDIUM | mt5.py L663-680 | UTC vs broker-offset session inconsistency |
| D8 | MEDIUM | mt5.py L714-752; stg.py L797-811 | unchecked order_send/remove retcodes |
| D9 | LOW | stg.py L307-727 | dead code (abcd_strategy) |
| D10 | MEDIUM | bot_state.json | orphan Gartley/Butterfly keys, code missing |
| D11 | RESOLVED | backtest/Optimizer walkforward.py | imports valid after move (stale doc) |
| D12 | LOW | telegram.py L6/L11 | hardcoded credential pattern |
| D13 | INFO | mt5.py L828-831 | global mutable news cache |

## Proposed fix order (pending authorization — NO change applied this stage)

1. D1/D2/D3: add None-guards that RAISE a typed error (or return explicit
   status) + loud logging — the kill-switch must never fail silently.
2. D4/D5: remove risk escalators from any live path; wire kill-switches +
   news/time gates into whatever runner is used; notebook must not be a
   production entry point.
3. D6/D7/D8: timeout+try/except on news; broker-offset for session gates;
   retcode checks on every order_send/remove.
4. D9/D10/D12: quarantine dead code; resolve orphan state keys (user decision);
   env-var credentials.
5. D11: refresh stale audit docs.

## LOOP-4 addendum (D9/D10/D12 executed 2026-09-05)

- D9: `abcd_strategy` QUARANTINED — banner added at the definition (stg.py);
  function preserved intact; no production caller exists (verified).
- D10: **MISSING DEPENDENCY registered** — `Gartley_Stg` / `Butterfly_Stg` are
  referenced only by `bot_state.json`; their source (the never-recovered
  "stg peleh.py") does not exist in the repository. Resolution (restore the
  file vs remove the orphan keys) requires a USER DECISION; bot_state.json was
  deliberately NOT modified (user runtime data).
- D12: `module/telegram.py` rewritten — credentials ONLY from environment
  (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHANNEL_ID`); placeholder `yorToken` and
  the hardcoded numeric channel id REMOVED; import-safe without telebot/
  mplfinance (`TELEGRAM_AVAILABLE` flag); duplicate echo_all handler removed;
  send functions no-op safely and never print credentials. NOTE: the numeric
  channel id remains in git history (mitigation: treat it as rotated; it grants
  no trading capability).

