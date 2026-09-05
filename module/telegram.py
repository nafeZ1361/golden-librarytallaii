# module/telegram.py — CP19 LOOP-4 (D12) hardened version.
# - Credentials come ONLY from the environment (never hardcoded, never printed):
#     TELEGRAM_BOT_TOKEN  /  TELEGRAM_CHANNEL_ID
# - Import-safe: if telebot/mplfinance are not installed the module still
#   imports (TELEGRAM_AVAILABLE=False) and every send function no-ops with a
#   log. Nothing here can reach a broker; this module is notifications only.
# - The duplicate echo_all handler was removed (CP19 finding).
# - NO polling loop is started by this module.

import os as _os

from .mt5 import *
from .indicators import *

try:
    import telebot
    import mplfinance as mpf
    TELEGRAM_AVAILABLE = True
except ImportError as _imp_ex:
    telebot = None
    mpf = None
    TELEGRAM_AVAILABLE = False
    print("[TELEGRAM] disabled: missing dependency (%s)" % _imp_ex.name)

TOKEN = _os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID = _os.environ.get("TELEGRAM_CHANNEL_ID", "")

# CP23: route Telegram API through a local proxy when configured
# (TELEGRAM_PROXY, e.g. http://127.0.0.1:8227) — required on networks where
# api.telegram.org is blocked. Fail behavior stays fail-open/logged.
TELEGRAM_PROXY = _os.environ.get("TELEGRAM_PROXY", "")
if TELEGRAM_AVAILABLE and telebot is not None and TELEGRAM_PROXY:
    telebot.apihelper.proxy = {"http": TELEGRAM_PROXY, "https": TELEGRAM_PROXY}

if TELEGRAM_AVAILABLE and TOKEN:
    bot = telebot.TeleBot(TOKEN)
else:
    bot = None
    if TELEGRAM_AVAILABLE:
        print("[TELEGRAM] disabled: TELEGRAM_BOT_TOKEN / TELEGRAM_CHANNEL_ID not set")


def _configured():
    if not TELEGRAM_AVAILABLE:
        print("[TELEGRAM] send skipped: telebot/mplfinance not installed")
        return False
    if bot is None or not TOKEN or not CHANNEL_ID:
        print("[TELEGRAM] send skipped: credentials not configured (env)")
        return False
    return True


def send_message_to_channel(message):
    if not _configured():
        return False
    return bot.send_message(CHANNEL_ID, message)


def send_image_to_channel(image_path, caption=""):
    if not _configured():
        return False
    with open(image_path, 'rb') as image:
        return bot.send_photo(CHANNEL_ID, image, caption=caption)


if bot is not None:
    @bot.message_handler(func=lambda message: True)
    def echo_all(message):
        send_message_to_channel(message.text)
else:
    def echo_all(message):  # unconfigured: kept for API compatibility, inert
        send_message_to_channel(message.text)


def plot_candlestick_with_levels(df, stop_loss , tp1 , tp2 , tp3):

    title="\n Telegram Free Signals = @HashemTrader"

    levels = [
        ("SL", stop_loss, "red"),
        ("TP 1", tp1, "green"),
        ("TP 2", tp2, "green"),
        ("TP 3", tp3, "green"),
    ]

    add_plots = []
    for label, level, color in levels:
        add_plots.append(
            mpf.make_addplot(
                [level] * len(df),
                color=color,
                linestyle="--",
                label=f"{label}: {level:.2f}"
            )
        )

    style = mpf.make_mpf_style(base_mpf_style="tradingview", gridstyle="--")

    image_path = "TelegramSignal.png"
    mpf.plot(
        df,
        type="candle",
        addplot=add_plots,
        style=style,
        title=title,
        ylabel="Price",
        savefig=image_path,
        datetime_format="%H:%M",
        volume=False,
    )
    return image_path


def plot_candlestick_with_levels2(df, stop_loss , tp1 ):

    title="\n Telegram Free Signals = @HashemTrader"

    levels = [
        ("SL", stop_loss, "red"),
        ("TP", tp1, "green"),
    ]

    add_plots = []
    for label, level, color in levels:
        add_plots.append(
            mpf.make_addplot(
                [level] * len(df),
                color=color,
                linestyle="--",
                label=f"{label}: {level:.2f}"
            )
        )

    style = mpf.make_mpf_style(base_mpf_style="tradingview", gridstyle="--")

    image_path = "TelegramSignal.png"
    mpf.plot(
        df,
        type="candle",
        addplot=add_plots,
        style=style,
        title=title,
        ylabel="Price",
        savefig=image_path,
        datetime_format="%H:%M",
        volume=False,
    )
    return image_path


def send_telegram_signal_3tp(symbol, timeframe, stop_loss, tp1, tp2, tp3, message):
    if not _configured():
        return False
    df = candle(symbol, timeframe, limit=60).obj

    if df is not None:
        df['aligned_time'] = pd.to_datetime(df['aligned_time'])
        df.set_index('aligned_time', inplace=True)

        df.columns = df.columns.str.lower()

        image_path = plot_candlestick_with_levels(df, stop_loss, tp1, tp2, tp3)

        return send_image_to_channel(
            image_path,
            caption=(message)
        )
    return False


def send_telegram_signal_1tp(symbol, timeframe, stop_loss, tp1, message):
    if not _configured():
        return False
    df = candle(symbol, timeframe, limit=60).obj

    if df is not None:
        df['aligned_time'] = pd.to_datetime(df['aligned_time'])
        df.set_index('aligned_time', inplace=True)

        df.columns = df.columns.str.lower()

        image_path = plot_candlestick_with_levels2(df, stop_loss, tp1)

        return send_image_to_channel(
            image_path,
            caption=(message)
        )
    print(f"خطا در دریافت داده‌ها برای {symbol}")
    return False
