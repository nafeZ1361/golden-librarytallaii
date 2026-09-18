# stability_windows_test.py
# READ-ONLY stability test
# Does NOT modify source code, parameters, strategy, broker state, or orders.
# Creates evidence/results only under project_audit/stability_windows_cache/

import os
import re
import io
import sys
import glob
import json
import contextlib
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------
# Automatically locate project files / Python executable
# ---------------------------------------------------------------------
HASHEM = os.path.join(ROOT, "backtest", "hashem_backtest.py")
BACKTESTER = os.path.join(ROOT, "backtest", "backtester.py")
CACHE = os.path.join(ROOT, "project_audit", "stability_windows_cache")
os.makedirs(CACHE, exist_ok=True)

if not os.path.exists(HASHEM):
    raise FileNotFoundError(HASHEM)

# ---------------------------------------------------------------------
# Import actual project functions
# ---------------------------------------------------------------------
from backtest.hashem_backtest import backtest, backtest_candle
from backtest.indicators import backtest_supertrend, backtest_trend_ali
import MetaTrader5 as mt5
import pandas as pd

# ---------------------------------------------------------------------
# Parameters
# Automatically copied from the known backtester.py configuration.
# If backtester.py contains these values, use them automatically.
# ---------------------------------------------------------------------
SYMBOL = "XAUUSD."
TF = "3m"

WINDOW_DAYS = 30
NUMBER_OF_WINDOWS = 6

USE_RISK_FREE = False
RISK_FREE_DISTANCE_PIPS = 50.0
USE_SL = True
SL_PIPS = 100.0
USE_TP = True
TP_PIPS = 200.0
CLOSE_OPPOSITE_POSITION = False

INITIAL_BALANCE = 5000.0
POSITION_SIZE_MODE = "risk_percent"
FIXED_LOT_SIZE = 0.01
RISK_PERCENT = 2
RISK_BASED_ON = "initial"

ANALYZE_WEEKDAYS = True
ANALYZE_TIME_SESSIONS = True
SESSION_DURATION_HOURS = 4.0

ATR_PERIOD = 10
MULTIPLIER = 3.0
TREND_LENGTH = 60
TREND_LENGTH_MULT = 6.0
TREND_MODE = "Hma"
CANDLE_TYPE = "ha"


# ---------------------------------------------------------------------
# Try to read actual values from backtester.py automatically.
# ---------------------------------------------------------------------
def extract_value(name, default):
    if not os.path.exists(BACKTESTER):
        return default

    try:
        text = open(BACKTESTER, "r", encoding="utf-8").read()

        patterns = [
            rf"^\s*{re.escape(name)}\s*=\s*([^\n#]+)",
        ]

        for pattern in patterns:
            m = re.search(pattern, text, re.MULTILINE)
            if m:
                raw = m.group(1).strip()
                try:
                    return eval(raw, {"__builtins__": {}}, {})
                except Exception:
                    return raw.strip("'\"")

    except Exception:
        pass

    return default


SYMBOL = extract_value("symbol", SYMBOL)
TF = extract_value("tf", TF)
WINDOW_DAYS = extract_value("BACKTEST_DAYS", WINDOW_DAYS)
USE_RISK_FREE = extract_value("USE_RISK_FREE", USE_RISK_FREE)
RISK_FREE_DISTANCE_PIPS = extract_value(
    "RISK_FREE_DISTANCE_PIPS", RISK_FREE_DISTANCE_PIPS
)
USE_SL = extract_value("USE_SL", USE_SL)
SL_PIPS = extract_value("SL_PIPS", SL_PIPS)
USE_TP = extract_value("USE_TP", USE_TP)
TP_PIPS = extract_value("TP_PIPS", TP_PIPS)
CLOSE_OPPOSITE_POSITION = extract_value(
    "CLOSE_OPPOSITE_POSITION", CLOSE_OPPOSITE_POSITION
)
INITIAL_BALANCE = extract_value("INITIAL_BALANCE", INITIAL_BALANCE)
POSITION_SIZE_MODE = extract_value(
    "POSITION_SIZE_MODE", POSITION_SIZE_MODE
)
FIXED_LOT_SIZE = extract_value("FIXED_LOT_SIZE", FIXED_LOT_SIZE)
RISK_PERCENT = extract_value("RISK_PERCENT", RISK_PERCENT)
RISK_BASED_ON = extract_value("RISK_BASED_ON", RISK_BASED_ON)

