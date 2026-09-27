# Local Agent Setup

## Purpose
The repository is prepared for a VS Code local agent to execute terminal commands and read their output without requiring the user to relay routine PowerShell results.

## Recommended architecture
VS Code + Cline/OpenCode -> project PowerShell terminal -> .venv/Python -> tests/backtest -> evidence -> GitHub.

## Important limitation
Repository files can configure the agent, but they cannot grant ChatGPT direct access to a user's Windows terminal. The local agent must be installed/running in VS Code and granted terminal/workspace permissions.

## First launch
Open this repository in VS Code and run the local agent from the repository root. The agent must read:
1. AGENTS.md
2. .clinerules/xauusd-autonomous-agent.md
3. the current stage-specific skill

Then execute the stage itself in the terminal and read outputs directly.

## Current project stage
Stage 7.1 Final Audit.

## Current known environment blocker
The project .venv previously lacked numpy and scikit-learn. requirements.txt pins:
- numpy==2.2.6
- pandas==2.3.3
- scikit-learn==1.5.2

The agent should verify the live environment rather than trust this note, install only missing pinned dependencies, and rerun the affected tests.

## Never
- claim PASS without actual execution
- ask the user to paste routine test output
- run live trading or order execution
- reset/clean the repository destructively
- delete untracked user files
