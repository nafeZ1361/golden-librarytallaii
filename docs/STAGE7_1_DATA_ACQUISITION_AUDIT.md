# Stage 7.1 Data Acquisition Architecture Audit

## Verified repository facts
- DATA_FLOW.md specifies MT5 M1 bars as the canonical source and local resampling.
- Phase 6 dataset validation is independent of MT5 access.
- The repository declares MetaTrader5 and pandas dependencies.
- Raw XAUUSD historical data is absent from the repository.
- The current backtest layer contains direct MT5 initialization and should remain outside the ML layer.

## Gap
The Qwen Linux environment cannot access the Windows MT5 terminal. A GitHub-hosted runner is not the user's broker-connected MT5 terminal.

## Controlled solution
Use a repository-level Windows x64 self-hosted GitHub Actions runner on the same Windows machine that has MT5. The workflow is manual-only and performs data acquisition, not trading.

## Safety
- No order/trade API is called.
- No credentials are stored in GitHub.
- Raw data is not committed to Git.
- Metadata records symbol, M1 timeframe, UTC timestamps, row count and SHA-256.
- Workflow does not run automatically.

## Gate
This branch is NOT Stage 7.1 PASS. PASS requires a successful workflow run with real MT5 data and metadata evidence.
