# R0 — RESEARCH INFRASTRUCTURE AUDIT

Generated: 2026-09-05 | Scope: READ-ONLY inventory of the existing research
infrastructure against the Master Research Protocol requirements (§4).

## 1. Inventory — component map

| Layer | Component | Location | State |
|---|---|---|---|
| Data Loader | `load_windows` / `window_bounds_from_m3` / TZ-corrected range fetch | `research_harness.py` L20-70 | MATURE — coherent df= pipeline, start_pos=1, TZ fix (CP6 v2 lesson) |
| Backtest Engine | `backtest()` / `run_backtest()` | `backtest/hashem_backtest.py` | VERIFIED — CP2 12/12, deterministic on frozen inputs |
| Engine Mirror | `harness_backtest` (fixed mode) | `research_harness.py` L128-196 | VERIFIED — equivalence True (CP4b) |
| Indicator Layer | 16 backtest indicators (df= parameterized) | `backtest/indicators.py` | VERIFIED — no self-fetch (CP1) |
| Strategy Signal Layer | A1-v1, A2-v1 (frozen), A2-v2 | root `strategy_*.py` | FROZEN variants; A1 RETIRED, A2-v1 control, A2-v2 RETIRED |
| Optimizer | grid + walk-forward | `backtest/optimizer.py`, `backtest/Optimizer walkforward.py` | present (imports valid since move) — NOT used in the registered pipeline (D1: no grid) |
| OOS Pipeline | freeze -> manifest -> integrity -> one-shot eval | `cp6_oos_freeze.py` / `cp6_oos_validation.py` pattern | MATURE — reusable |
| Artifact Storage | `project_audit/` + `stability_windows_cache/` + git | repo | 72 audit files; all hashed; immutable-by-convention (rule 7) |
| Test Infrastructure | 5 suites (54 checks) | `tests/` | PASS (LOOP1-4 + CP20) |
| Determinism Infrastructure | A/B pattern + registered constants (SEED=55056, N_BOOT=10000) | cp5_determinism / cp6 / cp5_9 scripts | MATURE — per-experiment scripts |
| Safety Layer | None-guards, fail-safe kill-switches, retcode checks, HARD_RISK_CAP | `module/mt5.py`, `bot_runner.py` | PASS (CP19-CP22) |

## 2. Gap analysis vs Master Research Protocol

| Protocol requirement | State | Gap |
|---|---|---|
| R1 Data Registry + versioning | manifests exist per-dataset | **NO unified registry** -> built this phase (`DATA_REGISTRY.json`) |
| R2 Research Contract standard | pre-registrations exist ad-hoc (CP5.0, CP5.9) | **NO standard template** -> built (`RESEARCH_CONTRACT_TEMPLATE.md`) |
| R4 Hypothesis Registry | statuses scattered across audit files | **built** (`HYPOTHESIS_REGISTRY.json`) |
| R5 Determinism framework | per-experiment scripts | documented (`RESEARCH_INFRASTRUCTURE_GUIDE.md`) — adequate |
| R6 Baseline comparison | baseline = locked control only; random-entry baseline NEVER computed | **GAP registered** — required for any new hypothesis (R6 gate) |
| R8 Statistical validation | hit-rate + Wald + HAC + MBB + Bonferroni implemented | adequate (reuse constants) |
| R11 Economic validation | C0/C1/C2 constant-cost arithmetic | **GAP: no per-trade cost/slippage ledger** — required before any DEMO claim |
| R13 Independent reproduction | OOS used fresh scripts; no Engine-B duplicate | **GAP registered** — needed at DEMO-eligibility, not before |
| R14 Multi-regime validation | never executed (no regime labels) | **GAP registered** |
| Experiment Ledger | none | **built** (`EXPERIMENT_LEDGER.json`) |
| ML policy | n/a (no ML used) | documented in guide |

## 3. Verdict

**NO CRITICAL INFRASTRUCTURE DEFECT.** The pipeline that produced the
NO-PROVEN-EDGE verdict is sound; the gaps are organizational artifacts
(registry/contract/ledger), built in this phase. Two research gaps (R6 random
baseline, R11 per-trade cost ledger, R13 engine-B, R14 regimes) are registered
as REQUIRED gates for any future DEMO-eligibility claim.

## 4. Frozen-artifact protection statement

No frozen dataset, prior report, or retired result was read-modified. The
registry files created in this phase are NEW artifacts (rule 7 respected).
