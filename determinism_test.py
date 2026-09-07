# -*- coding: utf-8 -*-
r"""
DETERMINISM TEST (BASELINE LOCK) - DRAFT v1 FOR REVIEW - DO NOT RUN YET
========================================================================

Status : DRAFT awaiting explicit user review. This file has NOT been executed.
Target : backtest() in backtest/hashem_backtest.py (defined at line 21) - the only
         backtest function wired to an entry script in this repo
         (backtest/backtester.py). run_backtest() (line 846) is reachable ONLY via
         optimize_strategy() (line 795) and is therefore out of scope here.

Run mode (after approval):
    python .\determinism_test.py     (from the project root; the script chdirs
    itself to its own folder so relative report paths match the project layout)

Exit codes: 0 = PASS, 1 = FAIL (outputs differ), 2 = missing dependencies,
            3 = empty dataset from MT5.

WHY "FROZEN" DESIGN (important):
    backtest/backtester.py fetches the LAST `limit` candles from MT5 at run time
    (mt5.copy_rates_from_pos, hashem_backtest.py:1316) and computes its two signal
    series with two MORE separate MT5 fetches (indicators.py:67-69 and 889-892).
    Running the full script twice therefore compares two DIFFERENT data windows
    whenever a new 3m candle appeared between runs, plus a possible intra-run
    misalignment between the three fetches. That measures data drift, not code
    determinism. This test freezes ONE dataset + ONE signal set to disk, then
    calls backtest() TWICE on byte-identical inputs. Any output difference then
    isolates the simulation function itself (Baseline Lock).

WHAT IT DOES:
    1. Freeze stage (once): df  = backtest_candle('XAUUSD.', '3m', 14400)
       signal       = backtest_supertrend(..., atr_period=10, multiplier=3.0,
                                         candle_type='ha')['signal']
       confirmation = backtest_trend_ali(..., length=60, length_mult=6.0,
                                         mode='Hma', candle_type='ha')['trend']
       Then aligns lengths exactly like backtester.py lines 24-31 and saves all
       three to CSV. If the cache already exists it is reused untouched
       (no MT5 fetch on re-runs).
    2. Calls backtest() twice with byte-identical df/signals and the parameter
       set copied verbatim from backtester.py. Captures each run's stdout (the
       "BACKTEST COMPLETED - TRADE STATISTICS" block, hashem_backtest.py:304-325)
       and the returned report filename.
    3. Compares: (a) the two stdout texts, (b) the two generated HTML reports
       after blanking the generation timestamp (hashem_backtest.py:668) - or the
       "No trades executed" case where backtest() returns None
       (hashem_backtest.py:299-301).
    4. Writes evidence to project_audit/determinism_cache/ and prints PASS/FAIL
       plus a short diff of the first differences.

SIDE EFFECTS (full disclosure - nothing else is touched):
    - CREATES project_audit/determinism_cache/ (df.csv, signal.csv,
      confirmation.csv, run1_stdout.txt, run2_stdout.txt, result.md) - new
      files only, never overwrites project sources.
    - backtest() ITSELF unconditionally writes one HTML report per call into
      backtest/ (backtest_report_XAUUSD._3m_<YYYYmmdd_HHMMSS>.html,
      hashem_backtest.py:725-732). Two calls -> two report files. This cannot
      be avoided without editing project code (which this draft refuses to do).
    - Calls mt5.initialize() and one read-only market-data request
      (copy_rates_from_pos) during the freeze stage only. backtest() also calls
      mt5.initialize()/symbol_info() internally (hashem_backtest.py:31-33) to
      read symbol digits; if MT5 is unreachable it SILENTLY falls back to
      digits=5 (bare except, hashem_backtest.py:34-35), which changes pip size
      and therefore ALL results. This test logs the detected digits at start so
      a silent fallback cannot go unnoticed.
    - Sends NO orders, opens NO positions, touches NO bot_state.json / state
      files / database, and modifies NO existing project file.

RUNTIME DEPENDENCIES: pandas, numpy, plotly, yfinance, MetaTrader5, ta,
                      pandas_ta (imported indirectly via backtest.indicators),
                      and a running, logged-in MT5 terminal for the freeze stage.
"""

import hashlib
import io
import os
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPT_DIR)  # backtest() writes reports to the relative path 'backtest/...'

CACHE_DIR = os.path.join(SCRIPT_DIR, "project_audit", "determinism_cache")


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

from backtest.hashem_backtest import backtest, backtest_candle  # noqa: E402
from backtest.indicators import backtest_supertrend, backtest_trend_ali  # noqa: E402

# ---- parameter set copied VERBATIM from backtest/backtester.py ----
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
# signal parameters, verbatim from backtester.py
ATR_PERIOD = 10
MULTIPLIER = 3.0
TREND_LENGTH = 60
TREND_LENGTH_MULT = 6.0
TREND_MODE = 'Hma'
CANDLE_TYPE = 'ha'


