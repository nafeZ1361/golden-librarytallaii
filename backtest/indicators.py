from .hashem_backtest import backtest_candle
import datetime
import pandas as pd
import ta
import numpy as np
import pandas_ta
 

def backtest_ema(symbol, tf , window , limit, candle_type='ca'):
    if candle_type == 'ca':
        ohlc = backtest_candle(symbol, tf, limit)
    else:
        ohlc = backtest_candle(symbol, tf, limit, True)

    prices = pd.DataFrame(ohlc[:])
    prices['ema'] = prices['close'].ewm(span = window).mean()
    ema = prices['ema'].values.tolist()

    signals = ['buy' if prices.close[i] > ema[i]
               else 'sell' if prices.close[i] < ema[i]
               else 'nu' for i in range(len(prices))]
    
    return signals

def backtest_sma(symbol, tf , window , limit, candle_type='ca'):
    
    if candle_type == 'ca':
        ohlc = backtest_candle(symbol, tf, limit)
    else:
        ohlc = backtest_candle(symbol, tf, limit, True)

    prices = pd.DataFrame(ohlc[:])
    
    prices['sma'] = ta.trend.SMAIndicator(prices['close'], window=window).sma_indicator()
   
    ma_values = prices['sma'].values.tolist()

    signals = ['buy' if prices.close[i] > ma_values[i]
               else 'sell' if prices.close[i] < ma_values[i]
               else 'nu' for i in range(len(prices))]
    
    return signals
    
def backtest_cross_signal(series1, series2):
    
    if len(series1) != len(series2) :
        raise ValueError("both lengths most be equal!")
    
    signals = []
    for i in range(3, len(series1)) :
        if series1[i-1] > series2[i-1] and series1[i-2] > series2[i-2] and series1[i-3] <= series2[i-3]:
            signals.append('buy')
        elif series1[i-1] < series2[i-1] and series1[i-2] < series2[i-2] and series1[i-3] >= series2[i-3]:
            signals.append('sell')
        else:
            signals.append('hold')

    signals = ['hold', 'hold', 'hold'] + signals
    return signals

def backtest_supertrend(symbol, tf, limit, atr_period=10, multiplier=3.0, candle_type='ca', data=None):
    limit = int(limit)
    
    required_limit = max(limit, atr_period * 5)
    
    if data is not None:
        df = data.copy()
    elif candle_type == 'ca':
        df = backtest_candle(symbol, tf, required_limit).copy()
    else:
        df = backtest_candle(symbol, tf, required_limit, True).copy()
    
    def rma(series, length):
        result = [np.nan] * len(series)
        for i in range(len(series)):
            if i == 0:
                result[i] = series.iloc[i]
            else:
                result[i] = (result[i-1] * (length - 1) + series.iloc[i]) / length
        return pd.Series(result, index=series.index)

    df = df.copy()
    change_atr_method = True
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

        position = 'buy' if curr_trend == 1 else 'sell'
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

    if len(position_list) > limit:
        position_list = position_list[-limit:]
        signal_list = signal_list[-limit:]
    
    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_sar(symbol, tf, limit, start=0.02, increament=0.02, max_value=0.2, candle_type='ca'):
    limit = int(limit)
    
    required_limit = max(limit, 50)
    
    if candle_type == 'ca':
        df = backtest_candle(symbol, tf, required_limit).copy()
    else:
        df = backtest_candle(symbol, tf, required_limit, True).copy()
    
    high = df['high']
    low = df['low']

    length = len(high)
    psar_values = [0.0] * length
    trend = [0] * length
    af = [0.0] * length
    ep = [0.0] * length
    position_list = []
    signal_list = []
    
    psar_values[0] = low[0]
    trend[0] = 1
    af[0] = start
    ep[0] = high[0]
    position_list.append('buy')
    signal_list.append(None)
    
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
        
        position = 'buy' if trend[i] == 1 else 'sell'
        position_list.append(position)
        
        if trend[i] == 1 and trend[i-1] == -1:
            signal = 'buy'
        elif trend[i] == -1 and trend[i-1] == 1:
            signal = 'sell'
        else:
            signal = 'hold'
        signal_list.append(signal)
    
    if len(position_list) > limit:
        position_list = position_list[-limit:]
        signal_list = signal_list[-limit:]
    
    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_macd(symbol, tf, limit, fast=12, slow=26, signal=9):
    limit = int(limit)
    
    raw_data = backtest_candle(symbol, tf, limit)
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

