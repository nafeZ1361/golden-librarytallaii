# PHASE 1 — PROJECT BASELINE (Architecture Map · Dependency Map · Risk List · Test Baseline)

Status: **PHASE 1 DELIVERABLE — READ-ONLY RECONNAISSANCE. NO SOURCE MODIFIED.**
Date: 2026-09-20 (sandbox) | Repo: `nafeZ1361/golden-librarytallaii`
Scope authority: Master Execution Plan §Phase 1 (Gate: *no change until architecture approval*).

> Evidence rule (repo standard, `codebase_map.md`): every statement is classified
> **CONFIRMED** (read/executed directly), **INFERRED** (derived), or **UNKNOWN**.

---

## 0. Headline finding (read this first)

The workspace has **two different realities** depending on which git tree you read:

| Reality | What it is | Where |
|---|---|---|
| **`main` (checked out here)** | ~13 k lines of live/backtest/strategy code + research scripts + tests, but **NO `project_audit/` governance artifacts** and **no datasets** | working tree |
| **`origin/code-refactoring-guide-41a87`** | The **same** source **plus** a complete `project_audit/` evidence factory (CP0→CP22, frozen datasets, experiment ledger, forward-monitoring contract) | remote branch |

**CONFIRMED:** the entire history of this project — audits, frozen datasets, the
research verdict, the safety gates — lives on `origin/code-refactoring-guide-41a87`
and is **absent from `main`**. This is the single most important baseline fact.

**Binding verdict already on record** (`project_audit/FINAL_PROJECT_VERDICT.md`,
`CP18_LIVE_AUTHORIZATION_GATE.md`, `CP21_22_FINAL_SAFETY_GATE.md`):

```
RESEARCH  : NO PROVEN EDGE  (A1-h5 collapsed 55.60% IS -> 49.29% OOS; FAILED REPLICATION)
SAFETY    : PASS            (engineering: 54/54 regression; single entry point bot_runner.py)
LIVE      : DENIED          (no order may be placed on this evidence base)
FORWARD   : one dormant pre-registered contract (first-breakout fade, h5), DORMANT
```

The binding skill in this repo (`.agents/skills/research-governance/SKILL.md`)
states its **prime directive**: this agent is *not* a profit/win-rate maximizer;
it is an evidence factory expected to **retire** hypotheses. Optimizing for PnL is
the exact chain that already destroyed every prior hypothesis.

**Consequence for the Master Execution Plan:** the plan is a *sound generic*
research framework, but it is written as if the project were **greenfield**
("Phase 1 — understanding the existing state", Phases 3/4/5 marked "PASS",
Phase 6 "in progress"). In this repo those phases are **not greenfield** — the
data is **burned**, the verdict is **NO EDGE**, and there is **no `ml/` package**.
Executing the plan literally would (a) re-create artifacts that already exist
elsewhere and (b) re-look at burned data. This must be resolved by Cline
(scope decision) **before any Phase 2+ work**. See §6.

---

## 1. ARCHITECTURE MAP

### 1.1 Component groups (CONFIRMED by static read)

