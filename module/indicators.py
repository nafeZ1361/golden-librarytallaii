from .mt5 import *
import datetime
import pandas as pd
import MetaTrader5 as mt5
import ta
import time
import statistics
import numpy as np
import pandas_ta
 
#lines --------------

def sma_rsi(symbol, tf, rsi_period=14, sma_period=14 , candle_type='ca'):
    
    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)
    candles = pd.DataFrame(ohlc[:], columns=['open', 'high', 'low', 'close'])

    candles['rsi'] = ta.momentum.RSIIndicator(candles['close'], window=rsi_period).rsi()
    
    candles['sma_rsi'] = ta.trend.SMAIndicator(candles['rsi'], window=sma_period).sma_indicator()
    
    sma_rsi_list = candles['sma_rsi'].tolist()
    
    return sma_rsi_list


def ema(symbol, tf , window , candle_type='ca'):
    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)

    prices = pd.DataFrame(ohlc[:])
    prices['ema'] = prices['close'].ewm(span = window).mean()
    ema = prices['ema'].values.tolist()
    return (ema)


def sma(symbol, tf, window, candle_type='ca'):
    
    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)

    prices = pd.DataFrame(ohlc[:])
    
    prices['sma'] = ta.trend.SMAIndicator(prices['close'], window=window).sma_indicator()
   
    ma_values = prices['sma'].values.tolist()
    return ma_values
    

def wma(symbol, tf, window, candle_type='ca'):

    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)

    prices = pd.DataFrame(ohlc[:])
    
   
    prices['wma'] = ta.trend.WMAIndicator(prices['close'], window=window).wma()
   
    ma_values = prices['wma'].values.tolist()
    return ma_values


def mfi(symbol ,tf , period = 14) :
   
    ohlc = candle(symbol, tf , period*5)
   
    candles = pd.DataFrame(ohlc[:]) 
    candles['mfi'] = ta.volume.MFIIndicator(high=candles['high'], low=candles['low'], close=candles['close'], volume=candles['tick_volume'], window=period).money_flow_index()
    mfi = candles['mfi'].tolist()
    return mfi


def cci(symbol, tf, period=20 , candle_type = 'ca'):
    if candle_type == 'ca':
        ohlc = candle(symbol, tf, period * 10)
    else:
        ohlc = heikin_ashi(symbol, tf, period * 10)

    
    candles = pd.DataFrame(ohlc[:])
    
    candles['typical_price'] = (candles['high'] + candles['low'] + candles['close']) / 3
    
    candles['sma_tp'] = candles['typical_price'].rolling(window=period).mean()
    
    def calculate_mean_deviation(tp_series, sma_series, window):
        deviations = []
        for i in range(len(tp_series)):
            if i < window - 1:
                deviations.append(np.nan)
            else:
                tp_window = tp_series[i-window+1:i+1]
                sma_value = sma_series.iloc[i]
                
                mean_dev = np.mean(np.abs(tp_window - sma_value))
                deviations.append(mean_dev)
        
        return pd.Series(deviations, index=tp_series.index)
    
    candles['mean_dev'] = calculate_mean_deviation(
        candles['typical_price'], 
        candles['sma_tp'], 
        period
    )
    
    candles['cci'] = (candles['typical_price'] - candles['sma_tp']) / (0.015 * candles['mean_dev'])
    
    cci_values = candles['cci'].dropna().tolist()
    return cci_values


def smma(symbol , tf , period = 7 , candle_type = 'ca'):

    if candle_type == 'ca':
        ohlc = candle(symbol, tf, period * 10)
    else:
        ohlc = heikin_ashi(symbol, tf, period * 10)

    candles = ohlc[:]

    smma = [np.nan] * (period - 1)
    initial_smma = candles['close'][:period].mean()
    smma.append(initial_smma)
    
    for price in candles['close'][period:]:
        smma_value = (smma[-1] * (period - 1) + price) / period
        smma.append(smma_value)
    return smma


def adx(symbol , tf, di_length=14, adx_smoothing=14 , candle_type = 'ca'):
    if candle_type == 'ca':
        df = candle(symbol, tf,).copy()
    else:
        df = heikin_ashi(symbol, tf).copy()

    high = df['high']
    low = df['low']
    close = df['close']

    up = high.diff()
    down = -low.diff()

    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    true_range = np.maximum.reduce([tr1, tr2, tr3])

    def rma(series, length):
        alpha = 1 / length
        return series.ewm(alpha=alpha, adjust=False).mean()

    smoothed_tr = rma(pd.Series(true_range), di_length)
    smoothed_plus_dm = rma(pd.Series(plus_dm), di_length)
    smoothed_minus_dm = rma(pd.Series(minus_dm), di_length)

    plus_di = 100 * smoothed_plus_dm / smoothed_tr
    minus_di = 100 * smoothed_minus_dm / smoothed_tr

    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)

    adx = rma(dx, adx_smoothing)

    return adx.tolist()


def dema(symbol , tf , period = 9 , candle_type = 'ca'):
    if candle_type == 'ca':
        ohlc = candle(symbol, tf, period * 5)
    else:
        ohlc = heikin_ashi(symbol, tf, period * 5)

    candles = ohlc[:]

    candles['ema1'] = candles['close'].ewm(span=period, adjust=False).mean()
    candles['ema2'] = candles['ema1'].ewm(span=period, adjust=False).mean()
    candles['dema'] = 2 * candles['ema1'] - candles['ema2']
    dema = candles['dema'].tolist()

    return dema


def tema(symbol , tf , period = 14 , candle_type = 'ca') : 

    if candle_type == 'ca':
        ohlc = candle(symbol, tf, period * 10)
    else:
        ohlc = heikin_ashi(symbol, tf, period * 10)

    candles = ohlc[:]

    candles['ema1'] = candles['close'].ewm(span=period, adjust=False).mean()
    candles['ema2'] = candles['ema1'].ewm(span=period, adjust=False).mean()
    candles['ema3'] = candles['ema2'].ewm(span=period, adjust=False).mean()
    candles['tema'] = (3 * (candles['ema1'] - candles['ema2'])) + candles['ema3']
    tema = candles['tema'].tolist()

    return tema


def cross_signal(series1, series2):
    if series1[-1] > series2[-1] and series1[-2] > series2[-2] and series1[-3] <= series2[-3]:
        return 'buy'
    elif series1[-1] < series2[-1] and series1[-2] < series2[-2] and series1[-3] >= series2[-3]:
        return 'sell'
    else:
        return 'hold'

#------------channels

def donchain_channel(symbol , tf ,line = 'middle' ,  period = 20 , candle_type = 'ca') : 

    if candle_type == 'ca':
        ohlc = candle(symbol, tf, period * 2)
    else:
        ohlc = heikin_ashi(symbol, tf, period * 2)

    candles = pd.DataFrame(ohlc[:])

    candles['upper'] = candles['high'].rolling(window=period).max()
    candles['lower'] = candles['low'].rolling(window=period).min()
    candles['middle'] = (candles['upper'] + candles['lower']) / 2

    upper = candles['upper'].shift(+1).tolist()
    lower = candles['lower'].shift(+1).tolist()
    middle = candles['middle'].shift(+1).tolist()

    if line == 'upper' : 
        return upper
    
    if line == 'lower' : 
        return lower

    if line == 'middle' : 
        return middle


def keltner_channels(symbol , tf ,line = 'mid' ,  period = 20 , atr = 10 , multiplier = 2 , candle_type = 'ca') : 

    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)

    candles = pd.DataFrame(ohlc[:])

    candles['EMA'] = candles['close'].ewm(span=period, adjust=False).mean()
    candles['TR'] = np.maximum(candles['high'] - candles['low'], 
                          np.maximum(abs(candles['high'] - candles['close'].shift(1)),
                                     abs(candles['low'] - candles['close'].shift(1))))
    candles['ATR'] = candles['TR'].rolling(window=atr).mean()
    candles['Upper_Channel'] = (candles['EMA'] + (multiplier * candles['ATR'])).shift(1)
    candles['Lower_Channel'] = (candles['EMA'] - (multiplier * candles['ATR'])).shift(1)

    if line == "up" : 
        return candles['Upper_Channel'].tolist()
    
    if line == 'mid' : 
        return candles['EMA'].shift(1).tolist()
    
    if line == 'low' :
        return candles['Lower_Channel'].tolist()


def Bollinger_Band(symbol , tf, window = 20 , num_std_dev=2 , line = 'up' , candle_type = 'ca'):
    
    # line = 'up'  or 'down' , 'sma'
    if candle_type == 'ca':

        ohlc = candle(symbol , tf , limit=window) 
    else:
        ohlc = heikin_ashi(symbol , tf , limit=window) 
    
    
    SMA = statistics.mean(item['low'] for item in ohlc)
 
    SD = statistics.stdev(item['low'] for item in ohlc)
   
    UB = SMA + (num_std_dev * SD)
   
    LB = SMA - (num_std_dev * SD)
    
    if line == 'up' :
        return UB
    elif line == 'down':
        return LB
    else:
        return SMA

#--------------


def rsi(symbol , tf , candle_type = 'ca'):
    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)
    candles = pd.DataFrame(ohlc[:])
    candles['rsi'] = ta.momentum.RSIIndicator(candles['close'], window=14).rsi()
    rsi= candles['rsi'].tolist()
    return rsi


def sar(symbol, tf, start=0.02, increament=0.02, max_value=0.2, candle_type='ca'):
    if candle_type == 'ca':
        df = candle(symbol, tf).copy()
    else:
        df = heikin_ashi(symbol, tf).copy()

    high = df['high'].values    # تبدیل به numpy array
    low = df['low'].values      # تبدیل به numpy array

    length = len(high)
    psar_values = [0.0] * length
    trend = [0] * length
    af = [0.0] * length
    ep = [0.0] * length

    psar_values[0] = low[0]
    trend[0] = 1
    af[0] = start
    ep[0] = high[0]

    for i in range(1, length):
        if trend[i-1] == 1:
            psar_values[i] = psar_values[i-1] + af[i-1] * (ep[i-1] - psar_values[i-1])

            if low[i] <= psar_values[i]:
                trend[i] = -1
                psar_values[i] = ep[i-1]
                ep[i] = low[i]
                af[i] = start
            else:
                trend[i] = 1
                if high[i] > ep[i-1]:
                    ep[i] = high[i]
                    af[i] = min(af[i-1] + increament, max_value)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]

                if i >= 2:
                    psar_values[i] = min(psar_values[i], low[i-1], low[i-2])
                elif i >= 1:
                    psar_values[i] = min(psar_values[i], low[i-1])

        else:
            psar_values[i] = psar_values[i-1] + af[i-1] * (ep[i-1] - psar_values[i-1])

            if high[i] >= psar_values[i]:
                trend[i] = 1
                psar_values[i] = ep[i-1]
                ep[i] = high[i]
                af[i] = start
            else:
                trend[i] = -1
                if low[i] < ep[i-1]:
                    ep[i] = low[i]
                    af[i] = min(af[i-1] + increament, max_value)
                else:
                    ep[i] = ep[i-1]
                    af[i] = af[i-1]

                if i >= 2:
                    psar_values[i] = max(psar_values[i], high[i-1], high[i-2])
                elif i >= 1:
                    psar_values[i] = max(psar_values[i], high[i-1])

    return psar_values