def backtest_ut_bot(symbol, tf, limit, key_value: int = 3, atr_period: int = 10, candle_type='ca'):
    limit = int(limit)
    
    required_limit = max(limit, atr_period * 5)
    
    if candle_type == 'ca':
        df = backtest_candle(symbol, tf, required_limit).copy()
    else:
        df = backtest_candle(symbol, tf, required_limit, True).copy()

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
    df.loc[buy_signal_points, 'signal_state'] = 'buy'
    df.loc[sell_signal_points, 'signal_state'] = 'sell'
    df['signal_state'] = df['signal_state'].ffill()
    df['signal_state'] = df['signal_state'].fillna('neutral')
    
    position_list = df['signal_state'].tolist()
    signal_list = [None]
    
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] != 'buy':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] != 'sell':
            signal_list.append('sell')
        else:
            signal_list.append('hold')
    
    if len(position_list) > limit:
        position_list = position_list[-limit:]
        signal_list = signal_list[-limit:]
    
    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_trend_alert(symbol, limit, high_tf, low_tf):
    limit = int(limit)
    
    def candle_index(smaller_tf: str, larger_tf: str, candle_offset: int):
        timeframe_mapping = {
            "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "90m": 90,
            "1h": 60, "2h": 120, "4h": 240, "1d": 1440, "1w": 10080
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

    high_tf_df = backtest_candle(symbol, high_tf, limit, True).copy()
    low_tf_df = backtest_candle(symbol, low_tf, limit, True).copy()

    def ema(df, period):
        return df['close'].ewm(span=period, adjust=False).mean()

    ema_values = ema(low_tf_df, 20)
    position_list = []
    signal_list = [None]

    for i in range(1, 100):
        delta = ema_values.diff().iloc[-i]
        hi_index = candle_index(low_tf, high_tf, -i)

        if (high_tf_df.iloc[hi_index]['open'] < high_tf_df.iloc[hi_index]['close'] and
            low_tf_df.iloc[-i]['open'] < low_tf_df.iloc[-i]['close'] and
            low_tf_df.iloc[-i]['close'] > ema_values.iloc[-i] and
            delta > 0):
            position_list.append('buy')
        elif (high_tf_df.iloc[hi_index]['open'] > high_tf_df.iloc[hi_index]['close'] and
              low_tf_df.iloc[-i]['open'] > low_tf_df.iloc[-i]['close'] and
              low_tf_df.iloc[-i]['close'] < ema_values.iloc[-i] and
              delta < 0):
            position_list.append('sell')
        else:
            position_list.append('neutral')

    position_list = position_list[::-1]
    
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] != 'buy':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] != 'sell':
            signal_list.append('sell')
        else:
            signal_list.append('hold')

    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_stochrsi(symbol, tf, limit, line='blue', rsi_length=14, stoch_length=14, k_period=3, d_period=3, candle_type='ca'):
    limit = int(limit)
    
    if candle_type == 'ca':
        candles = backtest_candle(symbol, tf, limit).copy()
    else:
        candles = backtest_candle(symbol, tf, limit, True).copy()
    
    df_close = candles['close']
    stoch_rsi = pandas_ta.stochrsi(df_close, length=stoch_length, rsi_length=rsi_length, k=k_period, d=d_period)

    d = stoch_rsi['STOCHRSId_' + str(rsi_length) + '_' + str(stoch_length) + '_' + str(k_period) + '_' + str(d_period)].tolist()
    k = stoch_rsi['STOCHRSIk_' + str(rsi_length) + '_' + str(stoch_length) + '_' + str(k_period) + '_' + str(d_period)].tolist()
    
    return k if line == 'blue' else d