```
golden-librarytallaii/
├── backtest/                     # SIMULATION ONLY (no order_send)
│   ├── hashem_backtest.py  1366L  core engine: backtest()/run_backtest()/optimize_strategy()/backtest_candle()
│   ├── indicators.py       1015L  backtest variants of indicators (signal/trend lists aligned to df)
│   ├── optimizer.py         625L  grid-search (ThreadPoolExecutor); hard dep on tqdm
│   ├── backtester.py         65L  top-level script; module-level side effects (mt5.initialize + run on import)
│   └── "Optimizer walkforward.py" 369L  walk-forward variant — MISPLACED/BROKEN here (relative imports)
├── module/                       # LIVE TRADING LAYER (reaches mt5.order_send)
│   ├── mt5.py              1384L  broker API wrapper + safety hardening (MT5DataError, retcode verify)
│   ├── indicators.py       2599L  live indicator library (supertrend, trend_ali, SMC ports, ...)
│   ├── stg.py               815L  strategies (supertrend_stg, abcd_strategy, risk helpers)
│   ├── modifyPosition.py    113L  SL->breakeven, partial close, smartTP/smartSL
│   ├── monitor_bot.py       235L  read-only Telegram monitor bot
│   ├── telegram.py          263L  notifications (env-configured; no broker reach)
│   └── state_io.py           34L  JSON state save/load
├── bot_runner.py            262L  ★ SOLE AUTHORIZED PRODUCTION ENTRY POINT (DRY-RUN default)
├── bot.ipynb                     4 cells: cell1 config, cell2 supertrend_stg, cell3 live loop, cell4 Hedge-Grid EA
├── strategy_a1_meanrev.py    43L  research strategy A1 (research artifact only)
├── strategy_a2_breakout.py   82L  research strategy A2
├── strategy_a2_v2_firstbreakout.py 74L  frozen A2-v2 rule (forward contract population)
├── strategy_a4_v1_sessionbreakout.py 75L  research strategy A4
├── research_harness.py      254L  shared research harness (window loader, hit-rate, walk-forward)
├── cp1..cp5_*_test.py / determinism_test.py / lag_bias_test*.py / stability_windows_test.py
│                                 research/integrity scripts (MT5-dependent)
├── tests/                        8 pytest files (safety regression; MT5-mock based)
├── state_io.py (root)        72L  ORPHANED duplicate of module/state_io.py
├── config/mcporter.json           MCP client config (autoclaw productivity/github; notion disabled)
├── .agents/skills/research-governance/SKILL.md  ★ BINDING governance skill
└── requirements.txt              pinned deps (see §2)
```

### 1.2 Data-flow (CONFIRMED static; from `data_flow.md` on the other branch)

```
LIVE  : MT5 terminal ──copy_rates_from_pos(M1)──> module.mt5.candle()/heikin_ashi()
          └─ floor(M1 ts)->TF bucket -> groupby agg -> last `limit` buckets (INCLUDES forming bar @[0])
          -> module.indicators.* -> strategy -> bot_runner gates -> create_order -> mt5.order_send

BACKTEST: MT5 terminal ──copy_rates_from_pos(native TF)──> backtest_candle() -> backtest/indicators
          -> hashem_backtest.backtest()/run_backtest()   (NO order_send)

RESEARCH: research_harness.load_windows() -> frozen CSV windows -> strategies A1/A2/A4
          -> hit_rate()/walk_forward()  (MT5-free when reading frozen CSVs)
```

**Key structural fact (CONFIRMED):** live `candle()` **resamples from M1**, while
backtest pulls **native TF bars** — the two data bases are **not identical**
bar-for-bar. This is a documented, still-open discrepancy.

### 1.3 Entry points & risk classes

| Entry point | Trigger | Order reachable? | Class |
|---|---|---|---|
| `bot_runner.py` | manual | YES, only if `DRY_RUN=0` **AND** `ALLOW_LIVE=1` **AND** demo account | HIGH (guarded) |
| `bot.ipynb` cell 3 | manual cell exec | YES (live loop, 8 strategies, 1m) | CRITICAL (non-prod by policy) |
| `bot.ipynb` cell 4 | manual cell exec | YES (grid EA; stored output shows a past `retcode=10018` attempt) | CRITICAL (non-prod by policy) |
| `backtest/backtester.py` | import side-effect | NO (no order_send) | LOW (but runs on import) |
| `tests/*`, `cp*_test.py` | pytest / manual | NO (mock/no real MT5) | LOW |

**Authorized production path (CONFIRMED, CP21):** `bot_runner.py` only. Its gate
order is `DD-daily → DD-total → SIGNALS([-2] closed bar) → TIME → NEWS → RISK
(HARD cap 2.0%) → ORDER VALIDATION → CREATE ORDER`, each failing gate logs
`[GATE] ... NO ORDER`.

### 1.4 ML entities — **there are none**