def sar_signal(symbol, tf, start=0.02, increament=0.02, max_value=0.2 , candle_type = 'ca'):
    sar_values = sar(symbol, tf, start, increament, max_value, candle_type)
    candles = candle(symbol , tf , 5)
    if candles[-2]['open'] > sar_values[-2] and candles[-1]['close'] < sar_values[-1] :
        return 'sell'
    elif candles[-2]['open'] < sar_values[-2] and candles[-1]['close'] > sar_values[-1] :
        return 'buy'
    else:
        return False


def swing(symbol , tf , swing = 'high', window = 5 , lookback = 250)  : 

    ohlc = candle(symbol , tf ,lookback)

    candles = pd.DataFrame(ohlc[:])


    high_rolling_max = candles['high'].rolling(window=window, center=True).max()
    low_rolling_min = candles['low'].rolling(window=window, center=True).min()

    candles['swing_high'] = candles['high'][(candles['high'] == high_rolling_max) & (candles['high'].shift(window) < candles['high']) & (candles['high'].shift(-window) < candles['high'])]
    candles['swing_low'] = candles['low'][(candles['low'] == low_rolling_min) & (candles['low'].shift(window) > candles['low']) & (candles['low'].shift(-window) > candles['low'])]
    
    untouched_swing_highs = []
    untouched_swing_lows = []
    
    for i in range(len(candles)):
        if pd.notna(candles['swing_high'].iloc[i]):
            swing_high_touched = any(candles['high'].iloc[i+1:].ge(candles['swing_high'].iloc[i]))
            if not swing_high_touched:
                untouched_swing_highs.append(candles['swing_high'].iloc[i])
        
        if pd.notna(candles['swing_low'].iloc[i]):
            swing_low_touched = any(candles['low'].iloc[i+1:].le(candles['swing_low'].iloc[i]))
            if not swing_low_touched:
                untouched_swing_lows.append( candles['swing_low'].iloc[i])
    
    if swing == "high" : 
        return untouched_swing_highs

    if swing == "low" : 
        return untouched_swing_lows
    

def macd(symbol, tf, fast=12, slow=26, signal=9):

    raw_data = candle(symbol, tf, 500)
  
    data = raw_data.copy()
    
    data['close'] = pd.to_numeric(data['close'], errors='coerce')
    data = data.dropna(subset=['close'])
    
    macd_result = pandas_ta.macd(data['close'], fast=fast, slow=slow, signal=signal)
    
    macd_col = f"MACD_{fast}_{slow}_{signal}"
    signal_col = f"MACDs_{fast}_{slow}_{signal}"
    hist_col = f"MACDh_{fast}_{slow}_{signal}"
    
    mac = macd_result[macd_col]
    sig = macd_result[signal_col]
    his = macd_result[hist_col]
    
    return {
        'macd': mac.tolist(), 
        'signal': sig.tolist(), 
        'histogram': his.tolist()
    }


def line(symbol, upOrdown):

    candles = candle( symbol ,'7d' , 5)
    leg = (candles[-2]['high'] - candles[-2]['low']) / 8
    candle_color = check_candle(symbol , '7d' , -1)
    lines = []

    if candle_color == 'long':
        num1 = candles[-1]['low']
        lines.append(candles[-1]['low'])
        for _ in range(50):
            num1 += leg
            lines.append(num1)
    else:
        num1 = candles[-1]['high']
        lines.append(candles[-1]['high'])
        for _ in range(50):
            num1 -= leg
            lines.append(num1)

    x = []
    if upOrdown == 'up':
        price = mt5.symbol_info_tick(symbol).bid
        for i in lines:
            if i > price:
                x.append(i)

        if len(x) == 0:
            return False
        else:
            return min(x)
    else:
        price = mt5.symbol_info_tick(symbol).ask
        for i in lines:
            if i < price:
                x.append(i)

        if len(x) == 0:
            return False
        else:
            return max(x)


def nadaraya_watson(symbol , tf, h=8.0, mult=3.0, src_col='close', candle_type = 'ca'):
    if candle_type == 'ca':
        df = candle(symbol, tf)
    else:
        df = heikin_ashi(symbol, tf)

    data = df.copy()
    def gaussian_weight(x, h):
        return np.exp(- (x ** 2) / (2 * h ** 2))

    src = data[src_col].values
    n = len(src)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    center = np.full(n, np.nan)
    cross_up = np.full(n, False)
    cross_down = np.full(n, False)

    
    nwe_vals = np.full(n, np.nan)
    start_idx = max(0, n - 500)
    sae_total = 0.0
    count = 0

    for i in range(start_idx, n):
        sum_w = 0.0
        sum_wx = 0.0
        for j in range(start_idx, n):
            w = gaussian_weight(i - j, h)
            sum_w += w
            sum_wx += src[j] * w
        if sum_w != 0:
            y = sum_wx / sum_w
            nwe_vals[i] = y
            sae_total += abs(src[i] - y)
            count += 1

        sae = (sae_total / count) * mult if count > 0 else 0.0

        for i in range(start_idx, n):
            center[i] = nwe_vals[i]
            if not np.isnan(center[i]):
                upper[i] = center[i] + sae
                lower[i] = center[i] - sae

    last_cross_up = -10
    last_cross_down = -10
    min_gap = 1

    for i in range(1, n):
        if not np.isnan(lower[i]) and src[i - 1] < lower[i - 1] and src[i] > lower[i]:
            if i - last_cross_up > min_gap:
                cross_up[i] = True
                last_cross_up = i

        if not np.isnan(upper[i]) and src[i - 1] > upper[i - 1] and src[i] < upper[i]:
            if i - last_cross_down > min_gap:
                cross_down[i] = True
                last_cross_down = i

    return {
        'center': center,
        'upper': upper,
        'lower': lower,
        'cross_up': cross_up,
        'cross_down': cross_down
    }



def time_high_low(symbol, start_hour_tv, start_minute_tv, timeframe_str, num_candles):
    
   
    TV_OFFSET_HOURS = 3 
    
    today = datetime.datetime.now(datetime.timezone.utc).date()

    start_time_naive = datetime.datetime(
        today.year, today.month, today.day, 
        start_hour_tv, start_minute_tv, 0, 
        tzinfo=datetime.timezone.utc
    )

    start_time_utc = start_time_naive + datetime.timedelta(hours=TV_OFFSET_HOURS)
    
    
    def parse_timeframe(timeframe_str):
        tf_map = {
            '1m': (mt5.TIMEFRAME_M1, 1), '3m': (mt5.TIMEFRAME_M3, 3), 
            '5m': (mt5.TIMEFRAME_M5, 5), '15m': (mt5.TIMEFRAME_M15, 15),
            '30m': (mt5.TIMEFRAME_M30, 30), '1h': (mt5.TIMEFRAME_H1, 60),
            '4h': (mt5.TIMEFRAME_H4, 240), '1d': (mt5.TIMEFRAME_D1, 1440),
            '1w': (mt5.TIMEFRAME_W1, 10080), '1mn': (mt5.TIMEFRAME_MN1, 43200)
        }
        return tf_map.get(timeframe_str.lower(), (None, None))

    timeframe, timeframe_minutes = parse_timeframe(timeframe_str)
    
    end_time_utc = start_time_utc + datetime.timedelta(minutes=timeframe_minutes * num_candles)

    rates = mt5.copy_rates_range(symbol, timeframe, start_time_utc, end_time_utc)

    data = pd.DataFrame(rates)
    data['time'] = pd.to_datetime(data['time'], unit='s', utc=True) 
    data = data.sort_values(by='time')

    selected_candles = data.head(num_candles)

    highest_point = selected_candles['high'].max()
    lowest_point = selected_candles['low'].min()

    return {
        'high': highest_point,
        'low': lowest_point
    }


def ut_bot(symbol , tf, key_value: int = 3, atr_period: int = 10 , candle_type = 'ca'):
    if candle_type == 'ca':
        df = candle(symbol, tf).copy()
    else:
        df = heikin_ashi(symbol, tf).copy()

    if not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        raise ValueError("دیتافریم ورودی باید شامل ستون‌های 'open', 'high', 'low', 'close' باشد.")

    df['xATR'] = pandas_ta.atr(df['high'], df['low'], df['close'], length=atr_period)
    df['nLoss'] = key_value * df['xATR']
    price_src = df['close']

    df['xATRTrailingStop'] = 0.0
    for i in range(1, len(df)):
        prev_stop = df.loc[df.index[i-1], 'xATRTrailingStop']
        if price_src.iloc[i] > prev_stop and price_src.iloc[i-1] > prev_stop:
            df.loc[df.index[i], 'xATRTrailingStop'] = max(prev_stop, price_src.iloc[i] - df.loc[df.index[i], 'nLoss'])
        elif price_src.iloc[i] < prev_stop and price_src.iloc[i-1] < prev_stop:
            df.loc[df.index[i], 'xATRTrailingStop'] = min(prev_stop, price_src.iloc[i] + df.loc[df.index[i], 'nLoss'])
        elif price_src.iloc[i] > prev_stop:
            df.loc[df.index[i], 'xATRTrailingStop'] = price_src.iloc[i] - df.loc[df.index[i], 'nLoss']
        else:
            df.loc[df.index[i], 'xATRTrailingStop'] = price_src.iloc[i] + df.loc[df.index[i], 'nLoss']

    ema = price_src.ewm(span=1, adjust=False).mean()
    above = (ema.shift(1) < df['xATRTrailingStop'].shift(1)) & (ema > df['xATRTrailingStop'])
    below = (ema.shift(1) > df['xATRTrailingStop'].shift(1)) & (ema < df['xATRTrailingStop'])
    buy_signal_points = (price_src > df['xATRTrailingStop']) & above
    sell_signal_points = (price_src < df['xATRTrailingStop']) & below

    df['signal_state'] = pd.Series(dtype='object')
    
    df.loc[buy_signal_points, 'signal_state'] = 'long'
    df.loc[sell_signal_points, 'signal_state'] = 'short'
    
    df['signal_state'] = df['signal_state'].ffill()

    df['signal_state'] = df['signal_state'].fillna('No Signal')
    
    signal_list = df['signal_state'].tolist()
    
    return signal_list


def supertrend(symbol , tf, atr_period=10, multiplier=3.0 , candle_type = 'ha'):
    if candle_type == 'ca':
        df = candle(symbol, tf).copy()
    else:
        df = heikin_ashi(symbol, tf).copy()
    def rma(series, length):
        result = [np.nan] * len(series)
        for i in range(len(series)):
            if i == 0:
                result[i] = series.iloc[i]
            else:
                result[i] = (result[i-1] * (length - 1) + series.iloc[i]) / length
        return pd.Series(result, index=series.index)

    df = df.copy()
    change_atr_method=True
    hl2 = (df['high'] + df['low']) / 2

    tr0 = df['high'] - df['low']
    tr1 = abs(df['high'] - df['close'].shift(1))
    tr2 = abs(df['low'] - df['close'].shift(1))
    tr = pd.concat([tr0, tr1, tr2], axis=1).max(axis=1)
    atr = rma(tr, atr_period) if change_atr_method else tr.rolling(atr_period).mean()

    up_list = []
    dn_list = []
    trend_list = []
    supertrend_list = []
    position_list = []
    signal_list = []

    prev_up = 0
    prev_dn = 0
    prev_trend = 1

    for i in range(len(df)):
        if np.isnan(atr.iloc[i]):
            up_list.append(np.nan)
            dn_list.append(np.nan)
            trend_list.append(prev_trend)
            supertrend_list.append(np.nan)
            position_list.append(None)
            signal_list.append(None)
            continue

        up = hl2.iloc[i] - multiplier * atr.iloc[i]
        dn = hl2.iloc[i] + multiplier * atr.iloc[i]

        if i > 0:
            if df['close'].iloc[i - 1] > prev_up:
                up = max(up, prev_up)
        prev_up = up

        if i > 0:
            if df['close'].iloc[i - 1] < prev_dn:
                dn = min(dn, prev_dn)
        prev_dn = dn

        if prev_trend == -1 and df['close'].iloc[i] > prev_dn:
            curr_trend = 1
        elif prev_trend == 1 and df['close'].iloc[i] < prev_up:
            curr_trend = -1
        else:
            curr_trend = prev_trend

        prev_trend = curr_trend
        trend_list.append(curr_trend)

        supertrend = up if curr_trend == 1 else dn
        supertrend_list.append(supertrend)

        position = 'long' if curr_trend == 1 else 'short'
        position_list.append(position)

        if i == 0:
            signal = None
        elif trend_list[i] == 1 and trend_list[i-1] == -1:
            signal = 'buy'
        elif trend_list[i] == -1 and trend_list[i-1] == 1:
            signal = 'sell'
        else:
            signal = 'hold'
        signal_list.append(signal)

    return {
        'value': supertrend_list,
        'position': position_list,
        'signal': signal_list
    }

  
