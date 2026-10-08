# PROJECT_STATE.md

Last updated (UTC): 2026-10-08T11:57:00Z
Updated by: QCode/nafeZ1361
Current stage: Stage 7.3 Governance Alignment
Current HEAD (main): 36df7c9

## PROJECT GOAL

golden-librarytallaii یک مخزن پژوهشی و اعتبارسنجی برای سیستم ML/Trading مبتنی بر XAUUSD است که هدف آن ایجاد یک زنجیره قابل‌تکرار، بدون leakage و قابل ممیزی از داده، مدل، بک‌تست و evidence است. پروژه در حال حاضر به بازسازی کامل نیاز ندارد؛ اولویت با تکمیل اصلاحات کنترل‌شده، اعتبارسنجی مستقل، حفظ شواهد و عبور مرحله‌ای از Gateهای حاکمیتی است.

## CURRENT STATUS

- Baseline test suite: 171 passed + 2 subtests (pytest tests/ -q, full green).
- Stage 7.1 Technical Closure: **NOT FINAL-PASS** — PR #14 remains open and unmerged; required bot.ipynb smoke-check and final validation/merge gate are incomplete.
- Stage 7.3 Governance Alignment: DONE (pending final signature).
- Runtime mode: PAPER by default; LIVE blocked unless ENABLE_LIVE_TRADING=YES.

## LOCKED

- stage7/evidence/run1/ and stage7/evidence/run2/ — frozen run evidence; untouched by all current PRs.
- stage7_data/ — frozen dataset artifacts.
- Dataset SHA256: a7d856d8…6414 (480,087 rows).
- Locked split_manifest.json SHA256: 435c12cd…cba4 (see GAP-001 in stage7/GAPS.md).

## OPEN GAPS

Tracked in stage7/GAPS.md:

- GAP-001 / F-006 (MEDIUM, OPEN): split_manifest.json record mismatch between manifest fields and CSV row counts. Document-only per Decision 8; no code change; defer to Stage 8.
- GAP-002 / F-004 (RESOLVED): Risk config duality — fixed via `RiskValidator(RiskLimits.from_env())` at module/execution.py:53 (commit 222b76b); config.py documented as single source of truth.
- GAP-003 — Time-of-Day regime — RESEARCH GAP — Stage 7.2/8 — no impl
- GAP-004 — ATR/Volatility regime — RESEARCH GAP — Stage 8 — no impl
- GAP-005 — Monte Carlo trade-sequence — VALIDATION GAP — Stage 8 — no impl
- GAP-006 — Parameter landscape — VALIDATION GAP — Stage 8 — no impl
- GAP-007 — Slippage/execution friction — VALIDATION GAP — HIGH PRIORITY — Stage 8 (before any filter work) — no impl
- GAP-008 — OFI/Depth Skew — RESEARCH CANDIDATE — Stage 7.2 — no impl
- GAP-009 — `heikin_ashi().obj` mismatch — OPEN, pre-existing, out of scope PR #14.
- GAP-010 — missing `ml_signal_adapter` — OPEN, pre-existing/highly likely; historical deletion not proven; deferred.
- GAP-011 — PROJECT_STATE governance/document drift — OPEN pending reconciliation validation.
- GAP-012 — PR #14 branch/integration drift — OPEN / assessment pending; no rebase/merge yet.
- F-005 (PR #14, commit 1d54d8c): singleton import-time LIVE state in module/mt5.py.
- F-002 (PR #14, commit 8f8939c): non-deterministic peak_memory_mb in evidence.
- F-012: requirements.txt missing deps — resolved upstream (fa600be).
- F-003 (PR #15, commits 8df7799, 1dcfff6): skll/ pollution cleanup.

## POTENTIAL ENHANCEMENTS

Tracked in stage7/GAPS.md (GAP-003..GAP-008; none implemented).

## COMPLETED WORK

| Finding | Fix | Location |
|---|---|---|
| F-005 | PR #14 | commit 1d54d8c |
| F-002 | PR #14 | commit 8f8939c |
| F-012 | merged upstream | commit fa600be |
| F-003 | PR #15 | commits 8df7799, 1dcfff6 |
| F-004 | PR #16 | commit 222b76b |
| GAPS registry | PR #16 | commit 80f5cf3 (stage7/GAPS.md) |

Merged into main (2026-10-08): #17 → be8da8c, #15 → c5bb24b, #16 → 7f61d64.

## NEXT ACTIONS

1. Governance reconciliation validation for GAP-009..GAP-012 and Decisions 11–17.
2. Fresh audit of PR #14 against current main to assess branch/integration drift.
3. Human Confirmation for the chosen PR #14 integration action.
4. Required targeted validation, including the manual bot.ipynb smoke-check gate.
5. Final Human Confirmation for merge.
6. Merge PR #14.
7. Verify Stage 7.1 closure with evidence.
8. Stage 8 Final Audit only after Stage 7.1 closure.

## HARD CONSTRAINTS

- Never rebuild; smallest justified change only.
- Never `git reset --hard`, `git clean -fd`, `git add .`, `git commit -a`.
- Never claim PASS without evidence; never invent dates or metrics.
- No push/merge without separate Human Confirmation.
- ML pipeline independent of MetaTrader5; research/paper only, never real orders.
- Locked evidence directories must remain byte-identical.
- No change to `module/indicators.py`, no creation of `ml_signal_adapter.py`, and no test changes in this governance reconciliation.

## RECOVERY INSTRUCTIONS

1. Clone: `git clone https://github.com/nafeZ1361/golden-librarytallaii.git`
2. Read this file + DECISIONS_LOG.md + stage7/GAPS.md first.
3. Verify `git rev-parse main` matches "Current HEAD (main)" above; if it diverged, reconcile via PRs list before continuing.
4. Check OPEN PRs table below — any PR already merged supersedes its row here.
5. Resume only from the NEXT ACTIONS list; do not reopen resolved gaps.

## OPEN PRs

| PR | Branch | Content | Status | Merge gate |
|---|---|---|---|---|
| #14 | fix/stage71-f005-f002 | F-005 + F-002 fixes | OPEN, unmerged | fresh PR audit + manual bot.ipynb smoke-check + separate Human Confirmation |

## LEGACY PRs

Out of current scope: #12, #11, #9, #7, #6.
