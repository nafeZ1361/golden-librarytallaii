# bot_runner.py — SAFE runnable version of the trading bot (Phase-2 deliverable)
#
# Default mode = DRY RUN: computes the tested baseline signals on the live feed
# and logs intended orders. It NEVER sends orders unless BOTH environment
# variables are set:  DRY_RUN=0  AND  ALLOW_LIVE=1  (and even then: DEMO account only).
#
# Safety wiring (fixes Phase-0 HIGH-RISK findings):
#   - Fixed risk per trade (RISK_PCT=1.0). The loss-chasing risk_corrector_*
#     functions are deliberately NOT used (they escalate risk toward 100%).
#   - Kill-switches WIRED: daily drawdown 5% / total drawdown 12% checked every
#     loop; on trigger (live mode) all bot positions are closed and the bot stops.
#   - ONE tested strategy only (Supertrend(10,3) flip + trend_ali(60,6,Hma)
#     agreement = the coherent baseline), one position at a time, SL/TP attached.
#   - Signals evaluated on the last CLOSED bar ([-2] discipline), forming bar excluded.
#
# Run (dry run):    C:\Python312\python.exe bot_runner.py
# Run (live demo):  set DRY_RUN=0 and ALLOW_LIVE=1 first. DEMO account only.
# Stop:             Ctrl+C

import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

for mod in ("numpy", "pandas", "MetaTrader5", "ta", "pandas_ta", "plotly", "yfinance"):
    try:
        __import__(mod)
    except ImportError:
        print("MISSING DEPENDENCY:", mod)
        sys.exit(2)

import MetaTrader5 as mt5
from module.mt5 import (create_order, close_all_positions, balance, pnl_today,
                        daily_draw_down_checker, total_draw_down, lot_calculator,
                        total_position_comment, buy, sell)
from backtest.indicators import backtest_supertrend, backtest_trend_ali

# ---------------- configuration ----------------
SYMBOL, TF = 'XAUUSD.', '3m'
COMMENT = 'coherent_stg'
DRY_RUN = os.environ.get("DRY_RUN", "1") != "0"
ALLOW_LIVE = os.environ.get("ALLOW_LIVE", "0") == "1"
RISK_PCT = 1.0          # fixed % of balance per trade (no escalation)
SL_PIPS, TP_PIPS = 100.0, 200.0   # tested baseline: $10 SL / $20 TP on gold
DAILY_DD, TOTAL_DD = 5.0, 12.0    # kill-switch thresholds (%, from original cell-1 config)
LOOP_SECONDS = 20
LOOKBACK_BARS = 14400   # 30 days of M3 bars for indicator warm-up

if (not DRY_RUN) and (not ALLOW_LIVE):
    sys.exit("[guard] live mode requires ALLOW_LIVE=1. Refusing to start.")
if not DRY_RUN:
    print("[WARN] LIVE MODE: orders WILL be sent. DEMO account only!")

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)

# ---------------- init ----------------
if not mt5.initialize():
    log("MT5 initialize failed: %s" % str(mt5.last_error()))
    sys.exit(3)
info = mt5.symbol_info(SYMBOL)
if info is None:
    log("symbol not found: %s" % SYMBOL)
    sys.exit(3)
digits = info.digits
pip = (10 ** -digits) * 10
if not mt5.symbol_select(SYMBOL, True):
    log("could not select symbol")
    sys.exit(3)
start_balance = balance()
log("mode=%s | %s %s | digits=%s pip=%s | start_balance=%.2f"
    % ("DRY-RUN" if DRY_RUN else "LIVE", SYMBOL, TF, digits, pip, start_balance))
log("kill-switches: daily_dd=%.1f%% total_dd=%.1f%% | risk=%.1f%%/trade | strategy=ST(10,3)+trend_ali(60,6,Hma)"
    % (DAILY_DD, TOTAL_DD, RISK_PCT))

last_sig = None
killed = False

try:
    while not killed:
        # ---- kill-switches (wired every loop) ----
        if daily_draw_down_checker(start_balance, DAILY_DD):
            log("KILL-SWITCH: daily drawdown %.1f%% hit (pnl_today=%.2f)" % (DAILY_DD, pnl_today()))
            if not DRY_RUN:
                close_all_positions()
            killed = True
            break
        if total_draw_down(start_balance, TOTAL_DD):
            log("KILL-SWITCH: total drawdown %.1f%% hit" % TOTAL_DD)
            if not DRY_RUN:
                close_all_positions()
            killed = True
            break

        # ---- signals on the last CLOSED bar ----
        st = backtest_supertrend(SYMBOL, TF, LOOKBACK_BARS, atr_period=10,
                                 multiplier=3.0, candle_type='ha')
        conf = backtest_trend_ali(SYMBOL, TF, LOOKBACK_BARS, length=60, length_mult=6.0,
                                  mode='Hma', candle_type='ha')['trend']
        sig = st['signal'][-2]        # last CLOSED bar (forming bar is [-1])
        trend = conf[-2]

        if sig != last_sig:
            log("signal: %s (trend_ali=%s)" % (sig, trend))
            last_sig = sig

        if sig in ('buy', 'sell') and total_position_comment(COMMENT) == 0:
            agreed = (sig == 'buy' and trend == 'buy') or (sig == 'sell' and trend == 'sell')
            if agreed:
                tick = mt5.symbol_info_tick(SYMBOL)
                if sig == 'buy':
                    entry = tick.ask
                    sl = entry - SL_PIPS * pip
                    tp = entry + TP_PIPS * pip
                    otype = buy
                else:
                    entry = tick.bid
                    sl = entry + SL_PIPS * pip
                    tp = entry - TP_PIPS * pip
                    otype = sell
                lot = lot_calculator(SYMBOL, RISK_PCT, entry, sl)
                if DRY_RUN:
                    log("DRY-RUN intended order: %s %s lot=%.2f entry=%.2f sl=%.2f tp=%.2f (comment=%s)"
                        % (sig, SYMBOL, lot, entry, sl, tp, COMMENT))
                else:
                    res = create_order(SYMBOL, lot, otype, sl, tp, COMMENT)
                    log("LIVE order sent: %s lot=%.2f retcode=%s"
                        % (sig, lot, getattr(res, "retcode", None)))

        time.sleep(LOOP_SECONDS)

except KeyboardInterrupt:
    log("stopped by user (Ctrl+C).")
finally:
    if not DRY_RUN and killed:
        log("kill-switch shutdown complete.")
    mt5.shutdown()
    log("MT5 connection closed.")