def trend_alert(symbol, high_tf, low_tf):
        
    def candle_index(smaller_tf: str, larger_tf: str, candle_offset: int):

        timeframe_mapping = {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "90m" : 90,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "1d": 1440,
        "1w": 10080
        }

        def get_forex_open_time():
            
            now = datetime.datetime.now(datetime.timezone.utc)
            forex_open = now.replace(hour=22, minute=0, second=0, microsecond=0)
            if now < forex_open:
                forex_open -= datetime.timedelta(days=1)
            return forex_open
        
        smaller_tf = timeframe_mapping[smaller_tf]
        larger_tf = timeframe_mapping[larger_tf]
        
        forex_open = get_forex_open_time()
        now = datetime.datetime.now(datetime.timezone.utc)
        
        elapsed_time = now - forex_open
        small_tf_candles = int(elapsed_time.total_seconds() // (smaller_tf * 60))
        large_tf_candles = int(elapsed_time.total_seconds() // (larger_tf * 60))
        
        if candle_offset < 0:
            target_small_candle = small_tf_candles + candle_offset
        else:
            target_small_candle = candle_offset
        
        target_large_candle = target_small_candle // (larger_tf // smaller_tf)
        
        if candle_offset < 0:
            target_large_candle = target_large_candle - large_tf_candles - 1
        
        return target_large_candle

  
    high_tf_df = heikin_ashi(symbol ,high_tf , 100 ).copy()
    low_tf_df =  heikin_ashi(symbol ,low_tf , 100 ).copy()

    def ema(df, period):
        return df['close'].ewm(span=period, adjust=False).mean()

    ema_values = ema(low_tf_df, 20)
    signals = []

    for i in range(1,100) :

        delta = ema_values.diff().iloc[-i]
        hi_index = candle_index(low_tf , high_tf , -i)

        if (high_tf_df.iloc[hi_index]['open'] < high_tf_df.iloc[hi_index]['close'] and
            low_tf_df.iloc[-i]['open'] < low_tf_df.iloc[-i]['close'] and
            low_tf_df.iloc[-i]['close'] > ema_values.iloc[-i] and
            delta > 0):
            signals.append('long')
        elif (high_tf_df.iloc[hi_index]['open'] > high_tf_df.iloc[hi_index]['close'] and
            low_tf_df.iloc[-i]['open'] > low_tf_df.iloc[-i]['close'] and
            low_tf_df.iloc[-i]['close'] < ema_values.iloc[-i] and
            delta < 0):
            signals.append('short')
        else:
            signals.append('neutral')

    return signals[::-1]


def Atr(symbol , tf, period=14 , candle_type = 'ca'):
    if candle_type == 'ca':
        data = candle(symbol, tf).copy()
    else:
        data = heikin_ashi(symbol, tf).copy()
    df = data.copy()
    df['ATR'] = pandas_ta.atr(df['high'], df['low'], df['close'], period)
    return df['ATR'].values
     

def stochrsi(symbol , tf , line='blue' , rsi_length=14, stoch_length=14, k_period=3, d_period=3 , candle_type='ca'):
    if candle_type == 'ca':
        candles = candle(symbol, tf ).copy()
    else:
        candles = heikin_ashi(symbol, tf ).copy()
    df_close = candles['close']
    stoch_rsi = pandas_ta.stochrsi(df_close, length=stoch_length, rsi_length=rsi_length, k=k_period, d=d_period)

    d = stoch_rsi['STOCHRSId_' + str(rsi_length) + '_' + str(stoch_length) + '_' + str(k_period) + '_' + str(d_period)].tolist()
    k = stoch_rsi['STOCHRSIk_' + str(rsi_length) + '_' + str(stoch_length) + '_' + str(k_period) + '_' + str(d_period)].tolist()
    
    return k if line == 'blue' else d


def ssl_hybrid(symbol, tf,candle_type = 'ca' ,baseline_type="HMA", baseline_length=60,ssl2_type="JMA", ssl2_length=5,exit_type="HMA", exit_length=15,atr_period=14, atr_mult=1.0, atr_smoothing="WMA",risk_lookback=100, risk_sensitivity=2):

    if candle_type == 'ca':
        df = candle(symbol, tf, 500).copy()
    else:
        df = heikin_ashi(symbol, tf, 500).copy()
    def ma(ma_type, series, length, jurik_phase=3, jurik_power=1):
        if ma_type == "SMA":
            return series.rolling(length).mean()
        elif ma_type == "EMA":
            return series.ewm(span=length, adjust=False).mean()
        elif ma_type == "WMA":
            weights = np.arange(1, length+1)
            return series.rolling(length).apply(lambda x: np.dot(x, weights)/weights.sum(), raw=True)
        elif ma_type == "DEMA":
            e = series.ewm(span=length, adjust=False).mean()
            return 2*e - e.ewm(span=length, adjust=False).mean()
        elif ma_type == "TEMA":
            e1 = series.ewm(span=length, adjust=False).mean()
            e2 = e1.ewm(span=length, adjust=False).mean()
            e3 = e2.ewm(span=length, adjust=False).mean()
            return 3*(e1 - e2) + e3
        elif ma_type == "HMA":
            half = ma("WMA", series, int(length/2))
            full = ma("WMA", series, length)
            raw = 2*half - full
            return ma("WMA", raw, int(np.sqrt(length)))
        elif ma_type == "McGinley":
            mg = series.copy()
            for i in range(1, len(series)):
                mg.iloc[i] = mg.iloc[i-1] + (series.iloc[i] - mg.iloc[i-1]) / (length * ((series.iloc[i]/mg.iloc[i-1])**4))
            return mg
        elif ma_type == "JMA":
            phase_ratio = 0.5 if jurik_phase < -100 else 2.5 if jurik_phase > 100 else jurik_phase/100 + 1.5
            beta = 0.45*(length-1)/(0.45*(length-1)+2)
            alpha = beta**jurik_power
            jma = pd.Series(index=series.index, dtype=float)
            e0 = pd.Series(index=series.index, dtype=float)
            e1 = pd.Series(index=series.index, dtype=float)
            e2 = pd.Series(index=series.index, dtype=float)
            for i in range(len(series)):
                if i == 0:
                    e0.iloc[i] = series.iloc[i]
                    e1.iloc[i] = 0
                    e2.iloc[i] = 0
                    jma.iloc[i] = series.iloc[i]
                else:
                    e0.iloc[i] = (1-alpha)*series.iloc[i] + alpha*e0.iloc[i-1]
                    e1.iloc[i] = (series.iloc[i]-e0.iloc[i])*(1-beta) + beta*e1.iloc[i-1]
                    e2.iloc[i] = (e0.iloc[i] + phase_ratio*e1.iloc[i] - jma.iloc[i-1])*(1-alpha)**2 + (alpha**2)*e2.iloc[i-1]
                    jma.iloc[i] = e2.iloc[i] + jma.iloc[i-1]
            return jma
        else:
            return series

    def rma(series, length):
        alpha = 1/length
        r = series.copy()
        for i in range(1, len(series)):
            r.iloc[i] = alpha*series.iloc[i] + (1-alpha)*r.iloc[i-1]
        return r

    tr = np.maximum(df['high'] - df['low'], 
                    np.maximum(abs(df['high'] - df['close'].shift(1)), 
                               abs(df['low'] - df['close'].shift(1))))
    if atr_smoothing == "RMA":
        df['atr'] = rma(tr, atr_period)
    elif atr_smoothing == "SMA":
        df['atr'] = tr.rolling(atr_period).mean()
    elif atr_smoothing == "EMA":
        df['atr'] = tr.ewm(span=atr_period, adjust=False).mean()
    else:
        df['atr'] = ma("WMA", tr, atr_period)

    df['atr+'] = df['close'] + atr_mult*df['atr']
    df['atr-'] = df['close'] - atr_mult*df['atr']

    df['baseline'] = ma(baseline_type, df['close'], baseline_length)
    rangema = ma("EMA", tr, baseline_length)
    df['upperk'] = df['baseline'] + rangema*0.2
    df['lowerk'] = df['baseline'] - rangema*0.2

    emaHigh = ma(baseline_type, df['high'], baseline_length)
    emaLow = ma(baseline_type, df['low'], baseline_length)
    Hlv = np.zeros(len(df))
    for i in range(1, len(df)):
        if df['close'].iloc[i] > emaHigh.iloc[i]:
            Hlv[i] = 1
        elif df['close'].iloc[i] < emaLow.iloc[i]:
            Hlv[i] = -1
        else:
            Hlv[i] = Hlv[i-1]
    df['ssl1'] = np.where(Hlv < 0, emaHigh, emaLow)

    maHigh = ma(ssl2_type, df['high'], ssl2_length)
    maLow  = ma(ssl2_type, df['low'], ssl2_length)
    Hlv2 = np.zeros(len(df))
    for i in range(1, len(df)):
        if df['close'].iloc[i] > maHigh.iloc[i]:
            Hlv2[i] = 1
        elif df['close'].iloc[i] < maLow.iloc[i]:
            Hlv2[i] = -1
        else:
            Hlv2[i] = Hlv2[i-1]
    df['ssl2'] = np.where(Hlv2 < 0, maHigh, maLow)

    # --- Exit line ---
    ExitHigh = ma(exit_type, df['high'], exit_length)
    ExitLow  = ma(exit_type, df['low'], exit_length)
    Hlv3 = np.zeros(len(df))
    for i in range(1, len(df)):
        if df['close'].iloc[i] > ExitHigh.iloc[i]:
            Hlv3[i] = 1
        elif df['close'].iloc[i] < ExitLow.iloc[i]:
            Hlv3[i] = -1
        else:
            Hlv3[i] = Hlv3[i-1]
    df['sslExit'] = np.where(Hlv3 < 0, ExitHigh, ExitLow)

    atr_percentile = df['atr'].rank(pct=True)*100
    adjusted = (atr_percentile/100)**risk_sensitivity * 100
    risk_level = np.where(adjusted > 75, "High", np.where(adjusted < 25, "Low", "Normal"))
    distance_from_baseline = abs(df['close'] - df['baseline'])/df['atr']
    entry_distance = np.where(distance_from_baseline < 1, "Near",
                              np.where(distance_from_baseline < 2, "Extended", "Far"))

    bullish_color = "blue"
    bearish_color = "red"
    neutral_color = "gray"

    df['baseline_color'] = np.where(
        df['close'] > df['upperk'], bullish_color,
        np.where(df['close'] < df['lowerk'], bearish_color, neutral_color)
    )
    df['ssl1_color'] = np.where(
        df['close'] > df['ssl1'], bullish_color,
        np.where(df['close'] < df['ssl1'], bearish_color, neutral_color)
    )
    df['ssl2_color'] = np.where(
        df['close'] > df['ssl2'], bullish_color,
        np.where(df['close'] < df['ssl2'], bearish_color, neutral_color)
    )
    df['exit_color'] = np.where(
        df['close'] > df['sslExit'], bullish_color,
        np.where(df['close'] < df['sslExit'], bearish_color, neutral_color)
    )

    return {
        "atr+": df['atr+'].tolist(),
        "atr-": df['atr-'].tolist(),
        "baseline": df['baseline'].tolist(),
        "baseline_color": df['baseline_color'].tolist(),
        "ssl1": df['ssl1'].tolist(),
        "ssl1_color": df['ssl1_color'].tolist(),
        "ssl2": df['ssl2'].tolist(),
        "ssl2_color": df['ssl2_color'].tolist(),
        "sslExit": df['sslExit'].tolist(),
        "exit_color": df['exit_color'].tolist(),
        "upperk": df['upperk'].tolist(),
        "lowerk": df['lowerk'].tolist(),
        "risk_level": risk_level.tolist(),
        "entry_distance": entry_distance.tolist(),
        "atr_percentile": atr_percentile.tolist()
    }



def ichimoku(symbol, tf, conversion_line=9, base_line=26, lagging_span=26, leading_b_period=52 , candle_type = 'ca'):
    if candle_type == 'ca':
        df = candle(symbol, tf, 500).copy()
    else:
        df = heikin_ashi(symbol, tf, 500).copy()
    

    def kijun_sen(data, period):
        high = data['high']
        low = data['low']
        return (high.rolling(window=period).max() + low.rolling(window=period).min()) / 2

    tenkan_sen = kijun_sen(df, conversion_line)
    kijun_sen_line = kijun_sen(df, base_line)
    leading_span_a = (tenkan_sen + kijun_sen_line) / 2
    leading_span_b = kijun_sen(df, leading_b_period)
    lagging = df['close'].shift(-lagging_span)
    
    upper_kumo = leading_span_a.combine(leading_span_b, max)
    lower_kumo = leading_span_a.combine(leading_span_b, min)

    cloud_color = [
        "green" if a > b else "red"
        for a, b in zip(leading_span_a.fillna(0), leading_span_b.fillna(0))
    ]

    return {
        'conversion_line': tenkan_sen.tolist(),
        'baseline': kijun_sen_line.tolist(),
        'leading_span_a': leading_span_a.tolist(),
        'leading_span_b': leading_span_b.tolist(),
        'lagging_span': lagging.tolist(),
        'upper_kumo': upper_kumo.tolist(),
        'lower_kumo': lower_kumo.tolist(),
        'cloud': cloud_color
    }


def kalman_trend_levels(symbol, tf, short_len=50, long_len=150):
    
    ha_data = heikin_ashi(symbol, tf, max(short_len, long_len) * 2).copy()
    
    def kalman_filter(src, length, R=0.01, Q=0.1):
        estimate = src.copy()
        error_est = np.ones(len(src))
        error_meas = R * length
        
        for i in range(1, len(src)):
            prediction = estimate[i-1]
            
            kalman_gain = error_est[i-1] / (error_est[i-1] + error_meas)
            
            estimate[i] = prediction + kalman_gain * (src[i] - prediction)
            
            error_est[i] = (1 - kalman_gain) * error_est[i-1] + Q/length
            
        return estimate
    
    closes = ha_data['close'].values
    short_kalman = kalman_filter(closes, short_len)
    long_kalman = kalman_filter(closes, long_len)
    
    return {
        'short_kalman': short_kalman.tolist(),
        'long_kalman': long_kalman.tolist(),
        'trend': ['long' if s > l else 'short' for s,l in zip(short_kalman, long_kalman)]
    }
    

def half_trend(symbol, tf, amplitude=2, channel_deviation=2, candle_type='ca'):
    
    if candle_type == 'ca':
        df = candle(symbol, tf, amplitude * 20).copy()
    else:
        df = heikin_ashi(symbol, tf, amplitude * 20).copy()
    
   
    df['high_price'] = df['high'].rolling(window=amplitude).max()
    df['low_price'] = df['low'].rolling(window=amplitude).min()

    df['TR'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low'] - df['close'].shift(1)).abs()
        )
    )

    df['ATR'] = df['TR'].rolling(window=100).mean() / 2
    df['Dev'] = channel_deviation * df['ATR']

    df['high_ma'] = df['high'].rolling(window=amplitude).mean()
    df['low_ma'] = df['low'].rolling(window=amplitude).mean()

    df['trend'] = np.nan
    df['next_trend'] = np.nan
    df['max_low_price'] = np.nan
    df['min_high_price'] = np.nan
    df['up'] = np.nan
    df['down'] = np.nan
    df['HalfTrend'] = np.nan

    trend = 0
    next_trend = 0
    
 
    max_low_price = df['low'].iloc[0]
    min_high_price = df['high'].iloc[0]
    up = 0.0
    down = 0.0

    for i in range(len(df)):
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        
        prev_low = df['low'].iloc[i-1] if i > 0 else df['low'].iloc[0]
        prev_high = df['high'].iloc[i-1] if i > 0 else df['high'].iloc[0]

        high_price = df['high_price'].iloc[i]
        low_price = df['low_price'].iloc[i]
        high_ma = df['high_ma'].iloc[i]
        low_ma = df['low_ma'].iloc[i]
        atr = df['ATR'].iloc[i]
        dev = df['Dev'].iloc[i]

        if next_trend == 1:
            max_low_price = max(low_price, max_low_price)
            if high_ma < max_low_price and current_close < prev_low:
                trend = 1
                next_trend = 0
                min_high_price = high_price
        else:
            min_high_price = min(high_price, min_high_price)
            if low_ma > min_high_price and current_close > prev_high:
                trend = 0
                next_trend = 1
                max_low_price = low_price

        df.at[i, 'trend'] = trend
        df.at[i, 'next_trend'] = next_trend
        df.at[i, 'max_low_price'] = max_low_price
        df.at[i, 'min_high_price'] = min_high_price

        if trend == 0:
            if i > 0 and df['trend'].iloc[i-1] != 0:
                up = df['down'].iloc[i-1]
            else:
                up = df['up'].iloc[i-1] if i > 0 and not np.isnan(df['up'].iloc[i-1]) else max_low_price
                up = max(up, max_low_price)
            df.at[i, 'up'] = up
            df.at[i, 'HalfTrend'] = up
        else:
            if i > 0 and df['trend'].iloc[i-1] != 1:
                down = df['up'].iloc[i-1]
            else:
                down = df['down'].iloc[i-1] if i > 0 and not np.isnan(df['down'].iloc[i-1]) else min_high_price
                down = min(down, min_high_price)
            df.at[i, 'down'] = down
            df.at[i, 'HalfTrend'] = down

    
    df['buy_signal'] = (df['trend'] == 0) & (df['trend'].shift(1) == 1)
    df['sell_signal'] = (df['trend'] == 1) & (df['trend'].shift(1) == 0)

    positions = ['long' if trend == 0 else 'short' for trend in df['trend']]
    return positions


def ravand(symbol , tf):
    first = trend_alert(symbol , '1h' , tf)[-1]
    sec = heikin_ashi(symbol , '18m' , 3)[-1]
    if sec['close'] > sec['open'] and first == 'long':
        return 'long'
    elif sec['close'] < sec['open'] and first == 'short':
        return 'short'
    else:
        return False
    

def Trend_change_signal(trend):
    if trend[-2] == 'long' and trend[-3] == 'short' :
        return 'buy'
    elif trend[-2] == 'short' and trend[-3] == 'long' :
        return 'sell'
    else:
        return 'hold'

def Trend_change_signal_at(trends, idx=-2):
    # idx=-2 یعنی کندل بسته‌شده
    if not isinstance(trends, (list, tuple)) or len(trends) < 3:
        return 'hold'
    if abs(idx) > len(trends)-1:
        return 'hold'

    curr = trends[idx]
    prev = trends[idx-1]   # یک کندل قبل از آن (برای idx=-2 می‌شود -3)

    if curr == 'long' and prev == 'short':
        return 'buy'
    if curr == 'short' and prev == 'long':
        return 'sell'
    return 'hold'

def fibo(high , low, trend = 'up') -> dict:
    
    levels = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
    precision = 2

    t = str(trend).strip().lower()
   
    span = abs(high - low)
    level_prices = {}
    for lvl in levels:
        key = str(int(round(lvl * 1000)))
        price = (high - span * lvl) if t == 'up' else (low + span * lvl)
        level_prices[key] = round(price, precision)

    return level_prices


def tokyo_vol(symbol):

    range = time_high_low(symbol, 0, 0, '1h' , 8)

    return range['high'] - range['low']


def london_vol(symbol):

    range = time_high_low(symbol, 7, 0, '1h' , 8)

    return range['high'] - range['low']


def winRate(symbol , tf , type ='buy'):
    win = 50
    if check_time(8,15)  :
        win += 20
    else:
        win -= 20

    if macd(symbol , tf , 25 , 40)['histogram'][-1] > 0 :
        if type == 'buy':
            win += 10

    else :
        if type == 'sell':
            win += 10

    if supertrend(symbol , tf ,10 , 2 , 'ha')['position'][-1] == 'long':
        if type == 'buy':
            win += 10

    else :
        if type == 'sell':
            win += 10

    if check_candle(symbol , '18m' , -1 , 'ha') == 'long':
        if type == 'buy':
            win += 5

    else :
        if type == 'sell':
            win += 5
    if rsi(symbol , tf )[-1] > 70 and type == 'buy':
        win -= 10
    if rsi(symbol , tf )[-1] < 30 and type == 'sell':
        win -= 10
    if win < 10 :
        return 10
    elif win > 90 :
        return 90
    else:
        return win


def smartTrend(symbol , tf):
    if check_candle(symbol , '18m' , -1 , 'ha') == 'long' or winRate(symbol , tf , 'buy') > 70:
        return 'long'
    elif check_candle(symbol , '18m' , -1 , 'ha') == 'short' or winRate(symbol , tf , 'sell') > 70:
        return 'short'
    else:
        False


def zigzag(symbol, tf, depth=12, deviation=5, backstep=3):
    
    df_result = candle(symbol, tf, limit=300)
    
    if hasattr(df_result, '__call__'):
        df = df_result[:] 
    else:
        df = df_result
    
    high = df['high'].tolist()
    low = df['low'].tolist()
    rates_total = len(high)
    
    symbol_info = mt5.symbol_info(symbol)
    point = symbol_info.point if symbol_info else 0.0001
    
    zigzag_peaks = [0.0] * rates_total
    zigzag_bottoms = [0.0] * rates_total
    high_map = [0.0] * rates_total
    low_map = [0.0] * rates_total
    
    last_high, last_low = 0.0, 0.0
    last_high_pos, last_low_pos = 0, 0
    extreme_search = 0
    start = depth - 1
    
    for shift in range(start, rates_total):
        val_low = min(low[shift - depth + 1:shift + 1])
        if val_low != last_low:
            last_low = val_low
            if (low[shift] - val_low) <= (deviation * point):
                for back in range(backstep, 0, -1):
                    if shift - back >= 0 and low_map[shift - back] > val_low:
                        low_map[shift - back] = 0.0
                low_map[shift] = val_low if low[shift] == val_low else 0.0
        
        val_high = max(high[shift - depth + 1:shift + 1])
        if val_high != last_high:
            last_high = val_high
            if (val_high - high[shift]) <= (deviation * point):
                for back in range(backstep, 0, -1):
                    if shift - back >= 0 and high_map[shift - back] < val_high:
                        high_map[shift - back] = 0.0
                high_map[shift] = val_high if high[shift] == val_high else 0.0
    
    for shift in range(start, rates_total):
        if extreme_search == 0:
            if high_map[shift] != 0:
                last_high, last_high_pos, extreme_search = high[shift], shift, -1
                zigzag_peaks[shift] = last_high
            elif low_map[shift] != 0:
                last_low, last_low_pos, extreme_search = low[shift], shift, 1
                zigzag_bottoms[shift] = last_low
        elif extreme_search == 1:
            if low_map[shift] != 0 and low_map[shift] < last_low and high_map[shift] == 0:
                zigzag_bottoms[last_low_pos] = 0.0
                last_low_pos, last_low = shift, low_map[shift]
                zigzag_bottoms[shift] = last_low
            if high_map[shift] != 0 and low_map[shift] == 0:
                last_high, last_high_pos, extreme_search = high_map[shift], shift, -1
                zigzag_peaks[shift] = last_high
        elif extreme_search == -1:
            if high_map[shift] != 0 and high_map[shift] > last_high and low_map[shift] == 0:
                zigzag_peaks[last_high_pos] = 0.0
                last_high_pos, last_high = shift, high_map[shift]
                zigzag_peaks[shift] = last_high
            if low_map[shift] != 0 and high_map[shift] == 0:
                last_low, last_low_pos, extreme_search = low_map[shift], shift, 1
                zigzag_bottoms[shift] = last_low
    
    highs = {}
    lows = {}
    
    for i in range(rates_total):
        relative_index = -(rates_total - 1 - i)
        if zigzag_peaks[i] != 0:
            highs[len(highs)] = {"price": zigzag_peaks[i], "candle_index": relative_index}
        if zigzag_bottoms[i] != 0:
            lows[len(lows)] = {"price": zigzag_bottoms[i], "candle_index": relative_index}
    
    highs = {len(highs) - 1 - k: v for k, v in highs.items()}
    lows = {len(lows) - 1 - k: v for k, v in lows.items()}
    
    return {"high": highs, "low": lows}


def Trend_Indicator_A(symbol, tf, ma_type="EMA", ma_period=9, alma_sigma=6, candle_type = 'ha'):
    if candle_type == 'ca':
        ha_df = candle(symbol, tf,500).copy()
    else:
        ha_df = heikin_ashi(symbol, tf, 500).copy()

    if ma_type == "ALMA":
        m = np.floor(0.5 * (ma_period - 1))
        s = ma_period / alma_sigma
        w = np.exp(-((np.arange(ma_period) - m)**2) / (2 * s**2))
        
        def apply_alma(series):
            alma = np.convolve(series, w / w.sum(), mode='valid')
            return pd.Series(alma, index=series.index[ma_period-1:])
        
        ha_df['MA_Open'] = apply_alma(ha_df['open'])
        ha_df['MA_Close'] = apply_alma(ha_df['close'])
        ha_df['MA_High'] = apply_alma(ha_df['high'])
        ha_df['MA_Low'] = apply_alma(ha_df['low'])
    
    elif ma_type == "HMA":
        def apply_hma(series):
            wma_half = series.rolling(window=ma_period//2).mean()
            wma_full = series.rolling(window=ma_period).mean()
            hma = 2 * wma_half - wma_full
            return hma.rolling(window=int(np.sqrt(ma_period))).mean()
        
        ha_df['MA_Open'] = apply_hma(ha_df['open'])
        ha_df['MA_Close'] = apply_hma(ha_df['close'])
        ha_df['MA_High'] = apply_hma(ha_df['high'])
        ha_df['MA_Low'] = apply_hma(ha_df['low'])
    
    elif ma_type == "SMA":
        ha_df['MA_Open'] = ha_df['open'].rolling(window=ma_period).mean()
        ha_df['MA_Close'] = ha_df['close'].rolling(window=ma_period).mean()
        ha_df['MA_High'] = ha_df['high'].rolling(window=ma_period).mean()
        ha_df['MA_Low'] = ha_df['low'].rolling(window=ma_period).mean()
    
    elif ma_type == "VWMA" or ma_type == "WMA":
        weights = np.arange(1, ma_period + 1)
        
        ha_df['MA_Open'] = ha_df['open'].rolling(window=ma_period).apply(
            lambda x: np.dot(x, weights) / weights.sum())
        ha_df['MA_Close'] = ha_df['close'].rolling(window=ma_period).apply(
            lambda x: np.dot(x, weights) / weights.sum())
        ha_df['MA_High'] = ha_df['high'].rolling(window=ma_period).apply(
            lambda x: np.dot(x, weights) / weights.sum())
        ha_df['MA_Low'] = ha_df['low'].rolling(window=ma_period).apply(
            lambda x: np.dot(x, weights) / weights.sum())
    
    elif ma_type == "ZLEMA":
        lag = (ma_period - 1) // 2
        
        def apply_zlema(series):
            return series + (series - series.shift(lag)).ewm(span=ma_period, adjust=False).mean()
        
        ha_df['MA_Open'] = apply_zlema(ha_df['open'])
        ha_df['MA_Close'] = apply_zlema(ha_df['close'])
        ha_df['MA_High'] = apply_zlema(ha_df['high'])
        ha_df['MA_Low'] = apply_zlema(ha_df['low'])
    
    elif ma_type == "EMA":
        ha_df['MA_Open'] = ha_df['open'].ewm(span=ma_period, adjust=False).mean()
        ha_df['MA_Close'] = ha_df['close'].ewm(span=ma_period, adjust=False).mean()
        ha_df['MA_High'] = ha_df['high'].ewm(span=ma_period, adjust=False).mean()
        ha_df['MA_Low'] = ha_df['low'].ewm(span=ma_period, adjust=False).mean()
    
    else:
        raise ValueError("نوع MA معتبر نیست!")

    ha_df['Trend'] = 100 * (ha_df['MA_Close'] - ha_df['MA_Open']) / (ha_df['MA_High'] - ha_df['MA_Low'])
    
    signals = np.where(ha_df['Trend'] > 0, 'long', 'short')

    return signals


def deviation_trend_signals(symbol, tf, sma_length=50 , candle_type = 'ca'):
    
    if candle_type == 'ca':
        df = candle(symbol, tf,5000).copy()
    else:
        df = heikin_ashi(symbol, tf, 5000).copy()

    df = df.reset_index(drop=True)
    df['avg'] = df['close'].rolling(window=sma_length).mean()
    df['avg_diff'] = df['avg'] - df['avg'].shift(5)
    df['avg_col'] = df['avg_diff'] / df['avg_diff'].rolling(window=500).quantile(1.0)
    trends = [0] * len(df)
    positions = ['short'] * len(df) 
    
    for i in range(1, len(df)):
        prev_trend = trends[i-1]
        
        if (df['avg_col'].iloc[i] > 0.1 and 
            df['avg_col'].iloc[i-1] <= 0.1 and 
            prev_trend == 0):
            trends[i] = 1
            positions[i] = 'long'
            
        elif (df['avg_col'].iloc[i] < -0.1 and 
              df['avg_col'].iloc[i-1] >= -0.1 and 
              prev_trend == 1):
            trends[i] = 0
            positions[i] = 'short'
        
        else:
            trends[i] = prev_trend
            positions[i] = 'long' if prev_trend == 1 else 'short'
    
    return positions
    

def volumatic_vidya(symbol, tf, vidya_length=10, vidya_momentum=20, band_distance=2, value='trend', candle_type='ca'):
    
    if candle_type == 'ca':
        data = candle(symbol, tf, 5000).copy()
    else:
        data = heikin_ashi(symbol, tf, 5000).copy()
    
    def vidya_calc(data, vidya_length, vidya_momentum):
        momentum = data['close'].diff()
        sum_pos_momentum = momentum.where(momentum >= 0, 0).rolling(vidya_momentum).sum()
        sum_neg_momentum = (-momentum).where(momentum < 0, 0).rolling(vidya_momentum).sum()
        total_momentum = sum_pos_momentum + sum_neg_momentum
        abs_cmo = np.abs(100 * (sum_pos_momentum - sum_neg_momentum) / total_momentum.replace(0, np.nan))
        abs_cmo = abs_cmo.fillna(0)
        alpha = 2 / (vidya_length + 1)
        vidya = pd.Series(index=data.index, dtype='float64')
        vidya.iloc[0] = data['close'].iloc[0]
        for i in range(1, len(data)):
            vidya.iloc[i] = (alpha * abs_cmo.iloc[i] / 100 * data['close'].iloc[i] +
                            (1 - alpha * abs_cmo.iloc[i] / 100) * vidya.iloc[i-1])
        return vidya.rolling(15).mean().ffill()
    
    vidya = vidya_calc(data, vidya_length, vidya_momentum)
    
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.rolling(200).mean()  
    
    upper_band = vidya + atr * band_distance
    lower_band = vidya - atr * band_distance
    
    trend = pd.Series(index=data.index, dtype='object')
    smoothed_value = pd.Series(index=data.index, dtype='float64')
    is_trend_up = False
    
    for i in range(1, len(data)):
        crossover = (data['close'].iloc[i] > upper_band.iloc[i] and
                    data['close'].iloc[i-1] <= upper_band.iloc[i-1])
        crossunder = (data['close'].iloc[i] < lower_band.iloc[i] and
                     data['close'].iloc[i-1] >= lower_band.iloc[i-1])
        
        if crossover:
            is_trend_up = True
        elif crossunder:
            is_trend_up = False
        
        if is_trend_up:
            smoothed_value.iloc[i] = lower_band.iloc[i]
        else:
            smoothed_value.iloc[i] = upper_band.iloc[i]
        
        if i > 1:
            prev_trend_up = (smoothed_value.iloc[i-1] == lower_band.iloc[i-1])
            curr_trend_up = (smoothed_value.iloc[i] == lower_band.iloc[i])
            
            trend_cross_up = not prev_trend_up and curr_trend_up
            trend_cross_down = prev_trend_up and not curr_trend_up
            
            if trend_cross_up:
                trend.iloc[i] = 'long'
            elif trend_cross_down:
                trend.iloc[i] = 'short'
            else:
                trend.iloc[i] = trend.iloc[i-1] if pd.notna(trend.iloc[i-1]) else None
    
    if value == 'trend':
        return trend.tolist()
    elif value == 'line':
        return smoothed_value.tolist()
    else:
        raise ValueError("Use 'trend' or 'line'.")


def trend_magic(symbol, tf, cci_period=20, atr_period=5, atr_multiplier=1, candle_type='ca'):
    
    if candle_type == 'ca':
        ohlc = candle(symbol, tf, max(cci_period, atr_period) * 10)
    else:
        ohlc = heikin_ashi(symbol, tf, max(cci_period, atr_period) * 10)
    
    df = pd.DataFrame(ohlc[:])
    
    cci_values = cci(symbol, tf, cci_period, candle_type)
    
    atr_values = Atr(symbol, tf, atr_period, candle_type)
    
    min_len = min(len(cci_values), len(atr_values), len(df))
    df = df.tail(min_len).reset_index(drop=True)
    cci_values = cci_values[-min_len:]
    atr_values = atr_values[-min_len:]
    
    upT = df['low'].values - (atr_values * atr_multiplier)
    downT = df['high'].values + (atr_values * atr_multiplier)
    
    magic_trend = np.zeros(len(df))
    magic_trend[0] = upT[0]  
    
    for i in range(1, len(df)):
        if cci_values[i] >= 0: 
            if upT[i] < magic_trend[i-1]:
                magic_trend[i] = magic_trend[i-1]
            else:
                magic_trend[i] = upT[i]
        else:  
            if downT[i] > magic_trend[i-1]:
                magic_trend[i] = magic_trend[i-1]
            else:
                magic_trend[i] = downT[i]
    
    # تولید سیگنال‌ها
    signals = []
    for i in range(len(df)):
        if cci_values[i] >= 0:
            signals.append('long')
        else:
            signals.append('short')
    
    
    
    return {
        'magic_trend': magic_trend.tolist(),
        'signal': signals,
    }


def trend_ali(symbol, tf, length=60, length_mult=6.0, mode='Hma', candle_type='ca'):
 
    
    final_length = int(length * length_mult)
    
    if candle_type == 'ca':
        ohlc = candle(symbol, tf, final_length * 3)
    else:
        ohlc = heikin_ashi(symbol, tf, final_length * 3)
    
    def calc_wma(data, period):
        weights = np.arange(1, period + 1)
        wma_vals = []
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            wma_vals.append(np.sum(weights * window) / np.sum(weights))
        return np.array(wma_vals)
    
    def calc_ema(data, period):
        return pd.Series(data).ewm(span=period, adjust=False).mean().values
    
    def calc_hma(data, period):
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))
        wma_half = calc_wma(data, half_period)
        wma_full = calc_wma(data, period)
        min_len = min(len(wma_half), len(wma_full))
        raw_hma = 2 * wma_half[-min_len:] - wma_full[-min_len:]
        return calc_wma(raw_hma, sqrt_period)
    
    def calc_ehma(data, period):
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))
        ema_half = calc_ema(data, half_period)
        ema_full = calc_ema(data, period)
        min_len = min(len(ema_half), len(ema_full))
        raw_ehma = 2 * ema_half[-min_len:] - ema_full[-min_len:]
        return calc_ema(raw_ehma, sqrt_period)
    
    def calc_thma(data, period):
        period_3 = int(period / 3)
        period_2 = int(period / 2)
        wma_3 = calc_wma(data, period_3)
        wma_2 = calc_wma(data, period_2)
        wma_full = calc_wma(data, period * 2)
        min_len = min(len(wma_3), len(wma_2), len(wma_full))
        raw_thma = wma_3[-min_len:] * 3 - wma_2[-min_len:] - wma_full[-min_len:]
        return calc_wma(raw_thma, period * 2)
    
    df = pd.DataFrame(ohlc[:])
    close_prices = df['close'].values
    
    if mode == 'Hma':
        hull_values = calc_hma(close_prices, final_length)
    elif mode == 'Ehma':
        hull_values = calc_ehma(close_prices, final_length)
    elif mode == 'Thma':
        hull_values = calc_thma(close_prices, int(final_length / 2))
    else:
        raise ValueError("mode باید یکی از 'Hma', 'Ehma', یا 'Thma' باشد")
    
    signals = []
    for i in range(len(hull_values)):
        if i < 2:
            signals.append('NEUTRAL')
        else:
            if hull_values[i] > hull_values[i-2]:
                signals.append('long')
            else:
                signals.append('short')
    
    return {
    'trend': signals,
    'val': hull_values
    }




