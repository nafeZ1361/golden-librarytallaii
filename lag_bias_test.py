# -*- coding: utf-8 -*-
r"""
ONE-BAR LAG BIAS TEST - DRAFT v1 FOR REVIEW - DO NOT RUN YET
========================================================================

Status : DRAFT awaiting explicit user review. This file has NOT been executed.
Purpose: Quantify Phase-1 Finding #2 / #7 ("Zero-Latency Entry Bias" - backtest()
         enters at current_bar['close'] using a signal computed from that SAME
         bar, whereas the live path (Trend_change_signal) deliberately lags one
         bar behind by comparing trend[-2] vs trend[-3]).

WHAT IT DOES:
    1. Reuses the FROZEN dataset already on disk from determinism_test.py
       (project_audit/determinism_cache/df.csv, signal.csv, confirmation.csv).
       Does NOT fetch anything new from MT5. If that cache is missing, this
       script aborts (exit code 4) rather than fetching fresh data itself -
       comparisons must run on the exact same candles as the locked baseline.
    2. Runs backtest() ONCE with the signals exactly as frozen (= reproduces
       the Baseline Lock result: Total Trades 75, Win Rate 42.67%, ROI 42.00%
       on the 2026-07-22..2026-09-03 XAUUSD. 3m window - if this run does not
       reproduce that baseline, the two datasets are not actually identical
       and the comparison below is invalid; the script will say so explicitly).
    3. Builds a SECOND signal/confirmation pair shifted by one bar:
       lagged_signal[i]       = signal[i-1]        (lagged_signal[0] = 'hold')
       lagged_confirmation[i] = confirmation[i-1]   (lagged_confirmation[0] = 'hold')
       This approximates "what if entry only happened on the bar AFTER the
       signal bar closed" - i.e. the live-path's [-2]-vs-[-3] discipline -
       without touching backtest()'s internal entry-price logic (still
       current_bar['close'], but now attached to the bar the signal moved to).
    4. Runs backtest() a second time on the lagged signals, same parameters
       otherwise (verbatim from backtester.py / determinism_test.py).
    5. Prints both trade-statistics blocks side by side and the delta in
       Total Trades, Win Rate, Total Profit and ROI. Does NOT draw a
       pass/fail verdict - the two numbers are simply reported for the user
       to interpret, since "smaller ROI under lag" is evidence of bias but
       the exact magnitude needs human judgement in context.

WHAT THIS DOES NOT DO (explicit scope limits):
    - Does not fix or modify create_order / backtest() / any project file.
    - Does not test the TP/SL-same-bar-ordering bias (Finding #1) or the
      live-vs-backtest candle-source mismatch (Finding #5) - those need
      separate, differently-shaped tests.
    - Does not re-fetch MT5 data; results are only valid for the exact
      frozen window already on disk (2026-07-22 07:12 .. 2026-09-03 14:45
      per the last determinism_test.py run, subject to whatever is actually
      in the cache file at run time - this script prints the actual range
      it read so that can be double-checked, not assumed).

SIDE EFFECTS (full disclosure):
    - backtest() itself unconditionally writes one HTML report per call
      (hashem_backtest.py:725-732) into backtest/. Two calls here -> two
      MORE report files, in addition to the two already produced by
      determinism_test.py. Cannot be avoided without editing project code
      (which this draft refuses to do).
    - Writes ONE new evidence file: project_audit/determinism_cache/
      lag_bias_result.md. Does not overwrite df.csv/signal.csv/confirmation.csv
      or any determinism_test.py output.
    - No mt5 fetch (reuses cache). No orders. No state files touched.

RUN MODE (after approval, same interpreter as determinism_test.py - i.e. the
project's Python 3.12, NOT any bundled/agent interpreter, since project
.pyc files are cpython-312 and dependency versions are otherwise unpinned):
    python .\lag_bias_test.py     (from the project root)

Exit codes: 0 = completed (see printed deltas), 1 = baseline reproduction
            mismatch (frozen re-run != locked baseline - stop and investigate
            before trusting the lag comparison), 4 = frozen cache missing.
"""

