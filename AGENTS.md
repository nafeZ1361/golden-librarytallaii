# XAUUSD ML / Trading System — Agent Operating Contract

## Mission
Work on this repository as a research/backtesting engineering system for XAUUSD. Strictly research, backtest, paper/demo only. Never place real orders.

## Mandatory workflow
AUDIT → FIX → TEST → VALIDATE → PASS → HUMAN CONFIRMATION → NEXT STAGE

Never advance a stage automatically. A stage is PASS only with reproducible evidence.

## Non-negotiable rules
- NO REBUILD: preserve working architecture and reuse existing modules.
- Audit before changing code.
- Make the smallest justified change.
- Never use broad deletion, reset, or cleanup to hide problems.
- Never use git reset --hard, git clean -fd, git add ., or git commit -a for project changes.
- Never claim PASS without actual test/evidence output.
- Do not invent missing dates, data, metrics, artifacts, or test results.
- Keep ML independent of MetaTrader5.
- MT5 may be a historical data acquisition source; no live trading or order execution.
- Protect PASS phases; modify them only for a concrete verified defect.
- Before changing a file, inspect its implementation and tests.
- Prefer existing healthy compatible code over replacement.
- Keep changes reviewable and narrowly scoped.

## Stage gate
For every stage report objective, files inspected, files changed, tests executed with exact counts, validation evidence, blockers, commit SHA, and PASS/BLOCKED status.

## ML safety
Prevent train/validation/test leakage. Preserve chronological ordering. Respect purge/embargo. Do not use future information for features or execution decisions. Holdout/OOS boundaries must be explicit and reproducible. Model artifacts require deterministic metadata and registry identity.

## Backtest safety
Reuse the existing backtest engine. Separate signal generation from execution simulation. Make execution timing explicit. Historical replay must be deterministic. No live order APIs. Do not optimize parameters before correctness passes.

## Evidence
Prefer machine-checkable JSON/MD artifacts containing dataset identity/hash, model identity, feature/version identity, time window, assumptions, tests, and reproducibility metadata.

## Agent behavior
Read the relevant skill before specialized work. Do not load unrelated skills. If requirements conflict or evidence is missing, stop at BLOCKED and report the exact missing evidence.