# smart money ----------------------

def detect_bos(symbol, tf):
    df = candle(symbol, tf, 5000)
    df = df.copy()
    
    L = df['low'].iloc[0]
    H = df['high'].iloc[0]
    idmLow = df['low'].iloc[0]
    idmHigh = df['high'].iloc[0]
    lastH = df['high'].iloc[0]
    lastL = df['low'].iloc[0]
    H_lastH = df['high'].iloc[0]
    L_lastHH = df['low'].iloc[0]
    H_lastLL = df['high'].iloc[0]
    L_lastL = df['low'].iloc[0]
    
    HBar = 0
    LBar = 0
    lastHBar = 0
    lastLBar = 0
    idmLBar = None
    idmHBar = None
    
    mnStrc = None
    prevMnStrc = None
    top = df['high'].iloc[0]
    bot = df['low'].iloc[0]
    bar = 0
    top_ = df['high'].iloc[0]
    bot_ = df['low'].iloc[0]
    bar_ = 0
    
    isPrevBos = None
    findIDM = False
    isBosUp = False
    isBosDn = False
    isCocUp = True
    isCocDn = True
    
    puHigh = []
    puHBar = []
    puLow = []
    puLBar = []
    arrLastH = []
    arrLastHBar = []
    arrLastL = []
    arrLastLBar = []
    
    bos_signals = []
    
    for i in range(len(df)):
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        close = df['close'].iloc[i]
        
        if high >= top and low <= bot:
            if mnStrc is not None:
                prevMnStrc = True if mnStrc else False
            
            if prevMnStrc:
                top_ = top
                bar_ = bar
            else:
                bot_ = bot
                bar_ = bar
            
            top = high
            bot = low
            bar = i
            mnStrc = None
        
        if high >= top and low > bot:
            if prevMnStrc and mnStrc is None:
                puHBar.append(bar_)
                puHigh.append(top_)
                puLBar.append(bar)
                puLow.append(bot)
            elif (not prevMnStrc and mnStrc is None) or not mnStrc:
                puLBar.append(bar)
                puLow.append(bot)
            
            top = high
            bot = low
            bar = i
            prevMnStrc = None
            mnStrc = True
        
        if high < top and low <= bot:
            if not prevMnStrc and mnStrc is None:
                puHBar.append(bar)
                puHigh.append(top)
                puLBar.append(bar_)
                puLow.append(bot_)
            elif (prevMnStrc and mnStrc is None) or mnStrc:
                puHBar.append(bar)
                puHigh.append(top)
            
            top = high
            bot = low
            bar = i
            prevMnStrc = None
            mnStrc = False
        
        if high >= H:
            H = high
            HBar = i
            L_lastHH = low
            if len(puLow) > 0:
                idmLow = puLow[-1]
                idmLBar = puLBar[-1]
        
        if low <= L:
            L = low
            LBar = i
            H_lastLL = high
            if len(puHigh) > 0:
                idmHigh = puHigh[-1]
                idmHBar = puHBar[-1]
        
        if findIDM and isCocUp and isBosUp:
            if low < idmLow:
                findIDM = False
                isBosUp = False
                L = low
                LBar = i
                lastH = H
                lastHBar = HBar
                arrLastH.append(lastH)
                arrLastHBar.append(lastHBar)
                arrLastL.append(lastL)
                arrLastLBar.append(lastLBar)
                if len(arrLastH) > 0:
                    H_lastH = arrLastH[-1]
        
        if findIDM and isCocDn and isBosDn:
            if high > idmHigh:
                findIDM = False
                isBosDn = False
                H = high
                HBar = i
                lastL = L
                lastLBar = LBar
                arrLastH.append(lastH)
                arrLastHBar.append(lastHBar)
                arrLastL.append(lastL)
                arrLastLBar.append(lastLBar)
                if len(arrLastL) > 0:
                    L_lastL = arrLastL[-1]
        
        if isCocDn and high > lastH:
            if close > lastH:
                findIDM = True
                isBosUp = True
                isCocUp = True
                isBosDn = False
                isCocDn = False
                isPrevBos = False
                if len(arrLastL) > 0:
                    L_lastL = arrLastL[-1]
        
        if isCocUp and low < lastL:
            if close < lastL:
                findIDM = True
                isBosUp = False
                isCocUp = False
                isBosDn = True
                isCocDn = True
                isPrevBos = False
                if len(arrLastH) > 0:
                    H_lastH = arrLastH[-1]
        
        if not findIDM and not isBosUp and isCocUp:
            if high > lastH:
                if close > lastH:
                    bos_signals.append({'index': (i - 5000), 'type': 'BOS_Up', 'price': lastH})
                    findIDM = True
                    isBosUp = True
                    isCocUp = True
                    isBosDn = False
                    isCocDn = False
                    isPrevBos = True
                    lastL = L
                    lastLBar = LBar
                    L_lastL = L
        
        if not findIDM and not isBosDn and isCocDn:
            if low < lastL:
                if close < lastL:
                    bos_signals.append({'index': (i - 5000), 'type': 'BOS_Down', 'price': lastL})
                    findIDM = True
                    isBosUp = False
                    isCocUp = False
                    isBosDn = True
                    isCocDn = True
                    isPrevBos = True
                    lastH = H
                    lastHBar = HBar
                    H_lastH = H
        
        if high > lastH:
            lastH = high
            lastHBar = i
        
        if low < lastL:
            lastL = low
            lastLBar = i
    
    return bos_signals