**CONFIRMED:** `grep` for `sklearn|scikit|LogisticRegression|StandardScaler|
train_test_split|model_registry|joblib` across the checked-out tree returns **no
matches** (only `research_harness.py` matches the word `walk_forward`, which is a
**rule-based** walk-forward, not ML). There is **no** `ml/`, `features/`,
`datasets/`, `models/`, or `registry/` package. `bot.ipynb` has **no** sklearn
usage. **The ML system described in Master-Plan Phases 3–8 does not exist here.**

---

## 2. DEPENDENCY MAP

### 2.1 Declared vs installed (sandbox)

`requirements.txt` pins (CONFIRMED, from file):

```
metatrader5==5.0.5388 | numpy==2.2.6 | pandas==2.3.3 | pandas-ta==0.4.71b0 | ta==0.11.0
pytz==2025.2 | requests==2.32.5 | plotly==6.5.0 | yfinance==0.2.66 | tqdm==4.67.1
pyTelegramBotAPI>=4.21 | mplfinance==0.12.10b0
```

Sandbox availability (CONFIRMED by `importlib.util.find_spec`):

| Package | Status | Impact |
|---|---|---|
| `MetaTrader5` | **MISSING** | `module/*` and `backtest/*` cannot import; all MT5-dependent tests error at collection |
| `ta` | **MISSING** | same |
| `pandas_ta` | **MISSING** | same |
| `telebot`, `mplfinance` | **MISSING** | telegram/monitor paths unimportable |
| `yfinance` | **MISSING** | imported (unused) in `hashem_backtest.py` |
| `numpy` (2.3.5), `pandas` (2.2.3) | OK | versions differ from pins (2.2.6 / 2.3.3) |
| `sklearn` 1.6.1, `pytest` 9.0.3, `plotly`, `requests`, `pytz`, `tqdm` | OK | sklearn present but **unused by project code** |

### 2.2 Internal dependency highlights (CONFIRMED)

- `module/mt5.py` defines **no `__all__`**; `from .mt5 import *` re-exports `pd`,
  `np`, `mt5`, `requests`, `pytz` and **all order functions** — star-import
  coupling throughout `module/`.
- `module/telegram.py` uses `pd.to_datetime` **without importing pandas** — works
  only via the `from .mt5 import *` side effect.
- `backtest/optimizer.py` has a **hard `tqdm` import** (no fallback).
- `backtest/hashem_backtest.py` imports `yfinance` but **never uses it**.
- `"Optimizer walkforward.py"` uses **relative imports** for modules that exist
  only in `backtest/` → **broken at its current location**.
- **No import cycles** found in `module/` or `backtest/`.
- `state_io.py` (root) is an **orphaned duplicate**; only `module.state_io` is used.
- **No `pyproject.toml` / `pytest.ini` / `conftest.py` / lock file** exists.

### 2.3 Governance/agent dependencies

- `.agents/skills/research-governance/SKILL.md` — **binding** process rules
  (pre-registration, freeze-then-validate, append-only ledger, consequence
  clauses, no fabrication, human-only LIVE key).
- `config/mcporter.json` — MCP servers (productivity, github; notion off).
  No MCP is wired into any model-training path (consistent with Plan Phase 13).

---

## 3. RISK LIST

Severity × likelihood. "Gov" = governance/research-integrity risk.

