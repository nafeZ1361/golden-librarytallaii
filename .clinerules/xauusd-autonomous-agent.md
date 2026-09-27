# XAUUSD Autonomous Local Agent

## Mission
Execute the XAUUSD ML / Trading System locally from the VS Code workspace. The local agent is the terminal executor; GitHub is the source of truth.

## Execution loop
AUDIT -> FIX -> TEST -> VALIDATE -> PASS/BLOCKED -> NEXT STAGE

Run commands yourself in the project terminal and read their complete output. Do not ask the user to copy/paste routine commands or test output.

## Autonomous progression
After a stage reaches PASS with reproducible evidence, continue to the next stage automatically. Stop only for:
- BLOCKED environment or missing evidence
- destructive or irreversible action not explicitly authorized
- live-trading/order execution risk
- data loss risk
- credentials/secrets
- a requirement conflict

## Safety
- Research/backtest/paper/demo only.
- Never execute live orders or MT5 order APIs such as order_send.
- Never use git reset --hard, git clean -fd, broad deletion, or destructive cleanup.
- Never claim PASS without actual command output/artifacts.
- Inspect before editing; smallest justified change.
- Preserve working architecture; NO REBUILD.
- Do not optimize parameters before correctness validation.
- Keep ML independent of MetaTrader5.
- Do not silently modify protected PASS phases without concrete evidence.
- Never use git add . or git commit -a.
- Stage commits must be narrow and reviewable.

## Required evidence
For each stage record:
- branch and commit SHA
- commands actually executed
- exact test counts/results
- artifacts and hashes
- chronology/leakage/holdout validation
- changed files and diff summary
- PASS or BLOCKED reason

## Environment
Prefer the existing project .venv. If requirements.txt pins a missing dependency, install only the required pinned dependency into the active .venv, then verify its exact version before continuing.

## Git
Before work:
- git status --short
- git branch --show-current
- git log -1 --oneline

After work:
- git diff --check
- targeted tests
- relevant broader tests
- git status --short
- record commit SHA

Never hide untracked files. Never delete user files just to obtain a clean tree.