def detect_choch(symbol, tf):
    df = candle(symbol, tf, 5000)
    df = df.copy()
    
    L = df['low'].iloc[0]
    H = df['high'].iloc[0]
    idmLow = df['low'].iloc[0]
    idmHigh = df['high'].iloc[0]
    lastH = df['high'].iloc[0]
    lastL = df['low'].iloc[0]
    H_lastH = df['high'].iloc[0]
    L_lastHH = df['low'].iloc[0]
    H_lastLL = df['high'].iloc[0]
    L_lastL = df['low'].iloc[0]
    
    HBar = 0
    LBar = 0
    lastHBar = 0
    lastLBar = 0
    idmLBar = None
    idmHBar = None
    
    mnStrc = None
    prevMnStrc = None
    top = df['high'].iloc[0]
    bot = df['low'].iloc[0]
    bar = 0
    top_ = df['high'].iloc[0]
    bot_ = df['low'].iloc[0]
    bar_ = 0
    
    isPrevBos = None
    findIDM = False
    isBosUp = False
    isBosDn = False
    isCocUp = True
    isCocDn = True
    
    puHigh = []
    puHBar = []
    puLow = []
    puLBar = []
    arrLastH = []
    arrLastHBar = []
    arrLastL = []
    arrLastLBar = []
    
    choch_signals = []
    
    for i in range(len(df)):
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        close = df['close'].iloc[i]
        
        if high >= top and low <= bot:
            if mnStrc is not None:
                prevMnStrc = True if mnStrc else False
            
            if prevMnStrc:
                top_ = top
                bar_ = bar
            else:
                bot_ = bot
                bar_ = bar
            
            top = high
            bot = low
            bar = i
            mnStrc = None
        
        if high >= top and low > bot:
            if prevMnStrc and mnStrc is None:
                puHBar.append(bar_)
                puHigh.append(top_)
                puLBar.append(bar)
                puLow.append(bot)
            elif (not prevMnStrc and mnStrc is None) or not mnStrc:
                puLBar.append(bar)
                puLow.append(bot)
            
            top = high
            bot = low
            bar = i
            prevMnStrc = None
            mnStrc = True
        
        if high < top and low <= bot:
            if not prevMnStrc and mnStrc is None:
                puHBar.append(bar)
                puHigh.append(top)
                puLBar.append(bar_)
                puLow.append(bot_)
            elif (prevMnStrc and mnStrc is None) or mnStrc:
                puHBar.append(bar)
                puHigh.append(top)
            
            top = high
            bot = low
            bar = i
            prevMnStrc = None
            mnStrc = False
        
        if high >= H:
            H = high
            HBar = i
            L_lastHH = low
            if len(puLow) > 0:
                idmLow = puLow[-1]
                idmLBar = puLBar[-1]
        
        if low <= L:
            L = low
            LBar = i
            H_lastLL = high
            if len(puHigh) > 0:
                idmHigh = puHigh[-1]
                idmHBar = puHBar[-1]
        
        if findIDM and isCocUp and isBosUp:
            if low < idmLow:
                findIDM = False
                isBosUp = False
                L = low
                LBar = i
                lastH = H
                lastHBar = HBar
                arrLastH.append(lastH)
                arrLastHBar.append(lastHBar)
                arrLastL.append(lastL)
                arrLastLBar.append(lastLBar)
                if len(arrLastH) > 0:
                    H_lastH = arrLastH[-1]
        
        if findIDM and isCocDn and isBosDn:
            if high > idmHigh:
                findIDM = False
                isBosDn = False
                H = high
                HBar = i
                lastL = L
                lastLBar = LBar
                arrLastH.append(lastH)
                arrLastHBar.append(lastHBar)
                arrLastL.append(lastL)
                arrLastLBar.append(lastLBar)
                if len(arrLastL) > 0:
                    L_lastL = arrLastL[-1]
        
        if isCocDn and high > lastH:
            if close > lastH:
                choch_signals.append({'index': i - 5000, 'type': 'ChoCh_Up', 'price': lastH})
                findIDM = True
                isBosUp = True
                isCocUp = True
                isBosDn = False
                isCocDn = False
                isPrevBos = False
                if len(arrLastL) > 0:
                    L_lastL = arrLastL[-1]
        
        if isCocUp and low < lastL:
            if close < lastL:
                choch_signals.append({'index': i - 5000, 'type': 'ChoCh_Down', 'price': lastL})
                findIDM = True
                isBosUp = False
                isCocUp = False
                isBosDn = True
                isCocDn = True
                isPrevBos = False
                if len(arrLastH) > 0:
                    H_lastH = arrLastH[-1]
        
        if not findIDM and not isBosUp and isCocUp:
            if high > lastH:
                if close > lastH:
                    findIDM = True
                    isBosUp = True
                    isCocUp = True
                    isBosDn = False
                    isCocDn = False
                    isPrevBos = True
                    lastL = L
                    lastLBar = LBar
                    L_lastL = L
        
        if not findIDM and not isBosDn and isCocDn:
            if low < lastL:
                if close < lastL:
                    findIDM = True
                    isBosUp = False
                    isCocUp = False
                    isBosDn = True
                    isCocDn = True
                    isPrevBos = True
                    lastH = H
                    lastHBar = HBar
                    H_lastH = H
        
        if high > lastH:
            lastH = high
            lastHBar = i
        
        if low < lastL:
            lastL = low
            lastLBar = i
    
    return choch_signals

