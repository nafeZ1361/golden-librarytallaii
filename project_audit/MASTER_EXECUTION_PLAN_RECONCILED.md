# MASTER EXECUTION PLAN — Reconciled with Repository Governance

Status: **PLANNING ARTIFACT — NON-EXECUTING. NO SOURCE MODIFIED.**
Date: 2026-09-20 | Repo: `nafeZ1361/golden-librarytallaii`
Supersedes nothing; **reconciles** the provided Master Execution Plan (Phases 1–17)
with the binding governance already on record in this repository.

> This document adds **no** new experiment, dataset, result, or performance claim.
> It is a scope/governance map. Every factual line is traceable to
> `project_audit/PHASE1_PROJECT_BASELINE.md` or to governance artifacts on
> `origin/code-refactoring-guide-41a87`.

---

## 0. The one thing that must be understood first

The Master Plan is a **sound generic ML research framework**. But this repository
is **not greenfield**. It already carries a completed, audited research program
whose recorded verdict is:

```
RESEARCH : NO PROVEN EDGE   (A1-h5: 55.60% IS -> 49.29% OOS = FAILED REPLICATION)
SAFETY   : PASS             (engineering; 54/54 regression; sole entry point bot_runner.py)
LIVE     : DENIED           (CP18; no order may be placed on this evidence base)
FORWARD  : 1 dormant pre-registered contract (first-breakout fade, h5)
DATA     : in-sample window 2021-06 -> 2026-09-04 fully BURNED across 3 datasets; look budget m=4 spent
```

The repo's binding skill (`.agents/skills/research-governance/SKILL.md`) declares
its prime directive: this agent is an **evidence factory expected to retire
hypotheses**, *not* a profit/win-rate maximizer. "Optimizing for PnL is exactly
the causal chain that has already destroyed every hypothesis."

Therefore: **the plan's phase order and gates are adopted; the plan's implicit
assumption of a fresh, unburned dataset is not.** Any Phase that would *measure*
on burned data is converted into either (a) a **reuse** of an existing gate, or
(b) a **new pre-registration** with an explicit consequence clause.

---

## 1. Non-negotiable constraints (adopted verbatim, plus repo additions)

Adopted from the plan §2: no Live Trading, no Order Execution, no MT5 in the ML
layer, no future data in features, no leakage, no random split, no scope creep,
no deep learning without a separately approved phase, no auto-start of the next
phase, no unnecessary deletion/rewrite, no unvetted dependency, every change
small/traceable/testable.

**Repo additions (binding, from the research-governance skill):**
- **N1 Pre-register before data contact.** New hypothesis ⇒ write hypothesis,
  params, dataset version, acceptance criteria, and a **consequence clause**
  into `project_audit/CP*_PRE_REGISTRATION.md` *before* running anything on new data.
- **N2 Freeze, then validate.** Frozen code + hash-manifested frozen data; no
  change between IS and OOS measurement.
- **N3 Append-only records.** `EXPERIMENT_LEDGER.{json,md}` and the forward event
  ledger are never edited/deleted; corrections are new rows.
- **N4 Consequence clauses bind the Gate Controller.** No softer path for a FAIL.
- **N5 No fabrication.** If MT5/network/data is unavailable → record failure and stop.
- **N6 Human-only LIVE key.** Agent gates may output DENIED or RECOMMEND, never LIVE.

---

## 2. Agent roles (as given) mapped to repo reality

The plan names four agents. The repo's own skill notes: *"One model plays all
roles, so persona separation alone is theater. Independence comes from
structure."* The plan is consistent with this — keep the role order, but enforce
**structural** separation (frozen artifacts, hash manifests, append-only ledger)
so the roles are not merely labels.

```
Cline  (PM / Architect / Gate Controller)  -> sets scope; final approval; may output DENIED/RECOMMEND only
OpenCode (Senior Python/ML Engineer)       -> implements; auto-fix ONLY within the current phase scope
Kilo   (Independent QA / Leakage Reviewer) -> adversarial; its success metric is FINDING A FLAW
Ollama (Lightweight Reviewer)              -> style/logic/consistency; low resource
Order per phase: Cline -> OpenCode -> Kilo -> Ollama -> Cline Final Approval
```

---

## 3. Phase-by-phase disposition (what to do, given the repo)

Legend: **REUSE** = use existing governance artifact, don't duplicate ·
**NEW-REG** = requires new pre-registration · **BLOCKED** = needs Cline decision.

