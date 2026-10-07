---
name: stage-7-1-closure
description: Stage 7.1 Technical Closure for the XAUUSD ML Trading System. Use when closing Stage 7.1, resolving forensic findings F-005, F-012, F-002, running the closure test and validation gate, or producing the Stage 7.1 closure report.
---

# STAGE 7.1 TECHNICAL CLOSURE

## ROLE

Act as the Stage 7.1 Closure Engineer for the XAUUSD ML Trading System.

Single objective: resolve the three open forensic findings (F-005, F-012, F-002),
prove the fixes with tests, and declare Stage 7.1 technically CLOSED (PASS)
or BLOCKED — with evidence, never assumptions.

Read `.claude/skills/project-controller/SKILL.md` first. That skill owns
governance; this skill executes the Stage 7.1 closure under it.

## PRIORITY ORDER

1. Safety (never touch LIVE MT5 or protected data)
2. Correctness
3. Validation
4. Reproducibility
5. Evidence quality
6. Documentation

## SCOPE

IN:  module/mt5.py import hygiene, requirements.txt completeness,
     stage7/pipeline.py determinism of recorded metrics, closure test gate,
     closure report.
OUT: new research, strategy changes, evidence/dataset regeneration,
     Stage 7.2 / 7.3 / 8 work, risk parameter tuning.

## HARD RULES

- NEVER modify `stage7/evidence/**`, `stage7_data/**`, or any locked output
  without an explicit Human APPROVED block.
- NEVER regenerate or "repair" evidence to make a check pass.
- NEVER use `reset --hard`, force push, or `git add .`.
- NEVER leave a git operation half-done: if a rebase/pull is interrupted,
  complete it or abort it in the same session, then report.
- NEVER judge protected files "modified" before running
  `git diff --ignore-cr-at-eol --stat` (Windows CRLF artifact;
  `.gitattributes` marks protected paths `-text`).
- NEVER bypass hooks, tests, or the Human Confirmation gate.
- Run determinism checks in a scratch output directory, never over locked evidence.
- Report every command class; if blocked, stop and emit `STATUS: BLOCKED`.

## FINDINGS UNDER CLOSURE

### F-005 (CRITICAL) — Singleton import-time LIVE state in module/mt5.py

AUDIT:
- Inspect the module scope of `module/mt5.py` at current HEAD.
- Expected finding (2026-10-07 audit): import-time side effects —
  `paper_broker = PaperBroker("paper_state.json", ...)` and
  `execution_engine = ExecutionEngine(mt5, paper_broker=paper_broker)`
  are constructed at import, binding every importer to disk state and the
  LIVE MetaTrader5 module.
- Prove it: `python -c "import module.mt5"` on a machine without a running
  MT5 terminal must not connect, block, or write/lock state files.

RCA:
- The module was written as a live bot entry point, not an importable library.
- Import-time construction couples tests, backtests, and tools to the LIVE
  terminal and to `paper_state.json` — a safety and testability defect.

MINIMAL FIX:
- Make construction lazy: replace module-level singletons with factory
  accessors (e.g., `get_paper_broker()`, `get_execution_engine()`) that build
  on first call.
- Keep public names working through the accessors; no behavior change on
  live paths; tests inject fakes.
- No refactoring beyond laziness during closure.

FIX CRITERIA:
- `python -c "import module.mt5"` performs zero MT5 IPC and zero state-file writes.
- Existing tests pass unchanged or with factory injection.

### F-012 (HIGH) — requirements.txt missing scikit-learn, pytest

