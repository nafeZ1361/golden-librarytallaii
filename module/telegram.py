from .mt5 import *
from .indicators import *
import telebot
import mplfinance as mpf

TOKEN = 'yorToken'

bot = telebot.TeleBot(TOKEN)

# CHANNEL_ID = '@HashemTrader'
CHANNEL_ID = '337250342'

def send_message_to_channel(message):
    bot.send_message(CHANNEL_ID, message)


def send_image_to_channel(image_path, caption=""):
    with open(image_path, 'rb') as image:
        bot.send_photo(CHANNEL_ID, image, caption=caption)
        

@bot.message_handler(func=lambda message: True)
def echo_all(message):
  
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
     
    df = candle(symbol, timeframe, limit=60).obj
    
    if df is not None:
        df['aligned_time'] = pd.to_datetime(df['aligned_time'])
        df.set_index('aligned_time', inplace=True)
        
        df.columns = df.columns.str.lower()
        
        image_path = plot_candlestick_with_levels(df, stop_loss, tp1, tp2, tp3)

        send_image_to_channel(
            image_path,
            caption=(message)
        )
    else:
        return


def send_telegram_signal_1tp(symbol, timeframe, stop_loss, tp1, message):
    
    df = candle(symbol, timeframe, limit=60).obj
    
    if df is not None:
        df['aligned_time'] = pd.to_datetime(df['aligned_time'])
        df.set_index('aligned_time', inplace=True)
        
        df.columns = df.columns.str.lower()
        
        image_path = plot_candlestick_with_levels2(df, stop_loss, tp1)

        send_image_to_channel(
            image_path,
            caption=(message)
        )
    else:
        print(f"خطا در دریافت داده‌ها برای {symbol}")
        return



@bot.message_handler(func=lambda message: True)
def echo_all(message):
    send_message_to_channel(message.text)