| # | Plan Phase | Disposition | Concrete action / existing artifact |
|---|---|---|---|
| 1 | Project Baseline | **DONE** | `project_audit/PHASE1_PROJECT_BASELINE.md` (this session). Existing analogues: `codebase_map.md`, `data_flow.md`, `dependency_map.md`, `entry_points.md`, `trading_safety_audit.md`. |
| 2 | Dataset Pipeline | **REUSE + BLOCKED** | Frozen datasets already exist + validated (CP5/CP6/R1; dataset identity `be4fa581…`). Re-fetching is forbidden (N5). Decision §4-Q3. |
| 3 | Feature Engineering | **NEW (no artifact exists)** | No ML feature code on `main`. If built, must be leakage-free and tested — and may **not** be evaluated for edge on burned data without a new pre-registration. |
| 4 | Target / Label | **NEW** | No target code exists. Same caveat. |
| 5 | Time-Series Validation | **REUSE (rule-based) + NEW (ML)** | `research_harness.walk_forward` is rule-based (not ML). An ML purged/embargoed split is new and must be leakage-reviewed by Kilo. |
| 6 | ML Training & Registry | **NEW + BLOCKED** | **Never existed.** A model registry is net-new infrastructure. Decision §4-Q2/Q5. |
| 7 | Model Evaluation | **REUSE** | Existing: CP6 OOS replication, `cp5_statistical_validation.py` (HAC+MBB+Bonferroni), CP7 stress. |
| 8 | Walk-Forward Eval | **REUSE + NEW** | Existing CP4 WFO (rule-based); per-fold ML preprocessing fit-on-train-only is new. |
| 9 | Backtesting | **REUSE** | `backtest/hashem_backtest.py` + `research_harness.harness_backtest` (equivalence-proven). Must not use future info. |
| 10 | Robustness | **REUSE** | `cp5_7_robustness.py`, `cp7_stress.py`. |
| 11 | Risk Management | **REUSE** | CP11 `CP11_RISK_VALIDATION.md`; live risk caps `HARD_RISK_CAP_PERCENT=2.0`, DD kill-switches in `bot_runner.py`. Risk layer must stay independent of the model. |
| 12 | Market Data / Fundamental / News | **NEW-REG** | No such ingestion in ML path. Any source needs timestamp/source/latency/historical-availability metadata; no retro-injection (point-in-time correctness). |
| 13 | MCP Integration | **BLOCKED** | `config/mcporter.json` exists; **no MCP may drive model training** (plan §13). Keep MCP → Adapter → Validation → Dataset/Feature → Model. |
| 14 | Paper Trading | **REUSE** | CP15/CP16 slots + forward-monitoring contract (DORMANT). Uses same registry + risk layer + full logging. |
| 15 | Monitoring / Observability | **NEW + REUSE** | `module/monitor_bot.py` (read-only) + forward collector integrity/tamper-hash. |
| 16 | Final System Validation | **REUSE** | CP18-style gate document; nothing undocumented/untested may remain. |
| 17 | Live Trading Review | **REUSE — REVIEW ONLY** | CP18 gate = DENIED. LIVE requires the **human's** `FORWARD_START_TIMESTAMP` key (N6). |

---

## 4. Blocking scope decisions (Cline) — mirror of baseline §6

1. **Source of truth / branch.** Restore `project_audit/` + frozen datasets onto
   `main`, or run everything on `code-refactoring-guide-41a87`? (R2/R3)
2. **ML restart vs burned-line extension.** Is this a **new** ML program (needs
   pre-registration beating `baseline-lock-v1` under the same methodology) or an
   extension of a RETIRED line? (R1/R7)
3. **Authoritative dataset for Phases 2–5.** Confirm reuse of the frozen CSVs; MT5
   is unavailable in this environment and re-fetch is forbidden. (R3/R5/N5)
4. **Gate mapping.** Map Phases 9–17 onto CP10/CP11/CP16/CP17/CP18 + forward
   contract; do not build parallel unaudited machinery. (R12)
5. **Meaning of "PASS" for Phases 3–5.** No artifact on `main` supports those
   statuses; re-implement+retest, or correct the status column. (R7)

**Until these are answered, Phase 2+ is BLOCKED.** No agent may auto-start a phase.

---

## 5. Gate protocol (adopted, with repo enforcement)

For every phase: Cline defines scope → OpenCode implements (scope-limited
auto-fix) → tests run → Kilo adversarially reviews (must try to kill it) →
Ollama lightweight review → Cline final approval. On any failure/blocker: **stop
at that phase**, fix only within that phase's scope, then re-run
tests → Kilo → Ollama → Cline. Next phase without final approval is forbidden.

**Repo enforcement hooks:**
- Every ledger row carries code version + dataset version (N2/N3).
- Engineering loops are recorded separately from research experiments.
- A FAIL follows its pre-registered consequence clause (N4) — no invented path.
- `LIVE` is never an agent output (N6).

---

## 6. Final principle (unchanged, restated)

The goal is **not** a high-accuracy model. It is a system that is
**reliable, reproducible, leakage-safe, time-series correct, testable,
observable, risk-controlled, and modular** — in which every positive ML result
is confirmable on data outside training by a repeatable process. No backtest or
ML result alone guarantees future performance. In this repository, the honest
status today is **NO PROVEN EDGE / LIVE DENIED**, and it stays that way until
evidence — not enthusiasm — changes it.
