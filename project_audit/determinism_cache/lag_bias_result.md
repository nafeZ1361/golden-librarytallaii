ONE-BAR LAG BIAS TEST - 2026-09-03 15:41:27
candles: 14400

baseline (signal/confirmation as frozen, i.e. current-bar entry):
  Total Trades Executed: 75.0
  Winning Trades: 32.0
  Losing Trades: 43.0
  Win Rate: 42.67
  Total Profit: 2100.0
  Final Balance: 7100.0
  ROI: 42.0

lagged (signal/confirmation shifted 1 bar later):
  Total Trades Executed: 81.0
  Winning Trades: 35.0
  Losing Trades: 46.0
  Win Rate: 43.21
  Total Profit: 2400.0
  Final Balance: 7400.0
  ROI: 48.0

report files: backtest/backtest_report_XAUUSD._3m_20260903_154123.html | backtest/backtest_report_XAUUSD._3m_20260903_154127.html

NOTE: this isolates the effect of entry timing (Finding #2/#7) only.
It does NOT correct the TP/SL same-bar ordering bias (Finding #1) or
the live-vs-backtest candle-source mismatch (Finding #5); the lagged
numbers above are still optimistic relative to true live behavior.