ATR_PERIOD = extract_value("ATR_PERIOD", ATR_PERIOD)
MULTIPLIER = extract_value("MULTIPLIER", MULTIPLIER)
TREND_LENGTH = extract_value("TREND_LENGTH", TREND_LENGTH)
TREND_LENGTH_MULT = extract_value(
    "TREND_LENGTH_MULT", TREND_LENGTH_MULT
)
TREND_MODE = extract_value("TREND_MODE", TREND_MODE)
CANDLE_TYPE = extract_value("CANDLE_TYPE", CANDLE_TYPE)


# ---------------------------------------------------------------------
# MT5
# ---------------------------------------------------------------------
def mt5_info():
    ok = mt5.initialize()

    info = None
    digits = None

    if ok:
        info = mt5.symbol_info(SYMBOL)
        if info is not None:
            digits = info.digits

    return ok, digits


# ---------------------------------------------------------------------
# Signal alignment = EXACTLY the existing backtester.py behavior.
# ---------------------------------------------------------------------
def align_signals(df, signal, confirmation):

    signal = list(signal)
    confirmation = list(confirmation)

    if len(signal) > len(df):
        signal = signal[-len(df):]

    if len(confirmation) > len(df):
        confirmation = confirmation[-len(df):]

    if len(signal) < len(df):
        signal = signal + ["hold"] * (len(df) - len(signal))

    if len(confirmation) < len(df):
        confirmation = confirmation + ["hold"] * (
            len(df) - len(confirmation)
        )

    if len(signal) != len(df):
        raise RuntimeError("Signal length mismatch")

    if len(confirmation) != len(df):
        raise RuntimeError("Confirmation length mismatch")

    return signal, confirmation


# ---------------------------------------------------------------------
# Generate signals using the EXISTING project functions.
# ---------------------------------------------------------------------
def generate_signals(df):

    limit = len(df)

    signal = backtest_supertrend(
        SYMBOL,
        TF,
        limit,
        atr_period=ATR_PERIOD,
        multiplier=MULTIPLIER,
        candle_type=CANDLE_TYPE,
    )["signal"]

    confirmation = backtest_trend_ali(
        SYMBOL,
        TF,
        limit,
        length=TREND_LENGTH,
        length_mult=TREND_LENGTH_MULT,
        mode=TREND_MODE,
        candle_type=CANDLE_TYPE,
    )["trend"]

    return align_signals(df, signal, confirmation)