def backtest_kalman_trend_levels(symbol, tf, limit, sell_len=50, buy_len=150):
    limit = int(limit)
    
    required_limit = max(limit, max(sell_len, buy_len) * 3)
    ha_data = backtest_candle(symbol, tf, required_limit, True).copy()
    
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
    sell_kalman = kalman_filter(closes, sell_len)
    buy_kalman = kalman_filter(closes, buy_len)
    
    if len(sell_kalman) > limit:
        sell_kalman = sell_kalman[-limit:]
        buy_kalman = buy_kalman[-limit:]
    
    position_list = ['buy' if s > l else 'sell' for s, l in zip(sell_kalman, buy_kalman)]
    signal_list = [None]
    
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] == 'sell':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] == 'buy':
            signal_list.append('sell')
        else:
            signal_list.append('hold')
    
    if len(position_list) < limit:
        pad_size = limit - len(position_list)
        position_list = ['sell'] * pad_size + position_list
        signal_list = [None] * pad_size + signal_list
    
    return {
        'trend': position_list[-limit:],
        'signal': signal_list[-limit:]
    }

def backtest_half_trend(symbol, tf, limit, amplitude=2, channel_deviation=2, candle_type='ca'):
    limit = int(limit)
    
    required_limit = max(limit, amplitude * 50)
    
    if candle_type == 'ca':
        df = backtest_candle(symbol, tf, required_limit).copy()
    else:
        df = backtest_candle(symbol, tf, required_limit, True).copy()
    
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

    position_list = ['buy' if trend == 0 else 'sell' for trend in df['trend']]
    
    if len(position_list) > limit:
        position_list = position_list[-limit:]
    elif len(position_list) < limit:
        pad_size = limit - len(position_list)
        position_list = ['sell'] * pad_size + position_list
    
    signal_list = [None]
    
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] == 'sell':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] == 'buy':
            signal_list.append('sell')
        else:
            signal_list.append('hold')
    
    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_Trend_Indicator_A(symbol, tf, limit, ma_type="EMA", ma_period=9, alma_sigma=6, candle_type='ha'):
    limit = int(limit)
    
    required_limit = max(limit, ma_period * 10)
    
    if candle_type == 'ca':
        ha_df = backtest_candle(symbol, tf, required_limit).copy()
    else:
        ha_df = backtest_candle(symbol, tf, required_limit, True).copy()

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
            wma_half = series.rolling(window=max(1, ma_period//2)).mean()
            wma_full = series.rolling(window=ma_period).mean()
            hma = 2 * wma_half - wma_full
            return hma.rolling(window=max(1, int(np.sqrt(ma_period)))).mean()
        
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
        lag = max(1, (ma_period - 1) // 2)
        
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
        ha_df['MA_Open'] = ha_df['open'].ewm(span=ma_period, adjust=False).mean()
        ha_df['MA_Close'] = ha_df['close'].ewm(span=ma_period, adjust=False).mean()
        ha_df['MA_High'] = ha_df['high'].ewm(span=ma_period, adjust=False).mean()
        ha_df['MA_Low'] = ha_df['low'].ewm(span=ma_period, adjust=False).mean()

    ha_df['Trend'] = 100 * (ha_df['MA_Close'] - ha_df['MA_Open']) / (ha_df['MA_High'] - ha_df['MA_Low'] + 0.0001)
    
    position_list = np.where(ha_df['Trend'] > 0, 'buy', 'sell').tolist()
    
    if len(position_list) > limit:
        position_list = position_list[-limit:]
    elif len(position_list) < limit:
        pad_size = limit - len(position_list)
        position_list = ['sell'] * pad_size + position_list
    
    signal_list = [None]
    
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] == 'sell':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] == 'buy':
            signal_list.append('sell')
        else:
            signal_list.append('hold')

    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_ema_cross(symbol, tf, limit, fast_period=20, slow_period=50, candle_type='ca'):
    if candle_type == 'ca':
        ohlc = backtest_candle(symbol, tf, limit).copy()
    else:
        ohlc = backtest_candle(symbol, tf, limit, True).copy()

    prices = pd.DataFrame(ohlc[:])
    prices['fast_ema'] = prices['close'].ewm(span=fast_period).mean()
    prices['slow_ema'] = prices['close'].ewm(span=slow_period).mean()

    position_list = ['buy' if fast > slow else 'sell'
                    for fast, slow in zip(prices['fast_ema'], prices['slow_ema'])]

    signal_list = [None]
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] == 'sell':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] == 'buy':
            signal_list.append('sell')
        else:
            signal_list.append('hold')

    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_deviation_trend_signals(symbol, tf, limit, sma_length=50, candle_type='ca'):
    limit = int(limit)
    
    required_limit = max(limit, sma_length * 50)
    
    if candle_type == 'ca':
        df = backtest_candle(symbol, tf, required_limit).copy()
    else:
        df = backtest_candle(symbol, tf, required_limit, True).copy()

    df = df.reset_index(drop=True)
    df['avg'] = df['close'].rolling(window=sma_length).mean()
    df['avg_diff'] = df['avg'] - df['avg'].shift(5)
    df['avg_col'] = df['avg_diff'] / df['avg_diff'].rolling(window=500).quantile(1.0)
    trends = [0] * len(df)
    position_list = ['sell'] * len(df)
    
    for i in range(1, len(df)):
        prev_trend = trends[i-1]
        
        if (df['avg_col'].iloc[i] > 0.1 and 
            df['avg_col'].iloc[i-1] <= 0.1 and 
            prev_trend == 0):
            trends[i] = 1
            position_list[i] = 'buy'
            
        elif (df['avg_col'].iloc[i] < -0.1 and 
              df['avg_col'].iloc[i-1] >= -0.1 and 
              prev_trend == 1):
            trends[i] = 0
            position_list[i] = 'sell'
        
        else:
            trends[i] = prev_trend
            position_list[i] = 'buy' if prev_trend == 1 else 'sell'
    
    if len(position_list) > limit:
        position_list = position_list[-limit:]
    elif len(position_list) < limit:
        pad_size = limit - len(position_list)
        position_list = ['sell'] * pad_size + position_list
    
    signal_list = [None]
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] == 'sell':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] == 'buy':
            signal_list.append('sell')
        else:
            signal_list.append('hold')
    
    return {
        'trend': position_list,
        'signal': signal_list
    }

