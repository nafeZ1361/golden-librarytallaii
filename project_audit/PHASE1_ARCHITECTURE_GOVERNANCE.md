# PHASE 1 — ARCHITECTURE & GOVERNANCE
**Design only. Non-executing. No implementation. No data contact.**

Registered: 2026-09-20 | Repo: `nafeZ1361/golden-librarytallaii`
Governance authority: `.agents/skills/research-governance/SKILL.md` (mandatory)
Primary execution environment: **GenSpark sandbox** (declared by owner 2026-09-20)
Secondary: Cline local (inspection/engineering only, if requested)

> Scope discipline: this document **defines** architecture and governance. It
> modifies no trading logic, trains nothing, runs no backtest, collects no data,
> installs nothing, trades nothing, and consumes no burned research data.
> It produces outputs **A–G** only, then stops for human approval.

---

## 0. Constraints carried forward (from Phase 0)

- P0-C1 (`no fabrication`): if MT5/network/data is unavailable → record, stop.
- P0-C2 (source-of-truth conflict A): local path `ketabtallaee-backup` and commit
  `2d7cf9c58f4f4de85ff0cc323ca50e754afc075c` do **not exist** in the sandbox or on
  any remote ref. Must be resolved by the owner (Open Decision F1).
- P0-C3 (`main` lacks governance): the complete `project_audit/` (CP0–CP23,
  ledger, frozen-data manifests, forward contract) lives on
  `origin/code-refactoring-guide-41a87`, not on `main`.
- P0-C4 (burned data): IS window 2021-06 → 2026-09-04 is fully consumed across
  three registered datasets; the retargeting budget is spent.
- P0-C5 (binding verdict): **NO PROVEN EDGE / LIVE DENIED**, with one dormant
  pre-registered forward contract.

---

## 1. SOURCE OF TRUTH

**Canonical:** the GitHub repository `nafeZ1361/golden-librarytallaii` (private).
Everything scientifically valid must be reconstructible from its commits + the
frozen-data manifests.

| Item | Value |
|---|---|
| Remote | `origin → github.com/nafeZ1361/golden-librarytallaii.git` |
| Primary execution | GenSpark sandbox (`/home/user/webapp`) |
| Trunk | **`main`** (to be made governance-bearing — see §2 / Open Decision F2) |
| Research record branch | `origin/code-refactoring-guide-41a87` (immutable history) |
| Agent work branch | `genspark_ai_developer` |
| Tags | `baseline-lock-v1`, `cp5-source-freeze-v1` |
| Config | no `pyproject`/`pytest.ini`/lockfile on `main` (gap) |
| Tests | `tests/` (MT5-mock safety) + root `cp*_test.py` (MT5-dependent) |
| Documentation | `.agents/skills/research-governance/SKILL.md`, `project_audit/` |
| Governance rules | the research-governance skill (mandatory) |

**Rule SOT-1:** any disagreement between local files, GitHub refs, commits, or
prior reports ⇒ **STOP, name the conflict, request approval.** No assumption.
**Rule SOT-2:** the dataset hash, not a filename, is the identity (§4).
**Rule SOT-3:** a claim is only as valid as the artifact that supports it —
"no artifact ⇒ no claim."

---

## 2. BRANCH STRATEGY

Three roles, kept distinct:

| Branch | Role | Rules |
|---|---|---|
| `main` | Integration trunk + governance record | Must carry `project_audit/` (docs, ledger, manifests) and the skill. No force-push. |
| `code-refactoring-guide-41a87` | **Immutable historical research record** | Read-only. Never rewritten. Tags above point into it. |
| `genspark_ai_developer` | Agent working branch | All Phase work lands here, then reviewed → merged to `main` via PR. |

**Proposed change (needs F2):** a **one-time, append-only restoration** of the
governance artifacts + frozen-data manifests from
`code-refactoring-guide-41a87` onto `main`, done as a merge (history preserved),
**without** deleting or rewriting the source branch. Large frozen CSVs may live
in a designated data location referenced by hash rather than in the code trunk.