# ---------------------------------------------------------------------
# Run ONE baseline window.
# No lag.
# No optimization.
# No parameter changes.
# ---------------------------------------------------------------------
def run_window(df, window_number, start_time, end_time):

    signal, confirmation = generate_signals(df)

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):
        report = backtest(
            df.copy(),
            list(signal),
            list(confirmation),
            symbol=SYMBOL,
            tf=TF,
            backtest_days=WINDOW_DAYS,
            use_risk_free=USE_RISK_FREE,
            risk_free_distance_pips=RISK_FREE_DISTANCE_PIPS,
            use_sl=USE_SL,
            sl_pips=SL_PIPS,
            use_tp=USE_TP,
            tp_pips=TP_PIPS,
            close_opposite_position=CLOSE_OPPOSITE_POSITION,
            initial_balance=INITIAL_BALANCE,
            position_size_mode=POSITION_SIZE_MODE,
            fixed_lot_size=FIXED_LOT_SIZE,
            risk_percent=RISK_PERCENT,
            risk_based_on=RISK_BASED_ON,
            analyze_weekdays=ANALYZE_WEEKDAYS,
            analyze_time_sessions=ANALYZE_TIME_SESSIONS,
            session_duration_hours=SESSION_DURATION_HOURS,
        )

    stdout = buf.getvalue()

    stdout_path = os.path.join(
        CACHE, f"window_{window_number}_stdout.txt"
    )

    with open(stdout_path, "w", encoding="utf-8") as f:
        f.write(stdout)

    # Extract statistics printed by hashem_backtest.py
    def number(pattern, default=None):
        m = re.search(pattern, stdout, re.IGNORECASE)
        if not m:
            return default
        try:
            return float(m.group(1))
        except Exception:
            return default

    result = {
        "window": window_number,
        "start": str(start_time),
        "end": str(end_time),
        "candles": len(df),
        "total_trades": number(r"Total Trades Executed:\s*([-\d.]+)"),
        "winning_trades": number(r"Winning Trades:\s*([-\d.]+)"),
        "losing_trades": number(r"Losing Trades:\s*([-\d.]+)"),
        "win_rate": number(r"Win Rate:\s*([-\d.]+)%?"),
        "total_profit": number(r"Total Profit:\s*\$?([-\d.]+)"),
        "final_balance": number(r"Final Balance:\s*\$?([-\d.]+)"),
        "roi": number(r"ROI:\s*([-\d.]+)%?"),
        "report": report,
    }

    return result


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------
def main():

    ok, digits = mt5_info()

    print("=" * 70)
    print("MULTI-WINDOW BASELINE STABILITY TEST")
    print("=" * 70)
    print("Mode: READ-ONLY")
    print("Symbol:", SYMBOL)
    print("Timeframe:", TF)
    print("Window days:", WINDOW_DAYS)
    print("Windows:", NUMBER_OF_WINDOWS)
    print("MT5 initialize:", ok)
    print("Symbol digits:", digits)
    print()

    if not ok:
        raise RuntimeError(
            "MT5 is unavailable. Aborting to prevent silent fallback."
        )

    # Calculate exact candle count for each 30-day window.
    tf_minutes = int(re.search(r"\d+", str(TF)).group())
    candles_per_window = int(
        WINDOW_DAYS * 1440 / tf_minutes
    )

    total_candles = candles_per_window * NUMBER_OF_WINDOWS

    print(
        f"[fetch] requesting {total_candles} candles "
        f"for {NUMBER_OF_WINDOWS} consecutive windows..."
    )

    # IMPORTANT:
    # start_pos=1 excludes the currently-forming candle.
    # This test itself does not modify the project function.
    rates = mt5.copy_rates_from_pos(
        SYMBOL,
        mt5.TIMEFRAME_M3,
        1,
        total_candles,
    )

    if rates is None or len(rates) == 0:
        raise RuntimeError("MT5 returned no historical candles.")

    df_all = pd.DataFrame(rates)

    df_all["time"] = pd.to_datetime(
        df_all["time"],
        unit="s"
    )

    df_all = df_all.sort_values("time").reset_index(drop=True)

    if "tick_volume" in df_all.columns:
        df_all.rename(
            columns={"tick_volume": "volume"},
            inplace=True
        )

    print(
        f"[fetch] received {len(df_all)} candles "
        f"({df_all['time'].iloc[0]} .. "
        f"{df_all['time'].iloc[-1]})"
    )

    expected = total_candles

    if len(df_all) != expected:
        print(
            f"[WARNING] expected {expected} candles "
            f"but received {len(df_all)}"
        )

    results = []

    # -----------------------------------------------------------------
    # Split chronological data into independent 30-day windows.
    # Oldest -> newest.
    # -----------------------------------------------------------------
    for n in range(NUMBER_OF_WINDOWS):

        start = n * candles_per_window
        end = start + candles_per_window

        window_df = df_all.iloc[start:end].copy()
        window_df.reset_index(drop=True, inplace=True)

        if len(window_df) == 0:
            continue

        start_time = window_df["time"].iloc[0]
        end_time = window_df["time"].iloc[-1]

        print()
        print("-" * 70)
        print(
            f"[window {n + 1}/{NUMBER_OF_WINDOWS}] "
            f"{start_time} -> {end_time}"
        )
        print(f"candles: {len(window_df)}")

        if len(window_df) < candles_per_window:
            print(
                f"[SKIPPED] incomplete window: {len(window_df)} < "
                f"{candles_per_window} candles - ROI would be misleading."
            )
            results.append({
                "window": n + 1,
                "start": str(start_time),
                "end": str(end_time),
                "candles": len(window_df),
                "total_trades": None,
                "winning_trades": None,
                "losing_trades": None,
                "win_rate": None,
                "total_profit": None,
                "final_balance": None,
                "roi": None,
                "report": "SKIPPED - incomplete window",
            })
            continue

        result = run_window(
            window_df,
            n + 1,
            start_time,
            end_time,
        )

        results.append(result)

        print(
            "trades:",
            result["total_trades"],
            "| win rate:",
            result["win_rate"],
            "| profit:",
            result["total_profit"],
            "| ROI:",
            result["roi"],
        )

        # Save exact input data used by this window.
        window_df.to_csv(
            os.path.join(
                CACHE,
                f"window_{n + 1}_df.csv"
            ),
            index=False,
        )

    # -----------------------------------------------------------------
    # Final comparison
    # -----------------------------------------------------------------
    print()
    print("=" * 70)
    print("WINDOW STABILITY RESULTS")
    print("=" * 70)

    header = (
        "Window | Start | End | Candles | Trades | "
        "WinRate | Profit | ROI"
    )

    print(header)
    print("-" * len(header))

    for r in results:
        print(
            f"{r['window']:>6} | "
            f"{r['start']} | "
            f"{r['end']} | "
            f"{r['candles']:>7} | "
            f"{r['total_trades']} | "
            f"{r['win_rate']}% | "
            f"${r['total_profit']} | "
            f"{r['roi']}%"
        )

    # -----------------------------------------------------------------
    # Stability summary
    # -----------------------------------------------------------------
    rois = [
        r["roi"]
        for r in results
        if r["roi"] is not None
    ]

    trades = [
        r["total_trades"]
        for r in results
        if r["total_trades"] is not None
    ]

    summary = {
        "created": datetime.now().isoformat(),
        "symbol": SYMBOL,
        "timeframe": TF,
        "window_days": WINDOW_DAYS,
        "number_of_windows": len(results),
        "candles_per_window": candles_per_window,
        "mt5_digits": digits,
        "baseline_only": True,
        "lag": False,
        "optimization": False,
        "rois": rois,
        "roi_min": min(rois) if rois else None,
        "roi_max": max(rois) if rois else None,
        "roi_average": (
            sum(rois) / len(rois)
            if rois else None
        ),
        "trades_min": min(trades) if trades else None,
        "trades_max": max(trades) if trades else None,
        "results": results,
    }

    json_path = os.path.join(
        CACHE,
        "stability_results.json"
    )

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            summary,
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    md_path = os.path.join(
        CACHE,
        "stability_results.md"
    )

    with open(md_path, "w", encoding="utf-8") as f:

        f.write("# Multi-Window Baseline Stability Test\n\n")
        f.write(f"- Symbol: `{SYMBOL}`\n")
        f.write(f"- Timeframe: `{TF}`\n")
        f.write(f"- Window: `{WINDOW_DAYS}` days\n")
        f.write(f"- Windows: `{len(results)}`\n")
        f.write("- Mode: Baseline only\n")
        f.write("- Lag: No\n")
        f.write("- Optimization: No\n\n")

        f.write(
            "| Window | Start | End | Candles | "
            "Trades | Win Rate | Profit | ROI |\n"
        )
        f.write(
            "|---:|---|---|---:|---:|---:|---:|---:|\n"
        )

        for r in results:
            f.write(
                f"| {r['window']} | "
                f"{r['start']} | "
                f"{r['end']} | "
                f"{r['candles']} | "
                f"{r['total_trades']} | "
                f"{r['win_rate']}% | "
                f"${r['total_profit']} | "
                f"{r['roi']}% |\n"
            )

        f.write("\n## Summary\n\n")

        if rois:
            f.write(f"- Minimum ROI: **{min(rois)}%**\n")
            f.write(f"- Maximum ROI: **{max(rois)}%**\n")
            f.write(
                f"- Average ROI: **{sum(rois)/len(rois):.2f}%**\n"
            )

        f.write(
            "\nThis report is descriptive only. "
            "No strategy or parameter decision is made automatically.\n"
        )

    print()
    print("=" * 70)
    print("FILES SAVED")
    print("=" * 70)
    print(json_path)
    print(md_path)
    print()
    print("TEST COMPLETE")


if __name__ == "__main__":
    main()