def backtest_volumatic_vidya(symbol, tf, limit, vidya_length=10, vidya_momentum=20, band_distance=2, value='trend', candle_type='ca'):
    limit = int(limit)
    
    required_limit = max(limit, max(vidya_length, vidya_momentum) * 20)
    
    if candle_type == 'ca':
        data = backtest_candle(symbol, tf, required_limit).copy()
    else:
        data = backtest_candle(symbol, tf, required_limit, True).copy()
    
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
                trend.iloc[i] = 'buy'
            elif trend_cross_down:
                trend.iloc[i] = 'sell'
            else:
                trend.iloc[i] = trend.iloc[i-1] if pd.notna(trend.iloc[i-1]) else None
    
    if value == 'trend':
        position_list = trend.tolist()
        
        if len(position_list) > limit:
            position_list = position_list[-limit:]
        elif len(position_list) < limit:
            pad_size = limit - len(position_list)
            position_list = ['sell'] * pad_size + position_list
        
        signal_list = [None]
        
        for i in range(1, len(position_list)):
            if position_list[i] == 'buy' and position_list[i-1] != 'buy':
                signal_list.append('buy')
            elif position_list[i] == 'sell' and position_list[i-1] != 'sell':
                signal_list.append('sell')
            else:
                signal_list.append('hold')
        
        return {
            'trend': position_list,
            'signal': signal_list
        }
    elif value == 'line':
        return smoothed_value.tolist()
    else:
        raise ValueError("Use 'trend' or 'line'.")