| # | Risk | Sev | Class | Evidence |
|---|---|---|---|---|
| R1 | **Data is burned.** In-sample 2021-06→2026-09-04 fully consumed across 3 registered datasets; look budget m=4 spent. Any new lookback re-look = statistical cost that cannot be repaid. | **Critical** | Gov | `FORWARD_CONTRACT.md`, `EXPERIMENT_LEDGER.json` |
| R2 | **`main` lacks `project_audit/`.** Governance history, frozen datasets, ledger and forward contract exist only on `origin/code-refactoring-guide-41a87`. `main` readers see a project with **no record of its own verdict**. | **Critical** | Gov/Provenance | git tree diff (§0) |
| R3 | **`main` lacks the frozen datasets** (`cp5_window_*.csv`, `cp6_*`, `r1_*`) → any Phase-2 "dataset pipeline" on `main` would need MT5 (unavailable) or would silently diverge from the frozen identity. | **High** | Reproducibility | no `*.csv` on `main` |
| R4 | **Live execution exists in-tree** (`bot.ipynb` cells 3–4; `module/mt5.py` order functions). One env misconfiguration (`DRY_RUN=0 ALLOW_LIVE=1` on demo) places orders. | **High** | Safety | `bot_runner.py` header; notebook cells |
| R5 | **MT5 + `ta`/`pandas_ta` unavailable in sandbox** → the entire live/backtest layer is **un-importable here**; the current test baseline **cannot run**. | **High** | Environment | §2.1 |
| R6 | **Test suite cannot be collected on `main`** (8 collection ERRORs, all `ModuleNotFoundError: MetaTrader5`). Baseline is effectively **UNVERIFIABLE in this environment**. | **High** | QA | pytest run (§4) |
| R7 | **"Phases 3/4/5 marked PASS" in the plan is aspirational on `main`** — there is no feature/target/validation ML code here. Risk of a reviewer trusting a status that no artifact on `main` supports. | **High** | Gov | §1.4 |
| R8 | **Live/backtest data-base mismatch** (M1-resample vs native TF) — documented, unresolved. | Medium | Correctness | `data_flow.md §1` |
| R9 | **Lookahead candidates** flagged (position-0 forming bar in `candle()`; `[-1]`/`[-2]` conventions; repaint-prone `zigzag`/`nadaraya_watson`; intrabar TP/SL ordering). | Medium | Leakage | `data_flow.md §9` |
| R10 | **Duplication / dead code**: root `state_io.py`; duplicate `supertrend_stg`; misplaced broken walkforward file; unused `yfinance`. | Low | Maintainability | §2.2 |
| R11 | **No reproducibility manifest on `main`** (no hashes/lock) — a run here is not reproducible vs the frozen environment. | Medium | Reproducibility | §2.1 |
| R12 | **MCP governance**: Plan Phase 13 must keep MCP out of the training path; currently none is wired (good) — must stay that way. | Low | Governance | `config/mcporter.json` |

**No new lookahead/leakage was introduced by this Phase 1 work** — it is read-only.

---

## 4. TEST BASELINE

**Method:** `python3 -m pytest tests/ --collect-only -q` (no MT5, no orders).

```
tests/test_collector_repair.py        ERROR  (import forward_collector <- project_audit/forward_monitoring: ABSENT on main)
tests/test_cp20_integration.py        ERROR  (ModuleNotFoundError: MetaTrader5)
tests/test_forward_collector.py       ERROR  (forward_collector ABSENT on main)
tests/test_loop1_none_safety.py       ERROR  (MetaTrader5)
tests/test_loop2_risk_cap.py          ERROR  (MetaTrader5)
tests/test_loop3_network_session_retcode.py  ERROR (MetaTrader5)
tests/test_loop4_quarantine_credentials.py   ERROR (MetaTrader5)
tests/test_mt5_hardening.py           ERROR  (MetaTrader5)
=> no tests collected, 8 errors
```

**Recorded reference baseline** (from the repo's own records, CP22 on the other
branch): `LOOP1 15/15 · LOOP2 9/9 · LOOP3 12/12 · LOOP4 6/6 · CP20 12/12 = 54/54 PASS`
— but that requires the **full environment + `project_audit/`**, neither present
on `main`/sandbox.

**Two baseline defects exposed (not caused) by this run:**
- **B1:** 6 of 8 test files cannot import without `MetaTrader5` → environment gap.
- **B2:** 2 of 8 test files depend on `project_audit/forward_monitoring/forward_collector.py`,
  which **does not exist on `main`** → governance-artifact gap (R2).

**Conclusion:** the *current, on-`main`* test baseline is **RED / un-runnable**,
not the 54/54 recorded elsewhere. This is a **Phase-1 Gate finding**, not a code
regression. No test was modified.

---

## 5. PHASE-BY-PHASE RECONCILIATION (plan vs repo reality)

