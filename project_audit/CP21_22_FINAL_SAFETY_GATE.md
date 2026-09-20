# CP21 / CP22 — PRODUCTION ENTRY-POINT AUDIT & FINAL SAFETY REGRESSION

Generated: 2026-09-05 | Scope: engineering safety only. Research verdict
(CP9/CP18: NO PROVEN EDGE / LIVE DENIED) is UNCHANGED and independent of this
engineering work.

## CP21 — Production Entry-Point Audit

Sole authorized production entry point: **`bot_runner.py`** (DRY-RUN default;
live requires DRY_RUN=0 AND ALLOW_LIVE=1 AND still subject to CP18 DENIAL).

### Executed pipeline inside the runner loop (verified monotonic, positions in loop body)

```text
START → CONNECT(mt5.initialize) → VALIDATE(symbol/select)
  → KILL DD-daily (fail-safe True on evaluation failure)
  → KILL DD-total  (fail-safe True on evaluation failure)
  → SIGNALS (closed-bar only, [-2] discipline)
  → TIME CHECK  (check_time, broker-offset aware; env SESSION_*)
  → NEWS CHECK  (is_news, fail-open logged; env NEWS_FILTER, default ON)
  → RISK CHECK  (lot_calculator + HARD_RISK_CAP_PERCENT=2.0 + MAX_LOT)
  → ORDER VALIDATION (lot in (0, MAX_LOT]; non-degenerate SL/TP; tick present)
  → CREATE ORDER (retcode verified, logged)
```

Static verification: `python -c` position check inside the loop body →
`{'DD-daily': 82, 'DD-total': 354, 'TIME': 1424, 'NEWS': 1584, 'RISK(lot)': 2340,
'ORDER': 3105}` → monotonic True. Any gate failing logs `[GATE] ... NO ORDER`.

### Bypass analysis

- `bot.ipynb`: production guard cell inserted (LOOP 2/D5) — raises SystemExit
  unless `ALLOW_NOTEBOOK_TRADING=1`; the kernel then cannot reach any trading
  cell. Residual risk: a user deliberately skipping the guard cell — accepted
  and documented (notebook is non-production by policy; deletion requires a
  user decision).
- No other file calls `create_order`/`pending_order` (caller graph verified).

## CP22 — Final Safety Regression (from zero)

| Check | Result |
|---|---|
| D1 (kill-switch None-crashes) | FIXED — fail-safe TRIGGERED on any evaluation failure (broad except, CP20-INT12) |
| D2 (missing None guards) | FIXED — counters raise MT5DataError (never silent-0); close family returns explicit status |
| D3 (silent no-op closes) | FIXED — structured {attempted,closed,failed,verified_clean,status} + re-query verification + [MT5SAFETY] logs |
| D4 (risk escalator to 100%) | FIXED — HARD_RISK_CAP_PERCENT=2.0 enforced in both correctors (adversarial tests: risk=50/max_risk=100 → ≤ 2.0) |
| D5 (notebook as production) | FIXED — guard cell; bot_runner sole entry point |
| D6 (news fetch unhandled) | FIXED — timeout/status/exception/malformed guards, fail-open logged |
| D7 (session timezone) | FIXED — _broker_now() broker-offset aware, fail-open logged |
| D8 (fire-and-forget ops) | FIXED — retcode verified everywhere; close/pending verified by re-query; filling loop early-exits on DONE |
| D9 (dead code) | QUARANTINED — banner; function intact (research reference) |
| D10 (Gartley/Butterfly) | MISSING DEPENDENCY registered; bot_state.json untouched (user decision pending) |
| D11 (stale audit doc) | noted at CP19 (imports valid since the move) |
| D12 (credentials) | FIXED — env-only; placeholder + hardcoded channel id removed; import-safe |
| Regression suites | LOOP1 15/15 · LOOP2 9/9 · LOOP3 12/12 · LOOP4 6/6 · CP20 12/12 = **54/54 PASS** |
| Secrets scan | "yorToken"/"337250342" appear ONLY inside test negative-assertions; zero secrets in production code |
| Import validation | mt5/telegram/stg/bot_runner all compile |
| Frozen research artifacts | UNCHANGED (cp5 19d478230a…, cp6 b7baacd30f…, strategies 85c1781a/732d1eaa, harness c5e7844a) |
| Git state | clean working tree after commit; all changes atomic + pushed |

## FINAL SAFETY GATE

```text
D1-D3 = PASS
D4-D5 = PASS
D6-D8 = PASS
D9-D12 = PASS
CP20 = PASS (12/12 integration scenarios)
CP21 = PASS (single production entry point, gates in mandatory order, no bypass)
CP22 = PASS (54/54 regression + secrets scan + frozen integrity)

SAFETY STATUS = PASS   (engineering)
LIVE AUTHORIZATION = DENIED   (unchanged — research verdict CP9/CP18:
                               NO PROVEN EDGE; FAILED REPLICATION)
```

Safety and edge are independent axes: the robot is now ENGINEERING-SAFE, and
it still must not trade — because no edge has been proven.
