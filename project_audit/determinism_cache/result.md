DETERMINISM TEST (Baseline Lock) - 2026-09-03 15:17:38
target: backtest() hashem_backtest.py:21 via backtester.py parameter set
candles: 14400 | signal: 14400 | confirmation: 14400

STDOUT: DIFFERENT
line 15:
  run1: Backtest completed! Report saved to: backtest/backtest_report_XAUUSD._3m_20260903_151731.html
  run2: Backtest completed! Report saved to: backtest/backtest_report_XAUUSD._3m_20260903_151734.html

HTML REPORT: identical after timestamp normalization (raw hashes differ only by generation time)

report files: backtest/backtest_report_XAUUSD._3m_20260903_151731.html | backtest/backtest_report_XAUUSD._3m_20260903_151734.html

VERDICT: FAIL - outputs differ