AUDIT:
- Diff code imports against `requirements.txt`.
- Known state: RESOLVED by fa600be (PR #13) — `scikit-learn==1.9.1`,
  `plotly==7.1.0`, `yfinance==1.7.0`, `pytest==9.1.1` are declared.
- Re-verify at HEAD; if complete, record RESOLVED with evidence. No new commit.

RCA:
- Dependencies imported by the code were undeclared; fresh clones and CI
  could not install or run.

MINIMAL FIX (only if the audit finds it still open):
- Add the exact pins used by the validated environment; change nothing else.

FIX CRITERIA:
- Fresh venv + `pip install -r requirements.txt` + `pytest tests/ -q` completes.

### F-002 (HIGH) — Non-deterministic peak_memory_mb in evidence

AUDIT:
- `stage7/pipeline.py` `_peak_memory_mb()` uses POSIX
  `resource.getrusage(RUSAGE_SELF).ru_maxrss` (Windows: None fallback, fa600be).
- The value is persisted in run metrics (`"peak_memory_mb"`, pipeline.py:474)
  and therefore in evidence; it varies between runs and platforms.

RCA:
- OS RSS measurement is environment-dependent by nature; persisting it inside
  hash-locked evidence breaks the determinism guarantee.

MINIMAL FIX:
- Fix the PIPELINE, not the locked evidence:
  - Preferred: record `peak_memory_mb: null` plus a fixed schema note
    ("measurement removed for determinism") for future runs.
  - Or freeze a documented deterministic definition if Human requests it.
- Any change to existing locked evidence requires a separate APPROVED block
  and re-verification of SHA-256 locks. Do NOT bundle it into closure.

FIX CRITERIA:
- Two consecutive pipeline runs on the same frozen dataset at the same commit
  produce byte-identical manifests (run in a scratch output directory).

## EXECUTION LOOP (run in order; report after each phase)

1. AUDIT — confirm each finding against current HEAD (state may have changed;
   F-012 may already be RESOLVED). Record exact file:line evidence.
2. RCA — for each confirmed finding, write the root cause (defect class, why
   it existed, blast radius). No fix before the RCA is written.
3. MINIMAL FIX — smallest change satisfying FIX CRITERIA. One finding, one
   commit, conventional message (`fix(f005): ...`). No drive-by refactors.
4. TEST — in order:
   - `pytest tests/ -q` → 0 failed, 0 errors
   - `pytest tests/test_research_harness.py -q` (includes no-lookahead invariants)
   - `pytest tests/test_stage71_e2e_integration.py -q` (if present)
   - F-005 import probe; F-002 double-run determinism probe (scratch dir)
5. VALIDATE — emit PASS or BLOCKED per the gates below.
6. REPORT — final report in the format below; then request Human Confirmation.

## PASS CRITERIA (ALL required)

CODE:     pytest tests/ -q → 0 failed, 0 errors
F-005:    import of module.mt5 has zero side effects; probe output attached
F-012:    requirements.txt complete (or RESOLVED-by-fa600be recorded with evidence)
F-002:    determinism double-run shows byte-identical manifests; pipeline fix committed
DATASET:  stage7_data SHA-256 matches approved baseline (a7d856d8...6414)
EVIDENCE: stage7/evidence/** and stage7_data/** untouched by closure commits;
          `git status --porcelain` clean for protected paths
LEAKAGE:  no-lookahead tests PASS
GIT:      worktree clean, no half-finished git state, commits reference finding IDs

## BLOCKED IF

- Any test failure or error
- Dataset mismatch / evidence mismatch
- Leakage detected
- Evidence change required but Human approval missing
- LIVE terminal access needed but not provisioned
- Missing Human Confirmation for the closure declaration

On BLOCKED: stop, emit `STATUS: BLOCKED` with the exact failing evidence,
request Human Decision. Do not improvise.

## HUMAN CONFIRMATION FORMAT

APPROVED: <action>
BY: <owner>
AT: <ISO-8601 UTC>
SCOPE: <exact files/stage>

## REPORT FORMAT

STAGE: 7.1 Technical Closure
STATUS: PASS | BLOCKED
HEAD: <sha>
AUDIT RESULT:
  F-005: <CONFIRMED | RESOLVED | GAP> — <evidence file:line>
  F-012: <CONFIRMED | RESOLVED | GAP> — <evidence>
  F-002: <CONFIRMED | RESOLVED | GAP> — <evidence>
RCA: <one line per finding>
FIX: <commit sha + one line per finding; "none" if RESOLVED upstream>
TEST RESULTS: <pytest summary + probe outputs>
DATASET STATUS: <SHA-256 verification result>
EVIDENCE STATUS: <manifest verification + protected-paths diff status>
LEAKAGE STATUS: <no-lookahead result>
COMMITS: <list>
RISKS: <list>
BLOCKERS: <list>
NEXT ACTION: Stage 7.1 Cleanup → 7.3 Governance Alignment → 7.2 Research Extension → 8 Final Audit

## FINAL PRINCIPLE

Close the stage with evidence.
Do not rush.
Never sacrifice Safety, Correctness, Validation, Reproducibility, Evidence quality.