def backtest_trend_ali(symbol, tf, limit, length=60, length_mult=6.0, mode='Hma', candle_type='ca', data=None):
    limit = int(limit)
    final_length = int(length * length_mult)
    
    required_limit = max(limit, final_length * 5)
    
    if data is not None:
        ohlc = data.copy()
    elif candle_type == 'ca':
        ohlc = backtest_candle(symbol, tf, required_limit)
    else:
        ohlc = backtest_candle(symbol, tf, required_limit, True)
    
    def calc_wma(data, period):
        if len(data) < period:
            return np.array([])
        weights = np.arange(1, period + 1)
        wma_vals = []
        for i in range(period - 1, len(data)):
            window = data[i - period + 1:i + 1]
            wma_vals.append(np.sum(weights * window) / np.sum(weights))
        return np.array(wma_vals)
    
    def calc_ema(data, period):
        if len(data) < period:
            return np.array([])
        return pd.Series(data).ewm(span=period, adjust=False).mean().values
    
    def calc_hma(data, period):
        if len(data) < period:
            return np.array([])
        half_period = max(1, int(period / 2))
        sqrt_period = max(1, int(np.sqrt(period)))
        wma_half = calc_wma(data, half_period)
        wma_full = calc_wma(data, period)
        
        if len(wma_half) == 0 or len(wma_full) == 0:
            return np.array([])
        
        min_len = min(len(wma_half), len(wma_full))
        raw_hma = 2 * wma_half[-min_len:] - wma_full[-min_len:]
        
        if len(raw_hma) < sqrt_period:
            return np.array([])
        
        return calc_wma(raw_hma, sqrt_period)
    
    def calc_ehma(data, period):
        if len(data) < period:
            return np.array([])
        half_period = max(1, int(period / 2))
        sqrt_period = max(1, int(np.sqrt(period)))
        ema_half = calc_ema(data, half_period)
        ema_full = calc_ema(data, period)
        
        if len(ema_half) == 0 or len(ema_full) == 0:
            return np.array([])
        
        min_len = min(len(ema_half), len(ema_full))
        raw_ehma = 2 * ema_half[-min_len:] - ema_full[-min_len:]
        
        if len(raw_ehma) < sqrt_period:
            return np.array([])
        
        return calc_ema(raw_ehma, sqrt_period)
    
    def calc_thma(data, period):
        if len(data) < period * 2:
            return np.array([])
        period_3 = max(1, int(period / 3))
        period_2 = max(1, int(period / 2))
        wma_3 = calc_wma(data, period_3)
        wma_2 = calc_wma(data, period_2)
        wma_full = calc_wma(data, period * 2)
        
        if len(wma_3) == 0 or len(wma_2) == 0 or len(wma_full) == 0:
            return np.array([])
        
        min_len = min(len(wma_3), len(wma_2), len(wma_full))
        raw_thma = wma_3[-min_len:] * 3 - wma_2[-min_len:] - wma_full[-min_len:]
        
        if len(raw_thma) < period * 2:
            return np.array([])
        
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
        hull_values = calc_hma(close_prices, final_length)
    
    if len(hull_values) == 0:
        hull_values = np.array([df['close'].iloc[-limit:].mean()] * limit)
    
    if len(hull_values) > limit:
        hull_values = hull_values[-limit:]
    elif len(hull_values) < limit:
        padding_size = limit - len(hull_values)
        hull_values = np.concatenate([np.full(padding_size, hull_values[0] if len(hull_values) > 0 else 0), hull_values])
    
    position_list = []
    for i in range(len(hull_values)):
        if i < 2:
            position_list.append('buy' if i < 1 else ('buy' if hull_values[i] > hull_values[i-1] else 'sell'))
        else:
            if hull_values[i] > hull_values[i-2]:
                position_list.append('buy')
            else:
                position_list.append('sell')
    
    signal_list = [None]
    for i in range(1, len(position_list)):
        if position_list[i] == 'buy' and position_list[i-1] != 'buy':
            signal_list.append('buy')
        elif position_list[i] == 'sell' and position_list[i-1] != 'sell':
            signal_list.append('sell')
        else:
            signal_list.append('hold')
    
    return {
        'trend': position_list[-limit:],
        'signal': signal_list[-limit:]
    }