**Rule BR-1:** never rewrite published history (no force-push to `main`).
**Rule BR-2:** the historical research branch is frozen; corrections are new rows.
**Rule BR-3:** one branch per Phase review; PASS + approval before merge.

---

## 3. GOVERNANCE LOCATION

Governance artifacts live in **`project_audit/`**, on the trunk:

```
project_audit/
├── EXPERIMENT_LEDGER.md / .json        (append-only; every experiment)
├── DATA_REGISTRY.md                    (frozen datasets + consumption ledger)
├── HYPOTHESIS_GENERATOR_POLICY.md
├── RESEARCH_CONTRACT_TEMPLATE.md
├── CP*_*.md                            (gate documents, English, CP format)
├── forward_monitoring/                 (dormant contract + collector)
├── ml/                                 (NEW namespace — §14, Open Decision F3)
│   ├── ML_LEDGER.md / .json
│   └── ML_*_PRE_REGISTRATION.md
└── PHASE*_*.md                         (Phase reports)
```

**Rule GOV-1:** the skill is mandatory and outranks convenience.
**Rule GOV-2:** the ML namespace (`project_audit/ml/`) **references** the
existing ledger; it never edits or re-derives it.
**Rule GOV-3:** gate documents in English (CP format); user-facing verdicts in
Persian — per the skill.
**Rule GOV-4:** append-only. Corrections are new rows, never overwrites.

---

## 4. DATASET POLICY

Datasets are **frozen by hash** and consumed under a one-look rule.

| ID | Period (broker tz) | Bars | Identity (sha256) | Status |
|---|---|---|---|---|
| DS-CP5-MAIN | 2025-12-10 → 2026-09-04 | 86,400 | `be4fa581…` | **BURNED (IS)** |
| DS-CP6-OOS | 2025-03-20 → 2025-12-10 | 86,400 | `3d615ad8…` | **BURNED (OOS)** |
| DS-ARCH-OOS | 2024-06-26 → 2025-03-20 | 86,400 | `060ba244…` | **BURNED (OOS)** |
| DS-FRAG-FWD | 2026-09-04 17:33 → 23:54 | 128 | (CP6 manifest) | supplement only |
| **RES-ARCH-2021-2024** | 2021-06-20 → 2024-06-26 | ~230k | **UNSEEN RESERVE** | one-shot, first-come |
| **RES-FORWARD** | post 2026-09-04 | accumulating | UNSEEN | cleanest future OOS |

**Rule DS-1:** never re-fetch what is frozen; if data is unavailable, record & stop.
**Rule DS-2:** burned periods may NOT support confirmatory (directional) claims for
any already-consumed hypothesis family.
**Rule DS-3:** an unseen reserve is consumed **once**; after its verdict the period
is burned for that family.
**Rule DS-4:** every run cites the dataset **identity hash**; a mismatch is a FAIL.
**Rule DS-5:** timezone = naive broker time, never converted in research data.
The `+3:30` local→broker correction is **mandatory** for any range fetch.
**Rule DS-6:** spread/slippage modeling is a **required gate** before any DEMO
claim (currently a registered limitation: C0/C1/C2 constant-pip only).

---

## 5. RESEARCH vs LIVE SEPARATION

Two environments, structurally separated (import-level, not convention-level).

| | RESEARCH env | LIVE env |
|---|---|---|
| Purpose | build/validate hypotheses & models | execute the single authorized path |
| Data | frozen CSVs (hash-verified) | live MT5 feed |
| Imports | **no order API**, no `MetaTrader5` order use | MT5 |
| Entry | research scripts / harness | **`bot_runner.py` only** |
| Output | registry artifacts, ledger rows | DRY-RUN logs / (approved) demo orders |
| MT5 | **must not be required** (tests run MT5-free) | required |
| Live trading | **impossible** | DRY-RUN default; gated |

