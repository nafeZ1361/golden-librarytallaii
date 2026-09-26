---
name: backtesting
description: Integrate ML signals with the existing XAUUSD replay/backtest engine without rebuilding it or introducing live trading.
---

# Backtesting

1. Inspect the existing Backtester API and strategy contract first.
2. Reuse the existing engine; do not create a parallel engine.
3. Define model inference → signal → strategy/backtester explicitly.
4. Use only information available at decision time.
5. Define signal timestamp and execution timestamp separately.
6. Preserve existing position, spread, commission, PnL, and metric logic unless a verified defect exists.
7. Keep replay deterministic.
8. Add no-lookahead and deterministic replay tests.
9. Produce reproducible evidence artifacts.
10. Never call order execution APIs.