| Plan Phase | Plan status | Reality on `main` | Reality in governance records | Reconciliation needed |
|---|---|---|---|---|
| 1 Baseline | (this) | DONE (this doc) | `codebase_map.md`, `data_flow.md`, etc. exist on other branch | Port or reference |
| 2 Dataset | "PASS" | **No dataset code / no data on main** | Frozen datasets + integrity battery exist (other branch) | Cline decision |
| 3 Features | "PASS" | **No ML feature code** | Not an ML project historically | Cline decision |
| 4 Targets | "PASS" | **No target code** | — | Cline decision |
| 5 Validation | "PASS" | `research_harness.walk_forward` = **rule-based**, not ML TS-split | CP4 WFO was rule-based | Cline decision |
| 6 ML train/registry | "in progress" | **Absent** | **Never existed** | Cline decision |
| 7–11 | pending | Absent | Analogues: CP6 OOS, CP10 economic, CP11 risk | Reuse, don't duplicate |
| 12–17 | pending | Absent | CP13–CP18, forward contract | Bind to governance |

---

## 6. GATE — REQUIRED CLINE DECISIONS BEFORE PHASE 2

The Phase-1 Gate says *no change until architecture approval*. The following are
**blocking scope decisions**, each of which the plan's literal path would get
wrong. **No Phase 2+ work will start until these are answered.**

1. **Branch / source of truth (R2).** Should `project_audit/` (and the frozen
   datasets) be restored onto `main` from `origin/code-refactoring-guide-41a87`,
   or should all future work target that branch? *Without this, the ledger and
   pre-registration chain are not visible where the work happens.*
2. **Is this an ML restart or an extension of a RETIRED, burned research line
   (R1/R7)?** The Master Plan reads as greenfield ML; the repo records
   NO PROVEN EDGE with the look budget spent. If the intent is a **new ML
   program**, it must be **pre-registered as a new hypothesis** that beats the
   locked controls (`baseline-lock-v1`) under the same methodology, and it must
   state **which data it may look at** (the burned windows are off-limits for
   confirmatory claims).
3. **Data source for Phases 2–5 (R3/R5).** MT5 is unavailable in this sandbox and
   there is no dataset on `main`. Frozen CSVs live on the other branch. Confirm
   the authoritative dataset and that Phases 2–5 will **reuse frozen data** rather
   than re-fetch.
4. **Scope boundary vs the existing governance pipeline (R4/R12).** Confirm that
   the Plan's Phases 9–17 map onto the existing CP10/CP11/CP16/CP17/CP18 gates and
   the forward contract, **rather than creating parallel, unaudited machinery**.
5. **What "PASS" means for Phases 3–5.** These are marked PASS in the plan but have
   no artifact on `main`. Either (a) they will be re-implemented and re-tested as
   new ML components, or (b) the plan's status column is corrected to reflect that
   no such artifacts exist here. **A status must not be trusted without an artifact.**

---

## 7. PHASE 1 SUMMARY

- **Architecture Map:** delivered (§1). Live layer (`module/`), simulation layer
  (`backtest/`), research layer (strategies + harness), single guarded entry point
  (`bot_runner.py`), non-prod notebooks. **No ML layer exists.**
- **Dependency Map:** delivered (§2). MT5/`ta`/`pandas_ta`/`telebot`/`mplfinance`
  unavailable in-sandbox; versions diverge from pins; no lock/manifest.
- **Risk List:** delivered (§3). Two Critical (burned data; missing audit on
  `main`), several High (in-tree live path; un-runnable tests; status without
  artifact).
- **Test Baseline:** delivered (§4). On `main`/sandbox: **RED — 8/8 collection
  errors**; reference 54/54 requires the full env + `project_audit/`.

**Gate status:** `PHASE 1 = COMPLETE (read-only). PHASE 2+ = BLOCKED pending Cline
decisions in §6.` No source file was modified; no data was touched; no MT5/broker
contact; no order.

---

*Read-only reconnaissance. This document introduces no experiment, no result, and
no claim about strategy performance.*