def mt5_status():
    """Log whether MT5 is reachable and how many digits the symbol reports."""
    try:
        import MetaTrader5 as mt5
        ok = mt5.initialize()
        info = mt5.symbol_info(SYMBOL) if ok else None
        digits = info.digits if info is not None else None
        return "initialize=%s digits=%s" % (ok, digits)
    except Exception as exc:  # module missing or terminal unreachable
        return "UNAVAILABLE (%r)" % (exc,)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def freeze_inputs():
    os.makedirs(CACHE_DIR, exist_ok=True)
    df_path = os.path.join(CACHE_DIR, "df.csv")
    sig_path = os.path.join(CACHE_DIR, "signal.csv")
    conf_path = os.path.join(CACHE_DIR, "confirmation.csv")

    if all(os.path.exists(p) for p in (df_path, sig_path, conf_path)):
        import pandas as pd
        df = pd.read_csv(df_path)
        df["time"] = pd.to_datetime(df["time"])
        signal = pd.read_csv(sig_path)["signal"].tolist()
        confirmation = pd.read_csv(conf_path)["confirmation"].tolist()
        print("[freeze] cache reused: %d candles (%s .. %s)"
              % (len(df), df["time"].iloc[0], df["time"].iloc[-1]))
        return df, signal, confirmation

    print("[freeze] no cache -> fetching from MT5 (read-only market data)...")
    minutes = 3  # extract_number('3m'); kept literal to avoid helper coupling
    limit = int(BACKTEST_DAYS * 1440 / minutes)
    df = backtest_candle(SYMBOL, TF, limit)
    if len(df) == 0:
        print("[freeze] MT5 returned no candles for %s %s - aborting." % (SYMBOL, TF))
        sys.exit(3)
    limit = len(df)

    signal = backtest_supertrend(SYMBOL, TF, limit, atr_period=ATR_PERIOD,
                                 multiplier=MULTIPLIER,
                                 candle_type=CANDLE_TYPE)["signal"]
    confirmation = backtest_trend_ali(SYMBOL, TF, limit, length=TREND_LENGTH,
                                      length_mult=TREND_LENGTH_MULT,
                                      mode=TREND_MODE,
                                      candle_type=CANDLE_TYPE)["trend"]

    # alignment exactly as backtester.py lines 24-31
    if len(signal) > len(df):
        signal = signal[-len(df):]
    if len(confirmation) > len(df):
        confirmation = confirmation[-len(df):]
    if len(signal) < len(df):
        signal = signal + ["hold"] * (len(df) - len(signal))
    if len(confirmation) < len(df):
        confirmation = confirmation + ["hold"] * (len(df) - len(confirmation))

    import pandas as pd
    df.to_csv(df_path, index=False)
    pd.DataFrame({"signal": signal}).to_csv(sig_path, index=False)
    pd.DataFrame({"confirmation": confirmation}).to_csv(conf_path, index=False)
    print("[freeze] fetched and cached: %d candles (%s .. %s)"
          % (len(df), df["time"].iloc[0], df["time"].iloc[-1]))
    return df, signal, confirmation


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
    path = os.path.join(CACHE_DIR, "run%s_stdout.txt" % tag)
    with open(path, "w", encoding="utf-8") as f:
        f.write(out)
    print("[run %s] report=%s stdout_chars=%d" % (tag, report, len(out)))
    return out, report


TS_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


def normalize_report(path):
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    return TS_RE.sub("TIMESTAMP", html)


def first_diffs(a_text, b_text, max_lines=15):
    a_lines, b_lines = a_text.splitlines(), b_text.splitlines()
    diffs = []
    for i in range(max(len(a_lines), len(b_lines))):
        a = a_lines[i] if i < len(a_lines) else "<missing>"
        b = b_lines[i] if i < len(b_lines) else "<missing>"
        if a != b:
            diffs.append("line %d:\n  run1: %s\n  run2: %s"
                         % (i + 1, a[:160], b[:160]))
        if len(diffs) >= max_lines:
            diffs.append("... (more differences truncated)")
            break
    return "\n".join(diffs)


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    print("[mt5] %s   <- digits affect pip size; silent fallback=5 changes all results"
          % mt5_status())
    df, signal, confirmation = freeze_inputs()

    out1, rep1 = run_once(df, signal, confirmation, "1")
    out2, rep2 = run_once(df, signal, confirmation, "2")

    passed = True
    sections = []

    if out1 == out2:
        sections.append("STDOUT: IDENTICAL")
    else:
        passed = False
        sections.append("STDOUT: DIFFERENT\n" + first_diffs(out1, out2))

    if rep1 is None and rep2 is None:
        sections.append("HTML REPORT: both runs returned None (no trades executed)")
    elif rep1 is None or rep2 is None:
        passed = False
        sections.append("HTML REPORT: mismatch run1=%s run2=%s" % (rep1, rep2))
    else:
        h1, h2 = sha256_file(rep1), sha256_file(rep2)
        n1, n2 = normalize_report(rep1), normalize_report(rep2)
        if h1 == h2:
            sections.append("HTML REPORT: byte-identical (sha256=%s...)" % h1[:16])
        elif n1 == n2:
            sections.append("HTML REPORT: identical after timestamp normalization "
                            "(raw hashes differ only by generation time)")
        else:
            passed = False
            sections.append("HTML REPORT: DIFFERENT after timestamp normalization\n"
                            + first_diffs(n1, n2))
        sections.append("report files: %s | %s" % (rep1, rep2))

    verdict = "PASS - deterministic on frozen inputs" if passed \
        else "FAIL - outputs differ"
    result = ("DETERMINISM TEST (Baseline Lock) - %s\n"
              "target: backtest() hashem_backtest.py:21 via backtester.py "
              "parameter set\n"
              "candles: %d | signal: %d | confirmation: %d\n\n%s\n\nVERDICT: %s\n"
              % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), len(df),
                 len(signal), len(confirmation), "\n\n".join(sections), verdict))
    result_path = os.path.join(CACHE_DIR, "result.md")
    with open(result_path, "w", encoding="utf-8") as f:
        f.write(result)

    print("\n" + "=" * 70)
    print(result)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