**Rule RS-1:** research code must not import order APIs; live path must not
import training code. Enforced by a test asserting **zero order-API call sites**
outside `bot_runner.py` (the repo already has this class of test).
**Rule RS-2:** ML never bypasses the Risk layer (§A).
**Rule RS-3:** the monitor bot stays structurally read-only.

---

## 6. ML ARCHITECTURE (lightweight, sklearn-first)

Data-flow:

```
Frozen data → Data Validation → Time-Series Split → Feature Builder → Target Builder
   → [Preprocess(fit-on-train)] → Model → Evaluation → Registry
   → (optional) Regime Detector / Market-Intelligence ablation
   → Backtest adapter (reuse) → Risk layer (reuse) → Monitoring
```

### Component contracts (PURPOSE → INPUT → OUTPUT → VALIDATION → FAILURE CONDITION)

**C1 — Frozen Data Loader**
- PURPOSE: load a registered dataset by identity, never re-fetch.
- INPUT: dataset ID + expected sha256; frozen CSV path(s).
- OUTPUT: immutable DataFrame (time, ohlc, volume) + verified hash + manifest row.
- VALIDATION: recompute hash == registered; time strictly increasing; no dups; no NaN/Inf; OHLC valid.
- FAILURE: hash mismatch, missing file, non-monotonic time, or any NaN/Inf ⇒ **abort, no fallback**.

**C2 — Data Validator**
- PURPOSE: gate data before any transform.
- INPUT: loaded DataFrame + schema.
- OUTPUT: pass/fail report (gaps classified, ranges, dtypes).
- VALIDATION: gaps classified only as daily-break/weekend/holiday/known; intraday count reported.
- FAILURE: unclassified gap, out-of-grid bar, or schema drift ⇒ **abort**.

**C3 — Time-Series Splitter**
- PURPOSE: leak-free train/val/test + walk-forward with purge & embargo.
- INPUT: index (ordered bars), horizon h, fold spec, purge/embargo lengths.
- OUTPUT: fold iterators (train/val/test index sets) + frozen fold manifest.
- VALIDATION: strict chronology; no train index ≥ test start; purge ≥ h; embargo ≥ h; folds deterministic (seed) and reproducible.
- FAILURE: any overlap across the horizon boundary, or non-deterministic folds ⇒ **abort**.

