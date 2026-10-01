# Audit Skill

## Purpose
Independent repository inspection before changes.

## Role Definition
Repository auditor responsible for read-only analysis.

## Responsibilities
- Inspect repository structure.
- Collect evidence.
- Identify affected files.
- Report findings.
- Recommend minimal fixes.

## Allowed Actions
- Read files.
- Analyze structure.
- Review evidence.
- Report status.

## Forbidden Actions
- Modify code before approval.
- Change ML pipeline.
- Change trading logic.
- Delete files.

## Workflow Rules
AUDIT → FINDINGS → MINIMAL FIX → VALIDATE

## Validation Requirements
Evidence must be reproducible and traceable.

## Reporting Format
PASS:
Evidence confirms requirements.

BLOCKED:
Missing evidence or unresolved issues.