def detect_fvg(symbol, tf , unmitigated_only=False, unfilled_only=False):
    
    df = candle(symbol, tf , 5000).copy()
    if len(df) < 3:
        return []
    
    fvgs = []
    
    for i in range(1, len(df) - 1):
        prev_candle = df.iloc[i-1]
        current_candle = df.iloc[i]
        next_candle = df.iloc[i+1]
        
        if next_candle['low'] > prev_candle['high']:
            fvg_top = next_candle['low']
            fvg_bottom = prev_candle['high']
            fvg_range = fvg_top - fvg_bottom
            
            max_fill = 0.0
            is_mitigated = False
            
            for j in range(i+2, len(df)):
                cnd = df.iloc[j]
                
                if cnd['low'] <= fvg_bottom:
                    is_mitigated = True
                    max_fill = 100.0
                    break
                elif cnd['low'] < fvg_top:
                    fill_amount = fvg_top - cnd['low']
                    fill_percentage = (fill_amount / fvg_range) * 100
                    max_fill = max(max_fill, fill_percentage)
            
            fvg = {
                'index': i,
                'type': 'bullish',
                'top': fvg_top,
                'bottom': fvg_bottom,
                'is_mitigated': is_mitigated,
                'fill_percentage': max_fill
            }
            
            should_include = True
            if unmitigated_only and is_mitigated:
                should_include = False
            if unfilled_only and max_fill >= 100.0:
                should_include = False
            
            if should_include:
                fvgs.append(fvg)
        
        elif next_candle['high'] < prev_candle['low']:
            fvg_top = prev_candle['low']
            fvg_bottom = next_candle['high']
            fvg_range = fvg_top - fvg_bottom
            
            max_fill = 0.0
            is_mitigated = False
            
            for j in range(i+2, len(df)):
                cnd = df.iloc[j]
                
                if cnd['high'] >= fvg_top:
                    is_mitigated = True
                    max_fill = 100.0
                    break
                elif cnd['high'] > fvg_bottom:
                    fill_amount = cnd['high'] - fvg_bottom
                    fill_percentage = (fill_amount / fvg_range) * 100
                    max_fill = max(max_fill, fill_percentage)
            
            fvg = {
                'index': i - 5000,
                'type': 'bearish',
                'top': fvg_top,
                'bottom': fvg_bottom,
                'is_mitigated': is_mitigated,
                'fill_percentage': max_fill
            }
            
            should_include = True
            if unmitigated_only and is_mitigated:
                should_include = False
            if unfilled_only and max_fill >= 100.0:
                should_include = False
            
            if should_include:
                fvgs.append(fvg)
    
    return fvgs

