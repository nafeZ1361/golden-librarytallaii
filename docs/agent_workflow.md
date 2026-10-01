# Agent Workflow Governance

## Project

XAUUSD ML Trading System

## Purpose

Define controlled collaboration between AI agents while protecting the existing ML pipeline, Stage 7.1 evidence system, datasets, and trading logic.

## Agent Roles

### Cline
Project leader and system architect.

Responsibilities:
- Manage workflow.
- Review architecture decisions.
- Coordinate agents.
- Confirm PASS/BLOCKED decisions.

### OpenCode

ML and Python implementation agent.

Responsibilities:
- Implement approved code changes.
- Perform limited refactoring.
- Add technical tests.
- Preserve existing contracts.

### Kilo

Independent QA reviewer.

Responsibilities:
- Review leakage risks.
- Validate backtests.
- Find hidden defects.
- Perform independent checks.

### Ollama (Qwen3 1.7B)

Lightweight reviewer.

Responsibilities:
- Quick review.
- Second analysis.
- Low-resource validation support.

## Workflow

AUDIT
→ FIX
→ TEST
→ VALIDATE
→ PASS
→ HUMAN CONFIRMATION
→ NEXT STAGE

## Evidence Requirements

Every stage transition requires:

- Reproducible evidence.
- Hash verification where required.
- Test results.
- Validation report.
- Human confirmation.

## Change Control

Rules:

- Audit before modification.
- Minimal changes only.
- No direct main changes without validation.
- Use separate branches.
- Review diff before commit.

## Research Separation

Research modules must:

- Remain separate from production pipeline.
- Have independent evidence.
- Pass leakage and validation checks before integration.

## Validation Gates

PASS requires:

- Tests completed.
- Evidence verified.
- No unresolved blockers.

BLOCKED requires:

- Findings documented.
- Next action defined.
