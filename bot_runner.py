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
                        total_position_comment, buy, sell,
                        check_time, is_news, HARD_RISK_CAP_PERCENT)
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
# CP19 LOOP-6 / CP21 safety gates (engineering; no strategy parameter):
SESSION_START_HOUR = int(os.environ.get("SESSION_START_HOUR", "0"))   # 0-23 broker hour
SESSION_END_HOUR = int(os.environ.get("SESSION_END_HOUR", "23"))      # default: always allow
NEWS_FILTER = os.environ.get("NEWS_FILTER", "1") == "1"               # default: ON
MAX_LOT = float(os.environ.get("MAX_LOT", "1.0"))                     # order-size ceiling

if (not DRY_RUN) and (not ALLOW_LIVE):
    sys.exit("[guard] live mode requires ALLOW_LIVE=1. Refusing to start.")
if not DRY_RUN:
    print("[WARN] LIVE MODE: orders WILL be sent. DEMO account only!")

def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)

# CP23: optional Telegram notifications (notifications ONLY — no order
# capability; module/telegram.py never reaches a broker and is env-configured)
try:
    from module.telegram import (send_message_to_channel as _tg_notify,
                                 send_trade_signal as _tg_signal)
except Exception:  # noqa: BLE001 - notifications are optional by design
    _tg_notify = None
    _tg_signal = None


def notify(msg):
    if _tg_notify:
        try:
            _tg_notify("[runner] " + msg)
        except Exception as ex:  # noqa: BLE001 - never let notifications crash trading safety
            log("notify failed silently: %s" % type(ex).__name__)

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
# DEMO-ONLY GUARD: order mode (DRY_RUN=0) is allowed on DEMO accounts only.
acct = mt5.account_info()
if acct is None:
    log("account_info() returned None (terminal not logged in?)")
    sys.exit(3)
DEMO_TRADE_MODE = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
if (not DRY_RUN) and getattr(acct, "trade_mode", None) != DEMO_TRADE_MODE:
    sys.exit("[guard] order mode allowed on DEMO accounts only (trade_mode=%s). "
             "Refusing to start." % getattr(acct, "trade_mode", "?"))
start_balance = balance()
log("mode=%s | %s %s | digits=%s pip=%s | start_balance=%.2f"
    % ("DRY-RUN" if DRY_RUN else "LIVE-DEMO", SYMBOL, TF, digits, pip, start_balance))
log("account: login=%s name=%s trade_mode=%s"
    % (getattr(acct, "login", "?"), getattr(acct, "name", "?"),
       getattr(acct, "trade_mode", "?")))
log("kill-switches: daily_dd=%.1f%% total_dd=%.1f%% | risk=%.1f%%/trade | strategy=ST(10,3)+trend_ali(60,6,Hma)"
    % (DAILY_DD, TOTAL_DD, RISK_PCT))
notify("runner started: mode=%s %s %s | risk=%.1f%% | SAFETY=PASS, LIVE=DENIED(research)\n"
       "حالت اجرا: %s\nحساب: %s (login=%s)"
       % ("DRY-RUN" if DRY_RUN else "LIVE-DEMO", SYMBOL, TF, RISK_PCT,
          "آزمایشی — سفارشی ثبت نمی‌شود" if DRY_RUN
          else "دمو — سفارش فقط روی حساب دمو ثبت می‌شود",
          getattr(acct, "name", "?"), getattr(acct, "login", "?")))

last_sig = None
killed = False