import io
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)

CACHE_DIR = os.path.join(SCRIPT_DIR, "project_audit", "determinism_cache")
DF_PATH = os.path.join(CACHE_DIR, "df.csv")
SIG_PATH = os.path.join(CACHE_DIR, "signal.csv")
CONF_PATH = os.path.join(CACHE_DIR, "confirmation.csv")

# Locked baseline from the last determinism_test.py PASS-on-statistics run.
# Used only as a sanity check that the reused cache still reproduces it.
LOCKED_BASELINE = {
    "Total Trades Executed": 75,
    "Winning Trades": 32,
    "Losing Trades": 43,
    "Win Rate": 42.67,
    "Total Profit": 2100.00,
    "Final Balance": 7100.00,
    "ROI": 42.00,
}


def check_dependencies():
    missing = []
    for mod in ("numpy", "pandas", "plotly", "yfinance", "MetaTrader5", "ta", "pandas_ta"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print("MISSING DEPENDENCIES:", ", ".join(missing))
        print("This draft installs nothing by design. Install them, then re-run.")
        sys.exit(2)


check_dependencies()

from backtest.hashem_backtest import backtest  # noqa: E402

# ---- parameter set copied VERBATIM from backtest/backtester.py / determinism_test.py ----
SYMBOL = 'XAUUSD.'
TF = '3m'
BACKTEST_DAYS = 30
USE_RISK_FREE = False
RISK_FREE_DISTANCE_PIPS = 50.0
USE_SL = True
SL_PIPS = 100.0
USE_TP = True
TP_PIPS = 200.0
CLOSE_OPPOSITE_POSITION = False
INITIAL_BALANCE = 5000.0
POSITION_SIZE_MODE = 'risk_percent'
FIXED_LOT_SIZE = 0.01
RISK_PERCENT = 2
RISK_BASED_ON = 'initial'
ANALYZE_WEEKDAYS = True
ANALYZE_TIME_SESSIONS = True
SESSION_DURATION_HOURS = 4.0


def load_frozen_inputs():
    if not all(os.path.exists(p) for p in (DF_PATH, SIG_PATH, CONF_PATH)):
        print("[error] frozen cache not found at %s" % CACHE_DIR)
        print("Run determinism_test.py first (it creates this cache); "
              "this script deliberately does not fetch MT5 data itself.")
        sys.exit(4)

    import pandas as pd
    df = pd.read_csv(DF_PATH)
    df["time"] = pd.to_datetime(df["time"])
    signal = pd.read_csv(SIG_PATH)["signal"].tolist()
    confirmation = pd.read_csv(CONF_PATH)["confirmation"].tolist()
    print("[load] frozen cache: %d candles (%s .. %s)"
          % (len(df), df["time"].iloc[0], df["time"].iloc[-1]))
    return df, signal, confirmation


def build_lagged(signal, confirmation):
    """Shift both signal series one bar later: lagged[i] = original[i-1]."""
    lagged_signal = ["hold"] + list(signal[:-1])
    lagged_confirmation = ["hold"] + list(confirmation[:-1])
    return lagged_signal, lagged_confirmation


def run_once(df, signal, confirmation, tag):
    buf = io.StringIO()
    with redirect_stdout(buf):
        report = backtest(
            df.copy(), list(signal), list(confirmation), symbol=SYMBOL, tf=TF,
            backtest_days=BACKTEST_DAYS,
            use_risk_free=USE_RISK_FREE, risk_free_distance_pips=RISK_FREE_DISTANCE_PIPS,
            use_sl=USE_SL, sl_pips=SL_PIPS, use_tp=USE_TP, tp_pips=TP_PIPS,
            close_opposite_position=CLOSE_OPPOSITE_POSITION,
            initial_balance=INITIAL_BALANCE,
            position_size_mode=POSITION_SIZE_MODE, fixed_lot_size=FIXED_LOT_SIZE,
            risk_percent=RISK_PERCENT, risk_based_on=RISK_BASED_ON,
            analyze_weekdays=ANALYZE_WEEKDAYS,
            analyze_time_sessions=ANALYZE_TIME_SESSIONS,
            session_duration_hours=SESSION_DURATION_HOURS,
        )
    out = buf.getvalue()
    print("[run %s] report=%s" % (tag, report))
    return out, report


def parse_stats(stdout_text):
    """Pull the known numeric fields out of the printed statistics block."""
    stats = {}
    for line in stdout_text.splitlines():
        for key in LOCKED_BASELINE:
            prefix = key + ":"
            if line.strip().startswith(prefix):
                raw = line.split(":", 1)[1].strip()
                raw = raw.replace("$", "").replace("%", "").strip()
                try:
                    stats[key] = float(raw)
                except ValueError:
                    stats[key] = raw
    return stats


def main():
    df, signal, confirmation = load_frozen_inputs()

    print("\n[baseline check] re-running backtest() on the UNMODIFIED frozen "
          "signals to confirm the cache still reproduces the locked baseline...")
    out_base, rep_base = run_once(df, signal, confirmation, "baseline_recheck")
    base_stats = parse_stats(out_base)

    mismatch = []
    for key, locked_val in LOCKED_BASELINE.items():
        got = base_stats.get(key)
        if got is None or abs(float(got) - float(locked_val)) > 0.005:
            mismatch.append("%s: locked=%s got=%s" % (key, locked_val, got))

    if mismatch:
        print("\n[FAIL] frozen cache does NOT reproduce the locked baseline:")
        for m in mismatch:
            print("  " + m)
        print("\nStopping - the lag comparison below would not be meaningful "
              "against a baseline that does not match. Investigate before "
              "re-running (has df.csv/signal.csv/confirmation.csv changed "
              "since the last determinism_test.py run?).")
        sys.exit(1)

    print("[OK] baseline reproduced exactly - proceeding with lag comparison.")

    lagged_signal, lagged_confirmation = build_lagged(signal, confirmation)
    print("\n[lag run] backtest() with signal/confirmation shifted one bar later...")
    out_lag, rep_lag = run_once(df, lagged_signal, lagged_confirmation, "lagged")
    lag_stats = parse_stats(out_lag)

    print("\n" + "=" * 70)
    print("ONE-BAR LAG BIAS TEST - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("candles: %d (unchanged, frozen)" % len(df))
    print("=" * 70)
    header = "%-26s %15s %15s %15s" % ("metric", "baseline(t)", "lagged(t-1)", "delta")
    print(header)
    print("-" * len(header))
    for key in LOCKED_BASELINE:
        b = base_stats.get(key)
        l = lag_stats.get(key)
        if isinstance(b, (int, float)) and isinstance(l, (int, float)):
            delta = l - b
            print("%-26s %15.2f %15.2f %15.2f" % (key, b, l, delta))
        else:
            print("%-26s %15s %15s %15s" % (key, b, l, "n/a"))

    result_lines = [
        "ONE-BAR LAG BIAS TEST - %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "candles: %d" % len(df),
        "",
        "baseline (signal/confirmation as frozen, i.e. current-bar entry):",
    ] + ["  %s: %s" % (k, base_stats.get(k)) for k in LOCKED_BASELINE] + [
        "",
        "lagged (signal/confirmation shifted 1 bar later):",
    ] + ["  %s: %s" % (k, lag_stats.get(k)) for k in LOCKED_BASELINE] + [
        "",
        "report files: %s | %s" % (rep_base, rep_lag),
        "",
        "NOTE: this isolates the effect of entry timing (Finding #2/#7) only.",
        "It does NOT correct the TP/SL same-bar ordering bias (Finding #1) or",
        "the live-vs-backtest candle-source mismatch (Finding #5); the lagged",
        "numbers above are still optimistic relative to true live behavior.",
    ]
    result_path = os.path.join(CACHE_DIR, "lag_bias_result.md")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write("\n".join(result_lines))
    print("\n[saved] %s" % result_path)


if __name__ == "__main__":
    main()