**C4 — Feature Builder**
- PURPOSE: features from information available at/before bar t only.
- INPUT: price/volume frame up to t; declared feature spec (frozen).
- OUTPUT: feature matrix + feature metadata (name, lookback, warmup).
- VALIDATION: causal check (value at t unchanged if any t'>t is mutated); warmup NaN policy declared; deterministic.
- FAILURE: any dependence on future bars, or any use of the label ⇒ **abort** (leakage).

**C5 — Target Builder**
- PURPOSE: future-only labels.
- INPUT: closes; horizon(s) {1,3,5,10,20}; task (direction/return); threshold rule.
- OUTPUT: labels aligned so bar t's label uses only t+h; class map; balance report.
- VALIDATION: constructed strictly from future info; boundary rows dropped with no imputation; deterministic.
- FAILURE: label touches features, or last h rows back-filled ⇒ **abort**.

**C6 — Preprocessor**
- PURPOSE: fit transforms on TRAIN ONLY.
- INPUT: train feature matrix (+ val/test matrices).
- OUTPUT: fitted transformer artifact + transformed matrices.
- VALIDATION: equality test that val/test do not influence fitted params.
- FAILURE: any global fit, or fit on val/test ⇒ **abort** (scaling leakage).

**C7 — Model Trainer (Classical ML)**
- PURPOSE: train lightweight, declared, non-gridded models.
- INPUT: train (X,y) + frozen hyperparams (single config).
- OUTPUT: fitted model + training metadata.
- VALIDATION: reproducibility (same seed+data ⇒ identical), feature-set frozen, no target leakage.
- FAILURE: non-determinism, unregistered hyperparameter change, or model trained across the test boundary ⇒ **abort**.

**C8 — Evaluator**
- PURPOSE: honest out-of-sample metrics.
- INPUT: fitted model, held-out folds, metric set.
- OUTPUT: metrics (classification + regression), per-fold + aggregate + variance, class balance, calibration.
- VALIDATION: evaluated only on data never seen in training/preprocessing fit.
- FAILURE: accuracy-only reporting, or any test row seen in fit ⇒ **FAIL**.

**C9 — Model Registry** (see §10)
- PURPOSE: full reproducibility of every model.
- INPUT: model + preprocessing + feature/target/split metadata + metrics + seed + code commit + dataset hash.
- OUTPUT: versioned, hash-addressed artifact + manifest entry.
- VALIDATION: reload round-trip reproduces stored metrics bit-for-bit.
- FAILURE: any missing provenance field, or reload mismatch ⇒ **FAIL**.

**C10 — Regime Detector (optional)**
- PURPOSE: label regimes (trend/range/vol-high/vol-low) for conditioning.
- INPUT: causal features only.
- OUTPUT: regime series + stability report.
- VALIDATION: regime labels causal; used only if it measurably improves OOS.
- FAILURE: adds complexity without OOS benefit, or uses future info ⇒ **drop/reject**.

**C11 — Market-Intelligence Ablation Harness (optional)**
- PURPOSE: decide if extra info helps.
- INPUT: nested feature sets A→B→C→D (price / +indicators / +volume / +external).
- OUTPUT: per-ablation OOS comparison.
- VALIDATION: identical splits/costs across arms; no peeking.
- FAILURE: any arm selected on IS profit alone ⇒ **reject**.

**C12 — Backtest Adapter (reuse)**
- PURPOSE: model→signal→simulation with costs.
- INPUT: predictions; entry/exit/SL/TP; costs; sizing.
- OUTPUT: return, DD, PF, expectancy, exposure, trade count.
- VALIDATION: engine equivalence vs `research_harness.harness_backtest`; no future info.
- FAILURE: engine mismatch, or future info in fills ⇒ **abort**.

**C13 — Risk Layer (reuse)**
- PURPOSE: independent limits the model cannot bypass.
- INPUT: signals + account state.
- OUTPUT: sized orders or rejections.
- VALIDATION: adversarial tests (risk=50/max_risk=100 ⇒ ≤ `HARD_RISK_CAP_PERCENT=2.0`); DD kill-switches fail-safe.
- FAILURE: any path exceeding the cap, or model able to bypass ⇒ **CRITICAL FAIL**.

**C14 — Monitoring (optional, later)**
- PURPOSE: detect failure before decisions.
- INPUT: data quality, feature/prediction drift, latency, missing data.
- OUTPUT: alerts/logs (no statistical peeking for decisions).
- VALIDATION: read-only; never influences the single forward evaluation.
- FAILURE: any decision use of interim forward counts ⇒ **violation**.

### Complexity budget (governance binding — reconciled)
The `HYPOTHESIS_GENERATOR_POLICY` caps **MAX_FEATURES=3, MAX_PARAMETERS=4, no
grids (MAX_SEARCH_SPACE=0)**, program variants ≤ 10 (3 consumed → **7 remain**),
and fixes family size **m** up-front. ML does **not** get a multiple-testing
exemption:
- ML-1: a direction hypothesis keeps the strict ≤3-feature, no-grid budget.
- ML-2: an ML hypothesis declares a **frozen** feature set and **one** model
  configuration; feature *selection* happens **inside train folds only** and is
  declared; the OOS look is still **ONE**.
- ML-3: every ML variant consumes a program variant slot (≤7 remain) and enters
  the Bonferroni family **m**.
- ML-4: no hyperparameter search across the OOS; tuning is train/CV-internal.

---

## 7. PHASE / GATE ARCHITECTURE

```
DISCOVER → PLAN → IMPLEMENT → TEST → AUDIT → PASS/FAIL
```
- Roles (skill order): Repository Auditor → [Engineering loop] → [Research loop] → Gate Controller.
- Research loop = Quant Researcher (pre-register) → run (frozen) → Adversarial Validator → Ledger Manager.
- Gate Controller outputs only: `EDGE PROVEN`, `EVIDENCE FAILED`, or `INSUFFICIENT EVIDENCE`.

**Gate rules**
- G-1: PASS requires **evidence artifacts** (tests + hashes + ledger row), never assertion.
- G-2: no Phase auto-advances; each needs explicit human approval.
- G-3: FAIL ⇒ fix only within the current Phase scope, then retest.
- G-4: a consequence clause binds the verdict — no softer path for a FAIL.
- G-5: LIVE is never an agent output (human key only).
- G-6: conflicts ⇒ STOP + report.

---

## 8. REPRODUCIBILITY REQUIREMENTS

Every research run must be reconstructible from: **code commit + dataset identity
hash + frozen config + seed + environment spec + preprocessing artifact**.
- REP-1: no result without a code commit hash and dataset hash.
- REP-2: determinism test (frozen code+data ⇒ identical outputs) required.
- REP-3: environment pinned (lockfile) — currently **missing** on `main` (gap).
- REP-4: all randomness seeded and recorded.
- REP-5: artifacts hash-addressed; reload must reproduce stored metrics.

---

## 9. LEAKAGE CONTROLS

Mandatory checks before any result is trusted:
look-ahead · target leakage · scaling leakage · feature-selection leakage ·
imputation leakage · hyperparameter leakage · label leakage · dataset contamination.

Controls: causal feature tests; fit-on-train-only; purged+embargoed splits;
label constructed post-feature; single OOS look; adversarial (Kilo) review whose
success metric is **finding a flaw**. Existing suspects to re-verify when
touched: forming-bar inclusion in `candle()`; `[-1]`/`[-2]` conventions;
repaint-prone `zigzag`/`nadaraya_watson`; intrabar TP-vs-SL ordering.

**Rule LK-1:** any confirmed leakage is a **FAIL** and invalidates the affected result.

---

## 10. MODEL REGISTRY REQUIREMENTS

Each entry records: **Model ID · Version · Dataset (ID + hash) · Feature set ·
Target · Horizon · Train/Val/Test periods · Preprocessing · Hyperparameters ·
Metrics (per-fold + aggregate) · Seed · Code commit · Timestamp · Status.**

- REG-1: registry is **append-only**; new versions, never overwrite.
- REG-2: load must reproduce stored metrics; mismatch ⇒ FAIL.
- REG-3: a model is `CANDIDATE` until it passes OOS; never `PROVEN` from IS.
- REG-4: registry never claims edge — edge is the Gate Controller's call.
- REG-5: lightweight storage (JSON manifest + joblib artifacts), hash-addressed.

---

## 11. TESTING STRATEGY

Three tiers, **all MT5-free** so they run in the GenSpark sandbox:

1. **Unit** — loader/hash, splitter (purge/embargo determinism), feature causality,
   target causality, preprocessor fit-on-train-only, registry round-trip.
2. **Integration** — full pipeline on **tiny synthetic frozen frames** (no real data),
   including a "leakage canary" that must fail if future data leaks in.
3. **Governance/regression** — determinism, ledger append-only, provenance,
   zero-order-API-call-sites, kill-switch fail-safe.

**Baseline today:** on `main`/sandbox the suite is **RED** (8/8 collection errors:
`MetaTrader5` missing + `forward_collector` absent on `main`). The recorded
`54/54` requires the full environment + `project_audit/`.
**Rule TS-1:** new ML tests must not require MT5. **TS-2:** fix must not weaken
existing tests. **TS-3:** no dependency install without approval (Open Decision F5).

---

## 12. CP-GATE → ROADMAP MAPPING

| New roadmap Phase | Existing governance artifact | Disposition |
|---|---|---|
| 0 Discovery | `codebase_map.md`, `data_flow.md`, `dependency_map.md`, `entry_points.md` | **REUSE** |
| 1 Architecture & Governance | this doc + skill | **DONE (this)** |
| 2 Dataset Pipeline | `DATA_REGISTRY.md`, CP5/CP6/R1 freezes + integrity battery | **REUSE** |
| 3 Feature Engineering | none (ML-new) | **NEW + PRE-REG** |
| 4 Target Generation | none (ML-new) | **NEW + PRE-REG** |
| 5 Time-Series Validation | `research_harness.walk_forward` (rule-based) | **REUSE concept; ML split NEW** |
| 6 Classical ML | none (never existed) | **NEW + PRE-REG** |
| 7 Model Registry | `EXPERIMENT_LEDGER`, `DATA_REGISTRY` | **NEW namespace, references old** |
| 8 Market Regime | `cp5_7_robustness.py` (partial) | **NEW + PRE-REG (optional)** |
| 9 Advanced ML / Ensembles | — | **DEFER until justified** |
| 10 Market Intelligence | CP5.7/CP7 ablation-style | **REUSE harness; NEW + PRE-REG** |
| 11 Backtesting | `hashem_backtest.py`, `harness_backtest` | **REUSE** |
| 12 Strategy Optimization | CP5.7, `Optimizer walkforward.py` | **REUSE (no grids on OOS)** |
| 13 Robustness / Stress | `cp7_stress.py`, CP7 | **REUSE** |
| 14 Paper Trading | CP15/CP16 slots | **REUSE** |
| 15 Monitoring | `monitor_bot.py`, forward collector | **REUSE** |
| 16 Controlled Self-Improvement | R-cycle machinery (R1/R2) | **REUSE pattern** |
| 17 Trading Bot Integration | CP17, `bot_runner.py` | **REUSE** |
| 18 Final Audit | CP18 gate | **REUSE** |
| 19 Human Approval Gate | human key (`FORWARD_START_TIMESTAMP`) | **REUSE** |

---

## 13. HANDLING NO PROVEN EDGE / LIVE DENIED

`NO PROVEN EDGE` and `LIVE DENIED` are **permanent properties of the existing
evidence base**, not obstacles to new, honestly-pre-registered research.

- ND-1: both verdicts stay **unchanged** until new evidence overturns them.
- ND-2: failed baselines remain **locked controls** (`baseline-lock-v1`) forever.
- ND-3: any new hypothesis must **beat the locked controls under the same methodology**.
- ND-4: LIVE remains **DENIED**; only the human can unlock it.
- ND-5: the forward contract stays **DORMANT** (one evaluation at ≥300 events or ≥180 days).

---

## 14. FUTURE ML RESEARCH WITHOUT INVALIDATING PRIOR GOVERNANCE

Mechanism (structural, not verbal):
- IM-1: prior research (CP0–CP23, ledger, tags) is **immutable** and never re-derived.
- IM-2: ML work lives in a **separate namespace** `project_audit/ml/` that
  **references** the existing ledger by ID.
- IM-3: each ML hypothesis is a **new pre-registered contract** (new ID) citing
  dataset hashes and consuming either the **unseen reserve** (once) or the
  **forward stream** — **never** burned periods for confirmatory claims.
- IM-4: ML features/models obey the **same** statistical discipline (single OOS
  look; Bonferroni family `m`; consequence clause) and the variant budget (≤7).
- IM-5: engineering (registry, loaders) is recorded as **engineering loops**,
  separate from research experiments.
- IM-6: the Gate Controller, not the ML pipeline, issues any edge verdict.

---

## A. PHASE 1 ARCHITECTURE
Modular, lightweight, sklearn-first research system with a hard boundary between
**Research** (MT5-free, frozen data, hash-verified) and **Live** (single guarded
entry point `bot_runner.py`). Fourteen components defined with contracts (§6):
C1 loader · C2 validator · C3 TS splitter (purge/embargo/WF) · C4 features ·
C5 targets · C6 preprocessor (train-only) · C7 trainer (classical ML) ·
C8 evaluator · C9 registry · C10 regime (opt) · C11 ablation (opt) ·
C12 backtest adapter (reuse) · C13 risk layer (reuse) · C14 monitoring (opt).
Data-flow and failure conditions are explicit; complexity is budgeted.

## B. GOVERNANCE RULES
SOT-1..3 · BR-1..3 · GOV-1..4 · DS-1..6 · RS-1..3 · G-1..6 · REP-1..5 ·
LK-1 · REG-1..5 · TS-1..3 · ND-1..5 · IM-1..6 (plus the skill's six
non-negotiables and C1–C14 failure conditions).

## C. PHASE/GATE MAP
`DISCOVER → PLAN → IMPLEMENT → TEST → AUDIT → PASS/FAIL`; role pipeline
Auditor → Engineering/Research loop → Gate Controller; CP-gate mapping in §12.
No auto-advance; PASS needs evidence; FAIL stays in-phase; LIVE is human-only.

## D. ML ROADMAP
Baselines (Logistic/Linear) → Classical (Tree, RF, ExtraTrees, GB, HistGB) →
optional (XGBoost/LightGBM/CatBoost) → ensembles; **Advanced ML (MLP/CNN/TCN/
LSTM/GRU/Transformer) DEFERRED** until classical ML is validated and a real
limitation + sufficient data + acceptable compute are demonstrated. Regimes and
Market-Intelligence ablation are **optional and evidence-gated**. Lightweight,
low-memory first (limited hardware).

## E. RESEARCH DATA POLICY
Frozen-by-hash; no re-fetch; burned periods excluded from confirmatory claims;
unseen reserve consumed once; forward stream = cleanest future OOS; naive broker
time; spread/slippage gate before any DEMO claim; every run cites dataset hash.

## F. OPEN DECISIONS (require owner approval before Phase 2)
- **F1 — Resolve source-of-truth conflict.** What is `ketabtallaee-backup` /
  commit `2d7cf9c5`? Push it to GitHub or declare it non-canonical.
- **F2 — Declare trunk + govern the restore.** Approve `main` as governance-bearing
  trunk and a one-time append-only restore of `project_audit/` + data manifests
  from `code-refactoring-guide-41a87` (history preserved, no deletion).
- **F3 — Approve the ML namespace** `project_audit/ml/` and new hypothesis ID scheme.
- **F4 — Approve the ML complexity budget** (reconcile ≤3 features / no grids with ML feature sets).
- **F5 — Approve the environment plan** (MT5-free research env; which deps) — **no install yet**.
- **F6 — Choose the first ML hypothesis family** and which unseen reserve it consumes (or defer).
- **F7 — Confirm the forward contract stays dormant and untouched.**
- **F8 — Confirm Research/Live separation** and `bot_runner.py` as sole live entry.

## G. PHASE 1 PASS/FAIL
```
PHASE 1 = PASS (design deliverable complete)
Evidence: this architecture+governance document; conflicts documented (F1);
          CP-gate map (§12); data policy (§4); tests policy (§11).
Condition: Phase 2 REMAINS BLOCKED until F1 and F2 are decided (owner approval),
           and F4/F5 before any ML implementation.
No trading logic touched. No model trained. No backtest run. No data collected.
No dependency installed. No order sent. No burned data consumed.
---
STOP — awaiting explicit approval before Phase 2.
```