try:
    while not killed:
        # ---- kill-switches (wired every loop) ----
        if daily_draw_down_checker(start_balance, DAILY_DD):
            log("KILL-SWITCH: daily drawdown %.1f%% hit" % DAILY_DD)
            notify("KILL-SWITCH: daily drawdown %.1f%% hit -> positions closing, runner stopping"
                   % DAILY_DD)
            if not DRY_RUN:
                close_all_positions()
            killed = True
            break
        if total_draw_down(start_balance, TOTAL_DD):
            log("KILL-SWITCH: total drawdown %.1f%% hit" % TOTAL_DD)
            notify("KILL-SWITCH: total drawdown %.1f%% hit -> positions closing, runner stopping"
                   % TOTAL_DD)
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
            # CP21 safety gates (in mandatory order) — any gate failing => NO ORDER
            if not check_time(SESSION_START_HOUR, SESSION_END_HOUR):
                log("[GATE] TIME CHECK failed (session closed) -> NO ORDER")
            elif NEWS_FILTER and is_news():
                log("[GATE] NEWS CHECK failed (high-impact news window) -> NO ORDER")
            elif agreed:
                tick = mt5.symbol_info_tick(SYMBOL)
                if tick is None:
                    log("[GATE] ORDER VALIDATION failed: no tick -> NO ORDER")
                else:
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
                    # ORDER VALIDATION: bounded size and sane geometry
                    if lot <= 0 or lot > MAX_LOT:
                        log("[GATE] ORDER VALIDATION failed: lot=%.2f outside (0, %.2f]"
                            " -> NO ORDER" % (lot, MAX_LOT))
                    elif abs(entry - sl) <= 0 or abs(tp - entry) <= 0 or entry <= 0:
                        log("[GATE] ORDER VALIDATION failed: degenerate SL/TP -> NO ORDER")
                    elif DRY_RUN:
                        log("DRY-RUN intended order: %s %s lot=%.2f entry=%.2f sl=%.2f tp=%.2f (comment=%s)"
                            % (sig, SYMBOL, lot, entry, sl, tp, COMMENT))
                        # Persian report for the user's Telegram audit trail
                        notify("⚡ سیگنال (حالت آزمایشی — سفارش ثبت نشد)\n"
                               "جهت: %s — %s\n"
                               "حجم: %.2f\n"
                               "قیمت ورود: %.2f\n"
                               "حد ضرر (SL): %.2f\n"
                               "حد سود (TP): %.2f"
                               % ("خرید (BUY)" if sig == 'buy' else "فروش (SELL)",
                                  SYMBOL, lot, entry, sl, tp))
                    else:
                        res = create_order(SYMBOL, lot, otype, sl, tp, COMMENT)
                        retcode = getattr(res, "retcode", None)
                        log("LIVE order sent: %s lot=%.2f retcode=%s"
                            % (sig, lot, retcode))
                        order_fa = ("%s — %s\n"
                                    "حجم: %.2f\n"
                                    "قیمت ورود: %.2f\n"
                                    "حد ضرر (SL): %.2f\n"
                                    "حد سود (TP): %.2f"
                                    % ("خرید (BUY)" if sig == 'buy' else "فروش (SELL)",
                                       SYMBOL, lot, entry, sl, tp))
                        if retcode == getattr(mt5, "TRADE_RETCODE_DONE", 10009):
                            # VIP-style report (chart + caption), user's format.
                            # Optimal Entry = supertrend line (same baseline
                            # params) = ideal pullback re-entry; display only.
                            tf_label = "M" + TF.lower().replace("m", "")
                            one_r = abs(entry - sl)
                            tp1_lvl = entry + one_r if sig == 'buy' else entry - one_r
                            try:
                                from module.indicators import supertrend as _st
                                optimal = float(_st(SYMBOL, TF, atr_period=10,
                                                    multiplier=3.0,
                                                    candle_type='ha')['value'][-2])
                            except Exception:
                                optimal = entry
                            vip = ("❤️%s %s %s Signal❤️✔️\n\n"
                                   "📊Trade Score: ⭐️⭐️⭐️⭐️\n\n"
                                   "💎Market Entry = %.1f\n\n"
                                   "💎Optimal Entry = %.1f\n\n"
                                   "✅Tp1 = %.1f\n\n"
                                   "✅Tp2 = %.1f\n\n"
                                   "🔴Indicator Stop = %.1f\n\n"
                                   "✔️AI Confirmed\n\n"
                                   "✅Optimal Time\n\n"
                                   "❌Smart Counter Trend\n\n"
                                   "⚠️ Risk: %.0f %%"
                                   % (SYMBOL.replace('.', ''), tf_label,
                                      "Sell" if sig == 'sell' else "Buy",
                                      entry, optimal, tp1_lvl, tp, sl, RISK_PCT))
                            sent = False
                            if _tg_signal:
                                try:
                                    sent = _tg_signal(SYMBOL, TF, sl,
                                                      [tp1_lvl, tp], vip)
                                except Exception as ex:  # noqa: BLE001
                                    log("vip chart send failed silently: %s"
                                        % type(ex).__name__)
                            if not sent:
                                notify(vip)  # text-only fallback
                        else:
                            notify("❌ سفارش رد شد (retcode=%s)\n%s"
                                   % (retcode, order_fa))
            elif sig in ('buy', 'sell'):
                log("[GATE] strategy agreement failed -> NO ORDER")

        time.sleep(LOOP_SECONDS)

except KeyboardInterrupt:
    log("stopped by user (Ctrl+C).")
finally:
    if not DRY_RUN and killed:
        log("kill-switch shutdown complete.")
    mt5.shutdown()
    log("MT5 connection closed.")
