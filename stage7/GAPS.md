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
