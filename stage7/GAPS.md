# Stage 7 GAP Registry

Registered open and resolved gaps for the XAUUSD research system, governed by
AGENTS.md (AUDIT → FIX → TEST → VALIDATE → PASS → HUMAN CONFIRMATION).

Human Confirmation: APPROVED Decisions 8-A / 9-B / 10-A
BY: nafeZ1361
AT: 2026-10-08T10:55:27Z
SCOPE: stage7/GAPS.md (new), module/execution.py:53, module/config.py (docs only)

## GAP-001 — F-006: split_manifest.json record mismatch — OPEN

- Severity: MEDIUM
- Finding source: `.claude/skills/project-controller/SKILL.md` (KNOWN BLOCKERS)
- Affected artifacts: `stage7/evidence/run1/split_manifest.json` and
  `stage7/evidence/run2/split_manifest.json`
  (sha256 `435c12cd98d287ca0c8e16d9f1ca1ec8467a8e78cc3f1e7f9e616b4628e3cba4`,
  recorded in both `run_manifest.json` files)
- Generator: `stage7/pipeline.py` `split_manifest` record (written at
  `stage7/pipeline.py:551`)
- Decision: 8-A — document as GAP only; **no code change** on this branch.
- Status: **OPEN**
- Constraint: locked run1/run2 evidence is intentionally untouched; remediation
  requires a dedicated audited stage with fresh Human Confirmation.

## GAP-002 — F-004: Risk config duality — RESOLVED

- Severity: MEDIUM
- Finding: risk limits had two sources of truth — the hardcoded
  `RiskLimits(max_volume=1.0)` fallback in `module/execution.py:53` versus the
  `RiskLimits.from_env()` RISK_* environment contract used by `main.py:94`.
- Resolution (Decision 9-B, branch `fix/stage73-f004-riskconfig`):
  - `module/execution.py:53` default validator is now
    `RiskValidator(RiskLimits.from_env())` (fail-safe defaults).
  - The RISK_* contract is documented in `module/config.py` as the single
  source of truth (docs/comment only; no forced refactor).
  - `main.py` unchanged (already correct).
  - `module/execution.py:44` and `:52` (`TRADING_MODE`, `ENABLE_LIVE_TRADING`)
    intentionally unchanged: their construction-time env reads are load-bearing
    for the test suite (patch.dict mode tests) and are execution-mode gating,
    not risk config.
- Fix commit: `222b76b3d4656b6d14f64633b9d6c931f7b3d409`
  (`fix(f004): construct default risk validator via RiskLimits.from_env()`)
- Status: **RESOLVED** (pending full-suite re-validation and separate Human
  Confirmation to merge)

## GAP-003 — Time-of-Day regime — OPEN (RESEARCH GAP)

- Type: RESEARCH GAP
- Target stage: Stage 7.2/8
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-004 — ATR/Volatility regime — OPEN (RESEARCH GAP)

- Type: RESEARCH GAP
- Target stage: Stage 8
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-005 — Monte Carlo trade-sequence — OPEN (VALIDATION GAP)

- Type: VALIDATION GAP
- Target stage: Stage 8
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-006 — Parameter landscape — OPEN (VALIDATION GAP)

- Type: VALIDATION GAP
- Target stage: Stage 8
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-007 — Slippage/execution friction — OPEN (VALIDATION GAP, HIGH PRIORITY)

- Type: VALIDATION GAP
- Priority: HIGH — Stage 8, before any filter work
- Rationale: Stage 7.1 post-cost result is negative; validate friction first.
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-008 — OFI/Depth Skew — OPEN (RESEARCH CANDIDATE)

- Type: RESEARCH CANDIDATE
- Target stage: Stage 7.2
- Dependency: L2/L3 data
- Implementation: none ("no impl")
- Status: **OPEN**

## GAP-009 — heikin_ashi().obj mismatch — OPEN (PRE-EXISTING)

- Severity: MEDIUM
- Type: CODE MISMATCH — RESOLUTION GAP
- Finding: `module/indicators.py:1061` accesses `.obj` on the DataFrame returned by `heikin_ashi(...)`.
- Classification: PRE-EXISTING; not introduced by PR #14.
- Scope: OUT OF SCOPE for PR #14.
- Decision: DEFER; no change to `module/indicators.py` in this governance action.
- Status: **OPEN**
- Constraint: no indicator fix until separately audited and explicitly approved.

## GAP-010 — missing ml_signal_adapter — OPEN (PRE-EXISTING / HIGHLY LIKELY)

- Severity: HIGH
- Type: REPOSITORY/TEST INTEGRITY GAP
- Finding: `tests/test_stage71_e2e_integration.py` imports `ml_signal_adapter`, but no tracked module was found.
- Classification: PRE-EXISTING / HIGHLY LIKELY; PR #14 did not modify the test or adapter.
- Historical deletion: NOT PROVEN.
- Scope: OUT OF SCOPE for current governance action.
- Decision: DEFER; do not create `ml_signal_adapter.py`, modify tests, or install a dependency.
- Status: **OPEN**
- Constraint: root cause requires separate forensic investigation before remediation.

## GAP-011 — PROJECT_STATE governance/document drift — OPEN

- Severity: MEDIUM
- Type: GOVERNANCE/DOCUMENTATION DRIFT
- Finding: `PROJECT_STATE.md` records `Current HEAD (main): 4448ff0`, while the audited current main is `36df7c9`; it also states Stage 7.1 Technical Closure is approved although the PR #14 merge gate and required validation are still open.
- Decision: reconcile `PROJECT_STATE.md` using verified repository state only; no code/data/evidence changes.
- Status: **OPEN** until reconciliation is validated.

## GAP-012 — PR #14 branch/integration drift — OPEN (ASSESSMENT PENDING)

- Severity: MEDIUM
- Type: BRANCH/INTEGRATION DRIFT
- Finding: current main is `36df7c9`; PR #14 head is `8f8939c`; PR #14 base/merge-base is `d1597ef`; compare shows PR #14 is 2 commits ahead and 14 commits behind main.
- Classification: real branch divergence; semantic conflict or required rebase is NOT YET established.
- Decision: do not rebase or merge until a fresh PR #14 audit and explicit Human Confirmation.
- Status: **OPEN / ASSESSMENT PENDING**