def detect_ob(symbol, tf, merge_ratio=0.5, use_mother_bar=True):
    df = candle(symbol, tf, 5000)
    df = df.copy()
    if 'time' not in df.columns:
        df['time'] = df.index
    def handle_zone(zone_list: list, new_zone: dict, merge_ratio: float, is_supply: bool):
    
        if not zone_list or zone_list[-1].get('status') == 'mitigated':
            zone_list.append(new_zone)
            return

        last_zone = zone_list[-1]
        
        merge_condition = False
        if last_zone['top'] > last_zone['bottom']:
            range_last = last_zone['top'] - last_zone['bottom']
            top_close = abs(new_zone['top'] - last_zone['top']) / range_last < merge_ratio
            bottom_close = abs(new_zone['bottom'] - last_zone['bottom']) / range_last < merge_ratio
            overlap = (new_zone['top'] >= last_zone['bottom'] and new_zone['bottom'] <= last_zone['top'])
            if top_close or bottom_close or overlap:
                merge_condition = True

        if merge_condition:
            last_zone['top'] = max(new_zone['top'], last_zone['top'])
            last_zone['bottom'] = min(new_zone['bottom'], last_zone['bottom'])
        else:
            zone_list.append(new_zone)
    
    supply_zones = []
    demand_zones = []

    is_sweep_obs, is_sweep_obd = False, False
    obs_candidate, obd_candidate = {}, {}

    if len(df) < 5:
        return {'supply_zones': [], 'demand_zones': []}

    for i in range(4, len(df)):
        high, low = df['high'].iloc[i], df['low'].iloc[i]
        
        updated_supply = []
        for zone in supply_zones:
            if i - zone['index'] > len(df['high'].tolist()):
                continue
            if high >= zone['top']:
                continue
            if high >= zone['bottom'] and zone['status'] == 'active':
                zone['status'] = 'mitigated'
            
            updated_supply.append(zone)
        supply_zones = updated_supply

        updated_demand = []
        for zone in demand_zones:
            if i - zone['index'] > len(df['high'].tolist()):
                continue
            if low <= zone['bottom']:
                continue
            if low <= zone['top'] and zone['status'] == 'active':
                zone['status'] = 'mitigated'
            
            updated_demand.append(zone)
        demand_zones = updated_demand
        
        high_1, low_1 = df['high'].iloc[i-1], df['low'].iloc[i-1]
        high_2, low_2 = df['high'].iloc[i-2], df['low'].iloc[i-2]
        high_3, low_3, time_3 = df['high'].iloc[i-3], df['low'].iloc[i-3], df['time'].iloc[i-3]
        high_4, low_4 = df['high'].iloc[i-4], df['low'].iloc[i-4]

        if not is_sweep_obs:
            if high_3 > high_4 and high_3 > high_2:
                is_sweep_obs = True
                obs_candidate = {'high': high_3, 'low': low_3, 'time': time_3, 'index': i-3}
        else:
            if obs_candidate.get('low') and obs_candidate['low'] > high_1:
                new_zone = {
                    'time': obs_candidate['time'],
                    'index': obs_candidate['index'],
                    'top': obs_candidate['high'],
                    'bottom': obs_candidate['low'],
                    'status': 'active'
                }
                handle_zone(supply_zones, new_zone, merge_ratio, is_supply=True)
                is_sweep_obs = False
            else:
                isb_2 = high_2 < high_3 and low_2 > low_3
                if use_mother_bar and isb_2:
                    obs_candidate['high'] = max(obs_candidate['high'], high_2)
                    obs_candidate['low'] = min(obs_candidate['low'], low_2)
                else:
                    obs_candidate = {'high': high_2, 'low': low_2, 'time': df['time'].iloc[i-2], 'index': i-2}
        
        if not is_sweep_obd:
            if low_3 < low_4 and low_3 < low_2:
                is_sweep_obd = True
                obd_candidate = {'high': high_3, 'low': low_3, 'time': time_3, 'index': i-3}
        else:
            if obd_candidate.get('high') and obd_candidate['high'] < low_1:
                new_zone = {
                    'time': obd_candidate['time'],
                    'index': obd_candidate['index'],
                    'top': obd_candidate['high'],
                    'bottom': obd_candidate['low'],
                    'status': 'active'
                }
                handle_zone(demand_zones, new_zone, merge_ratio, is_supply=False)
                is_sweep_obd = False
            else:
                isb_2 = high_2 < high_3 and low_2 > low_3
                if use_mother_bar and isb_2:
                    obd_candidate['high'] = max(obd_candidate['high'], high_2)
                    obd_candidate['low'] = min(obd_candidate['low'], low_2)
                else:
                    obd_candidate = {'high': high_2, 'low': low_2, 'time': df['time'].iloc[i-2], 'index': i-2}

    return {'supply_zones': supply_zones, 'demand_zones': demand_zones}

def detect_idm(symbol, tf, structure_type: str = "Choch with IDM", pivot_length: int = 15):

    df = candle(symbol, tf, 5000)
    df = df.copy()

    if not all(col in df.columns for col in ['high', 'low', 'close']):
        raise ValueError("DataFrame must contain 'high', 'low', and 'close' columns.")
    
    df = df.reset_index(drop=True)
    if 'time' not in df.columns:
        df['time'] = pd.to_datetime(df.index, unit='s')
    
    if 'time' not in df.columns:
        df['time'] = pd.to_datetime(df.index, unit='s')
    highs, lows, n = df["high"].values, df["low"].values, len(df)
    pivot_highs_raw, pivot_lows_raw = [], []
    if n <= 2 * pivot_length:
        pivots = {"pivot_highs": [], "pivot_lows": [], "all_pivots": []}
    else:
        for i in range(pivot_length, n - pivot_length):
            if highs[i] == np.max(highs[i - pivot_length : i + pivot_length + 1]):
                pivot_highs_raw.append((i, highs[i]))
            if lows[i] == np.min(lows[i - pivot_length : i + pivot_length + 1]):
                pivot_lows_raw.append((i, lows[i]))
        pivot_highs = [{"index": i, "price": p, "time": df['time'].iloc[i]} for i, p in pivot_highs_raw]
        pivot_lows = [{"index": i, "price": p, "time": df['time'].iloc[i]} for i, p in pivot_lows_raw]
        all_pivots_sorted = sorted(
            [dict(p, type='high') for p in pivot_highs] +
            [dict(p, type='low') for p in pivot_lows],
            key=lambda x: x["index"]
        )
        pivots = {"pivot_highs": pivot_highs, "pivot_lows": pivot_lows, "all_pivots": all_pivots_sorted}
    
    H, L = 0.0, float('inf')
    idm_low, idm_high = 0.0, 0.0
    last_H, last_L = 0.0, float('inf')
    idm_l_bar, idm_h_bar = None, None
    h_bar, l_bar = None, None
    last_h_bar, last_l_bar = None, None
    mn_strc, prev_mn_strc = None, None
    top, bot = 0.0, float('inf')
    top_, bot_ = 0.0, float('inf')
    bar, bar_ = None, None
    find_IDM, is_bos_up, is_bos_dn = False, False, False
    is_coc_up, is_coc_dn = True, True
    is_prev_bos = None
    pu_high, pu_h_bar, pu_low, pu_l_bar = [], [], [], []
    arr_last_h, arr_last_h_bar, arr_last_l, arr_last_l_bar = [], [], [], []
    completed_events = []
    
    for i, row in df.iterrows():
        high, low, close, time_idx = row['high'], row['low'], row['close'], i
        
        if L == float('inf'):
            L, H = low, high
            last_L, last_H = low, high
            top, bot = high, low
            bar = time_idx
            l_bar, h_bar = time_idx, time_idx
            last_l_bar, last_h_bar = time_idx, time_idx
            continue
        
        if high >= top and low <= bot:
            if mn_strc is not None: 
                prev_mn_strc = bool(mn_strc)
            if prev_mn_strc: 
                top_, bar_ = top, bar
            else: 
                bot_, bar_ = bot, bar
            top, bot, bar, mn_strc = high, low, time_idx, None
        elif high >= top and low > bot:
            if prev_mn_strc and mn_strc is None:
                pu_h_bar.append(bar_)
                pu_high.append(top_)
                pu_l_bar.append(bar)
                pu_low.append(bot)
            elif (not prev_mn_strc and mn_strc is None) or not mn_strc:
                pu_l_bar.append(bar)
                pu_low.append(bot)
            top, bot, bar, prev_mn_strc, mn_strc = high, low, time_idx, None, True
        elif high < top and low <= bot:
            if not prev_mn_strc and mn_strc is None:
                pu_h_bar.append(bar)
                pu_high.append(top)
                pu_l_bar.append(bar_)
                pu_low.append(bot_)
            elif (prev_mn_strc and mn_strc is None) or mn_strc:
                pu_h_bar.append(bar)
                pu_high.append(top)
            top, bot, bar, prev_mn_strc, mn_strc = high, low, time_idx, None, False
        
        if high >= H:
            H, h_bar = high, time_idx
            idm_low = pu_low[-1] if len(pu_low) >= 1 else None
            idm_l_bar = pu_l_bar[-1] if len(pu_l_bar) >= 1 else None
        if low <= L:
            L, l_bar = low, time_idx
            idm_high = pu_high[-1] if len(pu_high) >= 1 else None
            idm_h_bar = pu_h_bar[-1] if len(pu_h_bar) >= 1 else None
        
        if find_IDM and is_coc_up and idm_low and low < idm_low:
            event = {'type': 'Bullish_IDM_Taken', 'idm_price': idm_low, 'start_index': idm_l_bar, 'end_index': time_idx}
            
            points = {"point_1_head": None, "point_3_start_of_move": None, "last_pivot_before_take": None, "point_3_mitigation": None, "point_1_mitigation": None}
            start_idx, end_idx = event['start_index'], event['end_index']
            last_pivots_before_take = [p for p in pivots['all_pivots'] if p['index'] < end_idx]
            if last_pivots_before_take:
                points['last_pivot_before_take'] = last_pivots_before_take[-1]
            head_slice = df.iloc[start_idx:end_idx + 1]
            if not head_slice.empty:
                head_idx = head_slice['high'].idxmax()
                points['point_1_head'] = {"index": head_idx, "price": df.loc[head_idx, 'high']}
                prev_pivots = [p for p in pivots['pivot_highs'] if p['index'] < head_idx]
                points['point_1_head']['prev_pivot_index'] = prev_pivots[-1]['index'] if prev_pivots else None
            if points['point_1_head']:
                point_1_price = points['point_1_head']['price']
                mitigation_slice = df.iloc[end_idx + 1:]
                if not mitigation_slice.empty:
                    mitigation_candles = mitigation_slice[mitigation_slice['high'] >= point_1_price]
                    if not mitigation_candles.empty:
                        mit_idx = mitigation_candles.index[0]
                        points['point_1_mitigation'] = {"mitigated": True, "index": mit_idx, "price": df.loc[mit_idx, 'high']}
                    else: 
                        points['point_1_mitigation'] = False
                else: 
                    points['point_1_mitigation'] = False
                head_idx = points['point_1_head']['index']
                prev_highs = [p for p in pivots['pivot_highs'] if p['index'] < head_idx]
                if prev_highs:
                    left_shoulder = prev_highs[-1]
                    shoulder_idx = left_shoulder['index']
                    candidate_lows = [p for p in pivots['pivot_lows'] if p['index'] < shoulder_idx]
                    for j in range(len(candidate_lows) - 1, -1, -1):
                        potential_point_3 = candidate_lows[j]
                        if potential_point_3['price'] < event['idm_price']:
                            points['point_3_start_of_move'] = potential_point_3
                            break 
            if points['point_3_start_of_move']:
                point_3_price = points['point_3_start_of_move']['price']
                mitigation_slice = df.iloc[end_idx + 1:]
                if not mitigation_slice.empty:
                    mitigation_candles = mitigation_slice[mitigation_slice['low'] <= point_3_price]
                    if not mitigation_candles.empty:
                        points['point_3_mitigation'] = {"mitigated": True, "index": mitigation_candles.index[0], "price": df.loc[mitigation_candles.index[0], 'low']}
                    else: 
                        points['point_3_mitigation'] = False
                else: 
                    points['point_3_mitigation'] = False
            
            event['pattern_points'] = points
            completed_events.append(event)
            find_IDM = False
            is_bos_up = False
            L, l_bar = low, time_idx
            if structure_type == "Choch with IDM" and idm_low == last_L:
                if is_prev_bos:
                    last_L = arr_last_l[-1] if len(arr_last_l) >= 1 else last_L
                    last_l_bar = arr_last_l_bar[-1] if len(arr_last_l_bar) >= 1 else last_l_bar
                else:
                    is_coc_up, is_coc_dn = False, True
            last_H, last_h_bar = H, h_bar
            arr_last_h.append(last_H)
            arr_last_h_bar.append(last_h_bar)
            arr_last_l.append(last_L)
            arr_last_l_bar.append(last_l_bar)
            pu_low.clear()
            pu_l_bar.clear()
        
        if find_IDM and is_coc_dn and idm_high and high > idm_high:
            event = {'type': 'Bearish_IDM_Taken', 'idm_price': idm_high, 'start_index': idm_h_bar, 'end_index': time_idx}
            
            points = {"point_1_head": None, "point_3_start_of_move": None, "last_pivot_before_take": None, "point_3_mitigation": None, "point_1_mitigation": None}
            start_idx, end_idx = event['start_index'], event['end_index']
            last_pivots_before_take = [p for p in pivots['all_pivots'] if p['index'] < end_idx]
            if last_pivots_before_take:
                points['last_pivot_before_take'] = last_pivots_before_take[-1]
            head_slice = df.iloc[start_idx:end_idx + 1]
            if not head_slice.empty:
                head_idx = head_slice['low'].idxmin()
                points['point_1_head'] = {"index": head_idx, "price": df.loc[head_idx, 'low']}
                prev_pivots = [p for p in pivots['pivot_lows'] if p['index'] < head_idx]
                points['point_1_head']['prev_pivot_index'] = prev_pivots[-1]['index'] if prev_pivots else None
            if points['point_1_head']:
                point_1_price = points['point_1_head']['price']
                mitigation_slice = df.iloc[end_idx + 1:]
                if not mitigation_slice.empty:
                    mitigation_candles = mitigation_slice[mitigation_slice['low'] <= point_1_price]
                    if not mitigation_candles.empty:
                        mit_idx = mitigation_candles.index[0]
                        points['point_1_mitigation'] = {"mitigated": True, "index": mit_idx, "price": df.loc[mit_idx, 'low']}
                    else: 
                        points['point_1_mitigation'] = False
                else: 
                    points['point_1_mitigation'] = False
                head_idx = points['point_1_head']['index']
                prev_lows = [p for p in pivots['pivot_lows'] if p['index'] < head_idx]
                if prev_lows:
                    left_shoulder = prev_lows[-1]
                    shoulder_idx = left_shoulder['index']
                    candidate_highs = [p for p in pivots['pivot_highs'] if p['index'] < shoulder_idx]
                    for j in range(len(candidate_highs) - 1, -1, -1):
                        potential_point_3 = candidate_highs[j]
                        if potential_point_3['price'] > event['idm_price']:
                            points['point_3_start_of_move'] = potential_point_3
                            break
            if points['point_3_start_of_move']:
                point_3_price = points['point_3_start_of_move']['price']
                mitigation_slice = df.iloc[end_idx + 1:]
                if not mitigation_slice.empty:
                    mitigation_candles = mitigation_slice[mitigation_slice['high'] >= point_3_price]
                    if not mitigation_candles.empty:
                        points['point_3_mitigation'] = {"mitigated": True, "index": mitigation_candles.index[0], "price": df.loc[mitigation_candles.index[0], 'high']}
                    else: 
                        points['point_3_mitigation'] = False
                else: 
                    points['point_3_mitigation'] = False
            
            event['pattern_points'] = points
            completed_events.append(event)
            find_IDM = False
            is_bos_dn = False
            H, h_bar = high, time_idx
            if structure_type == "Choch with IDM" and idm_high == last_H:
                if is_prev_bos:
                    last_H = arr_last_h[-1] if len(arr_last_h) >= 1 else last_H
                    last_h_bar = arr_last_h_bar[-1] if len(arr_last_h_bar) >= 1 else last_h_bar
                else:
                    is_coc_up, is_coc_dn = True, False
            last_L, last_l_bar = L, l_bar
            arr_last_h.append(last_H)
            arr_last_h_bar.append(last_h_bar)
            arr_last_l.append(last_L)
            arr_last_l_bar.append(last_l_bar)
            pu_high.clear()
            pu_h_bar.clear()
        
        if is_coc_dn and high > last_H and close > last_H:
            find_IDM, is_bos_up, is_coc_up = True, True, True
            is_bos_dn, is_coc_dn, is_prev_bos = False, False, False
        
        if is_coc_up and low < last_L and close < last_L:
            find_IDM, is_bos_dn, is_coc_dn = True, True, True
            is_bos_up, is_coc_up, is_prev_bos = False, False, False
        
        if not find_IDM and not is_bos_up and is_coc_up and high > last_H and close > last_H:
            find_IDM, is_bos_up, is_coc_up, is_prev_bos = True, True, True, True
            is_bos_dn, is_coc_dn = False, False
            last_L, last_l_bar = L, l_bar
        
        if not find_IDM and not is_bos_dn and is_coc_dn and low < last_L and close < last_L:
            find_IDM, is_bos_dn, is_coc_dn, is_prev_bos = True, True, True, True
            is_bos_up, is_coc_up = False, False
            last_H, last_h_bar = H, h_bar
        
        if high > last_H: 
            last_H, last_h_bar = high, time_idx
        if low < last_L: 
            last_L, last_l_bar = low, time_idx
    
    return completed_events

