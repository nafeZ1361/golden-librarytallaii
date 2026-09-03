import datetime
import pandas as pd
import MetaTrader5 as mt5
import ta
import pytz
import requests
import numpy as np


buy = mt5.ORDER_TYPE_BUY
buy_limit = mt5.ORDER_TYPE_BUY_LIMIT
buy_stop = mt5.ORDER_TYPE_BUY_STOP
sell = mt5.ORDER_TYPE_SELL
sell_limit = mt5.ORDER_TYPE_SELL_LIMIT
sell_stop = mt5.ORDER_TYPE_SELL_STOP
today = datetime.datetime.today().strftime('%A')


def get_broker_offset():
    if today != 'Sunday' and today != 'Saturday':
        symbols = mt5.symbols_get()
        if not symbols:
            return None
        for i in symbols:
            if "xauusd" in i.name.lower():
                symbol = i.name
        if symbol == None :
            symbol = symbols[0].name
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return None

        server_time_utc = datetime.datetime.fromtimestamp(tick.time, tz=datetime.timezone.utc)

        utc_time = datetime.datetime.now(datetime.timezone.utc)

        diff = server_time_utc - utc_time
        offset_hours = diff.total_seconds() / 3600

        offset_hours = round(offset_hours)

        return offset_hours

    else :
        return 3

def get_trading_sessions():
    now_utc = datetime.datetime.now(pytz.utc)

    sessions = {
        'Sydney': {
            'timezone': pytz.timezone('Australia/Sydney'),
            'start': datetime.time(7, 0),
            'end': datetime.time(16, 0)
        },
        'Tokyo': {
            'timezone': pytz.timezone('Asia/Tokyo'),
            'start': datetime.time(9, 0),
            'end': datetime.time(18, 0)
        },
        'London': {
            'timezone': pytz.timezone('Europe/London'),
            'start': datetime.time(8, 0),
            'end': datetime.time(17, 0)
        },
        'New York': {
            'timezone': pytz.timezone('America/New_York'),
            'start': datetime.time(8, 0),
            'end': datetime.time(17, 0)
        }
    }

    active_sessions = []
    current_session = None

    for name, session in sessions.items():
        tz = session['timezone']
        now_local = now_utc.astimezone(tz)
        local_time = now_local.time()
        start = session['start']
        end = session['end']

        is_open = start <= local_time < end if start < end else (local_time >= start or local_time < end)
        
        if is_open:
            active_sessions.append({
                'name': name,
                'local_time': now_local.strftime('%H:%M:%S'),
                'open_time': start.strftime('%H:%M'),
                'close_time': end.strftime('%H:%M'),
                'timezone': str(tz)
            })
            if not current_session:
                current_session = name

    sorted_active_sessions = [session for session in active_sessions if session['name'] == current_session] + \
                             [session for session in active_sessions if session['name'] != current_session]

    result = sorted_active_sessions[-1]['name'] 
    

    return result

def create_order(symbol, lot, order_type, sl=0.0, tp=0.0, comment='hashem'):
    symbol_info = mt5.symbol_info(symbol)
    
    filling_mode = symbol_info.filling_mode
    if filling_mode == 1:
        filling_mode = mt5.ORDER_FILLING_FOK
    elif filling_mode == 2:
        filling_mode = mt5.ORDER_FILLING_IOC
    else:
        filling_mode = mt5.ORDER_FILLING_FOK 
    
    price_info = mt5.symbol_info_tick(symbol)
    price = price_info.ask if order_type == buy else price_info.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"خطا در ثبت سفارش: {result.comment}")
    
    return result
        
def close_order(ticket):

    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        print(f"پوزیشن {ticket} پیدا نشد")
        return
    
    position = position[0]
    symbol = position.symbol
    volume = position.volume
    
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    price_info = mt5.symbol_info_tick(symbol)
    price = price_info.bid if position.type == mt5.POSITION_TYPE_BUY else price_info.ask
    
    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    
    for filling_mode in filling_modes:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        mt5.order_send(request)

def close_half_vol_order(ticket):

    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        print(f"پوزیشن {ticket} پیدا نشد")
        return
    
    position = position[0]
    symbol = position.symbol
    volume = round(position.volume / 2 , 2)
    if volume < 0.01 :
        volume = 0.01
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    price_info = mt5.symbol_info_tick(symbol)
    price = price_info.bid if position.type == mt5.POSITION_TYPE_BUY else price_info.ask
    
    filling_modes = [mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN]
    
    for filling_mode in filling_modes:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 0,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        mt5.order_send(request)
     
def close_all_positions():
    positions = mt5.positions_get()
    if positions is None:
        return

    for position in positions:
        p_ticket = position._asdict()['ticket']
        close_order(p_ticket)

def close_half_positions():
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return

    half_count = len(positions) // 2

    for i, position in enumerate(positions):
        if i >= half_count:
            break
        p_ticket = position._asdict()['ticket']
        
        close_order(p_ticket)

def total_positons():
    positions_total=mt5.positions_total()
    return positions_total

def balance():
    balance = mt5.account_info().balance
    return balance

def profit():
    positions = mt5.positions_get()
    profit = 0
    for position in positions:
        profit += position.profit
    return profit
 
def count_sl():
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    orders = mt5.history_deals_get(start_of_day, mt5_now)
    stop_count = sum(1 for order in orders if order.profit < 0 )
    return stop_count

def count_tp():
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    orders = mt5.history_deals_get(start_of_day, mt5_now)
    profit_count = sum(1 for order in orders if order.profit > 0)
    return profit_count

def profit_today():
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    orders = mt5.history_deals_get(start_of_day, mt5_now)
    profit_today = sum(order.profit for order in orders)    
    return profit_today

def count_sl_in_hours(hours=1):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_time = mt5_now - datetime.timedelta(hours=hours)
    orders = mt5.history_deals_get(start_time, mt5_now)
    stop_count = sum(1 for order in orders if order.profit < 0 )
    return stop_count

def count_tp_in_hours(hours=1):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_time = mt5_now - datetime.timedelta(hours=hours)
    orders = mt5.history_deals_get(start_time, mt5_now)
    stop_count = sum(1 for order in orders if order.profit > 0 )
    return stop_count

def count_sl_in_hours_with_comment(comment, hours=1):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_time = mt5_now - datetime.timedelta(hours=hours)
    deals = mt5.history_deals_get(start_time, mt5_now)
    if deals is None:
        print("No deals found.")
        return 0
    position_ids = set(deal.position_id for deal in deals if deal.comment == comment and deal.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL))
    stop_count = sum(1 for deal in deals if deal.position_id in position_ids and deal.profit < 0)

    return stop_count

def count_sl_with_comment(comment):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    deals = mt5.history_deals_get(start_of_day, mt5_now)
    if deals is None:
        print("No deals found.")
        return 0
    position_ids = set(deal.position_id for deal in deals if deal.comment == comment and deal.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL))
    stop_count = sum(1 for deal in deals if deal.position_id in position_ids and deal.profit < 0)

    return stop_count

def total_profit_today_with_comment(comment):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    deals = mt5.history_deals_get(start_of_day, mt5_now)
    if deals is None:
        print("No deals found.")
        return 0
    position_ids = set(deal.position_id for deal in deals if comment in deal.comment and deal.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL))
    profit_today = sum(deal.profit for deal in deals if deal.position_id in position_ids)

    return profit_today

def count_tp_with_comment(comment):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    deals = mt5.history_deals_get(start_of_day, mt5_now)
    if deals is None:
        print("No deals found.")
        return 0
    position_ids = set(deal.position_id for deal in deals if deal.comment == comment and deal.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL))
    profit_count = sum(1 for deal in deals if deal.position_id in position_ids and deal.profit > 0)

    return profit_count

def count_org_tp_comment(comment):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    
    deals = mt5.history_deals_get(start_of_day, mt5_now)
    if deals is None:
        return 0
    
    tp_hits = 0
    position_ids = set()
    
    for deal in deals:
        if deal.comment == comment:
            position_ids.add(deal.position_id)
    
    for deal in deals:
        if deal.position_id in position_ids and 'tp' in deal.comment:
            tp_hits += 1
    
    return tp_hits

def count_org_sl_comment(comment):
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference
    
    deals = mt5.history_deals_get(start_of_day, mt5_now)
    if deals is None:
        return 0
    
    tp_hits = 0
    position_ids = set()
    
    for deal in deals:
        if deal.comment == comment:
            position_ids.add(deal.position_id)
    
    for deal in deals:
        if deal.position_id in position_ids and 'sl' in deal.comment:
            tp_hits += 1
    
    return tp_hits

def count_tp_in_session(comment: str,session_name: str = 'London') -> int:
   
    sessions = {
        'Sydney':   {'tz': pytz.timezone('Australia/Sydney'),   'start': datetime.time(7, 0),  'end': datetime.time(16, 0)},
        'Tokyo':    {'tz': pytz.timezone('Asia/Tokyo'),         'start': datetime.time(9, 0),  'end': datetime.time(18, 0)},
        'London':   {'tz': pytz.timezone('Europe/London'),      'start': datetime.time(8, 0),  'end': datetime.time(17, 0)},
        'New York': {'tz': pytz.timezone('America/New_York'),   'start': datetime.time(8, 0),  'end': datetime.time(17, 0)},
    }

    if session_name is None:
        session_name = get_trading_sessions()
    if session_name not in sessions:
        raise ValueError(f"Session '{session_name}' is not recognized.")

    sess = sessions[session_name]
    tz = sess['tz']
    start_time = sess['start']
    end_time   = sess['end']

    today = datetime.datetime.now(tz).date()
    start_local = tz.localize(datetime.datetime.combine(today, start_time))
    end_local   = tz.localize(datetime.datetime.combine(today, end_time))

    offset = datetime.timedelta(hours=get_broker_offset())
    start_utc = start_local.astimezone(pytz.utc) + offset
    end_utc   = end_local.astimezone(pytz.utc)   + offset

    deals = mt5.history_deals_get(start_utc, end_utc)
    if not deals:
        return 0

    pos_ids = {d.position_id for d in deals if d.comment == comment}
    tp_hits = sum(
        1
        for d in deals
        if (d.position_id in pos_ids) and ('tp' in d.comment.lower())
    )

    return tp_hits

def count_sl_in_session(comment: str,session_name: str = 'London') -> int:
   
    sessions = {
        'Sydney':   {'tz': pytz.timezone('Australia/Sydney'),   'start': datetime.time(7, 0),  'end': datetime.time(16, 0)},
        'Tokyo':    {'tz': pytz.timezone('Asia/Tokyo'),         'start': datetime.time(9, 0),  'end': datetime.time(18, 0)},
        'London':   {'tz': pytz.timezone('Europe/London'),      'start': datetime.time(8, 0),  'end': datetime.time(17, 0)},
        'New York': {'tz': pytz.timezone('America/New_York'),   'start': datetime.time(8, 0),  'end': datetime.time(17, 0)},
    }

    if session_name is None:
        session_name = get_trading_sessions()
    if session_name not in sessions:
        raise ValueError(f"Session '{session_name}' is not recognized.")

    sess = sessions[session_name]
    tz = sess['tz']
    start_time = sess['start']
    end_time   = sess['end']

    today = datetime.datetime.now(tz).date()
    start_local = tz.localize(datetime.datetime.combine(today, start_time))
    end_local   = tz.localize(datetime.datetime.combine(today, end_time))

    offset = datetime.timedelta(hours=get_broker_offset())
    start_utc = start_local.astimezone(pytz.utc) + offset
    end_utc   = end_local.astimezone(pytz.utc)   + offset

    deals = mt5.history_deals_get(start_utc, end_utc)
    if not deals:
        return 0

    pos_ids = {d.position_id for d in deals if d.comment == comment}
    tp_hits = sum(
        1
        for d in deals
        if (d.position_id in pos_ids) and ('sl' in d.comment.lower())
    )

    return tp_hits

def candle(symbol='XAUUSD', tf='3m', limit=100):

    tf_lower = tf.lower()
    
    if tf_lower.endswith('m'):
        tf_minutes = int(tf_lower.replace('m', ''))
        base_tf = mt5.TIMEFRAME_M1
    elif tf_lower.endswith('h'):
        tf_hours = int(tf_lower.replace('h', ''))
        tf_minutes = tf_hours 
        base_tf = mt5.TIMEFRAME_H1
    elif tf_lower.endswith('d'):
        tf_days = int(tf_lower.replace('d', ''))
        tf_minutes = tf_days * 24
        base_tf = mt5.TIMEFRAME_H1
    else:
        raise ValueError("فرمت تایم‌فریم نامعتبر است")
    
    total_minutes = tf_minutes * limit * 2
    
    raw_data = mt5.copy_rates_from_pos(symbol, base_tf, 0, total_minutes)
    
    if raw_data is None or len(raw_data) == 0:
        print(f"هیچ داده‌ای برای نماد {symbol} یافت نشد")
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume'])
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    if tf_lower.endswith('m'):
        df['aligned_time'] = df['time'].dt.floor(f'{tf_minutes}min')
    elif tf_lower.endswith('h'):
        df['aligned_time'] = df['time'].dt.floor(f'{tf_hours}h')
    elif tf_lower.endswith('d'):
        df['aligned_time'] = df['time'].dt.floor(f'{tf_days}d')
    
    resampled = df.groupby('aligned_time').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).reset_index()
    
    result = (resampled
             .sort_values('aligned_time', ascending=False)
             .head(limit)
             .sort_values('aligned_time')
             .reset_index(drop=True)) 
    
    return result.iloc

def heikin_ashi(symbol='XAUUSD', tf='3m', limit=100):
   
    tf_lower = tf.lower()
    
    if tf_lower.endswith('m'):
        tf_minutes = int(tf_lower.replace('m', ''))
        base_tf = mt5.TIMEFRAME_M1
    elif tf_lower.endswith('h'):
        tf_hours = int(tf_lower.replace('h', ''))
        tf_minutes = tf_hours 
        base_tf = mt5.TIMEFRAME_H1
    elif tf_lower.endswith('d'):
        tf_days = int(tf_lower.replace('d', ''))
        tf_minutes = tf_days * 24
        base_tf = mt5.TIMEFRAME_H1
    else:
        raise ValueError("فرمت تایم‌فریم نامعتبر است")
    
    total_minutes = tf_minutes * limit * 2
    
    raw_data = mt5.copy_rates_from_pos(symbol, base_tf, 0, total_minutes)
    if raw_data is None or len(raw_data) == 0:
        print(f"هیچ داده‌ای برای نماد {symbol} یافت نشد")
        return pd.DataFrame()
    
    df = pd.DataFrame(raw_data, columns=['time', 'open', 'high', 'low', 'close', 'tick_volume'])
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    if tf_lower.endswith('m'):
        df['aligned_time'] = df['time'].dt.floor(f'{tf_minutes}min')
    elif tf_lower.endswith('h'):
        df['aligned_time'] = df['time'].dt.floor(f'{tf_hours}h')
    elif tf_lower.endswith('d'):
        df['aligned_time'] = df['time'].dt.floor(f'{tf_days}d')
    
    resampled = df.groupby('aligned_time').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'tick_volume': 'sum'
    }).reset_index()
    
    df = (resampled
          .sort_values('aligned_time', ascending=False)
          .head(limit)
          .sort_values('aligned_time')
          .set_index('aligned_time'))
    
    ha_df = pd.DataFrame(index=df.index)
    
    ha_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    
    ha_df['open'] = 0.0
    ha_df.iloc[0, ha_df.columns.get_loc('open')] = df['open'].iloc[0]
    
    for i in range(1, len(df)):
        ha_df.iloc[i, ha_df.columns.get_loc('open')] = (
            ha_df['open'].iloc[i-1] + ha_df['close'].iloc[i-1]
        ) / 2
    
    ha_df['high'] = ha_df[['open', 'close']].max(axis=1).combine(df['high'], max)
    ha_df['low'] = ha_df[['open', 'close']].min(axis=1).combine(df['low'], min)
    
    return ha_df.iloc

def check_candle(symbol , tf , cdl = -1 , candle_type = 'ca'):
    
    if candle_type == 'ca':
        ohlc = candle(symbol, tf)
    else:
        ohlc = heikin_ashi(symbol, tf)

    if ohlc[cdl]['open'] > ohlc[cdl]['close']:
        return 'short'
    else:
        return 'long'
    
def isBeta(symbol , tf , index = -1 ):
    candles = candle(symbol, tf)
    res = candles[index]
    if res['open'] > res['close']:
        # short kandel
        if res['open'] == res['high'] :
            return True
        else:
            return False
        
    elif res['open'] < res['close']:
        # long kandel
        if res['open'] == res['low'] :
            return True
        else:
            return False
    else:
        return False
    
def isBack(symbol , tf , index = -1 , upOrDown = 'up' ):
    candles = candle(symbol, tf)
    res = candles[index]
    if res['open'] > res['close']:
        # short kandel
        if upOrDown == 'up'and (res['open'] - res['close'])*3 < res['high'] - res['open'] :
            return True
        elif upOrDown == 'down'and (res['open'] - res['close'])*4 < res['close'] - res['low']:
            return True
        else:
            return False
        
    elif res['open'] < res['close']:
        # long kandel
        if upOrDown == 'up'and (res['close'] - res['open'])*4 < res['high'] - res['close'] :
            return True
        
        elif upOrDown == 'down'and (res['close'] - res['open'])*3 < res['open'] - res['low'] :
            return True
        
        else:
            return False
    else:
        return False

def body(symbol, tf , index = -1):
    candles = candle(symbol, tf)
    res = candles[index]
    if res['open'] > res['close']:
        # short kandel
        body = res['open'] - res['close']
        return body
        
    elif res['open'] < res['close']:
        # long kandel
        body = res['close'] - res['open']
        return body
    else:
        return 0
    
def isgap(symbol, tf):
    candles = candle(symbol, tf)
    #long
    if candles[-1]['open'] > candles[-2]['close'] and check_candle(symbol, tf , -1) == 'long' and check_candle(symbol, tf , -2) == 'long':
        return True
    #short
    if candles[-1]['open'] < candles[-2]['close'] and check_candle(symbol, tf , -1) == 'short' and check_candle(symbol, tf , -2) == 'short':
        return True
    else:
        return False
    
def check_time(start_hour, end_hour):
    current_time = datetime.datetime.now(datetime.UTC).time()
    if current_time.hour >= start_hour and current_time.hour <= end_hour:
        return True
    else:
        return False
    
def check_time_min(start_hour, start_minute, end_hour, end_minute):

    current_time = datetime.datetime.now(datetime.UTC).time()
   
    start_time = datetime.time(start_hour, start_minute)
    end_time = datetime.time(end_hour, end_minute)
    
    if start_time <= current_time <= end_time:
        return True
    else:
        return False

def last_open_position_minutes(symbol):
    BROKER_TIMEZONE_OFFSET = datetime.timedelta(hours=get_broker_offset())
    positions = mt5.positions_get(symbol=symbol)
    if not positions or len(positions) == 0:
        return 0 
    last_position_time = max(position.time for position in positions)
    last_position_datetime_utc = datetime.datetime.fromtimestamp(last_position_time, tz=datetime.timezone.utc)
    server_time = mt5.symbol_info_tick(symbol).time
    server_datetime = datetime.datetime.fromtimestamp(server_time, tz=datetime.timezone.utc)
    last_position_datetime_broker = last_position_datetime_utc + BROKER_TIMEZONE_OFFSET
    now_broker = server_datetime + BROKER_TIMEZONE_OFFSET
    difference = now_broker - last_position_datetime_broker
    minutes_passed = difference.total_seconds() / 60

    return round(minutes_passed)

def count_consecutive_sl():
    time_difference = datetime.timedelta(hours=get_broker_offset())
    mt5_now = datetime.datetime.now(datetime.timezone.utc) + time_difference
    start_of_day = (datetime.datetime(mt5_now.year, mt5_now.month, mt5_now.day, tzinfo=datetime.timezone.utc) + time_difference) 
    orders = mt5.history_deals_get(start_of_day, mt5_now)

    consecutive_sl_count = 0

    for order in orders:
        if order.profit < 0:  # Stop Loss
            consecutive_sl_count += 1
        elif order.profit > 0:  # Take Profit
            consecutive_sl_count = 0  # Reset count on TP

    return consecutive_sl_count

def modify_stop(ticket, new_stop_loss):

    position = mt5.positions_get(ticket=ticket)
    if not position:
        return False
    
    position = position[0]

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_stop_loss,
        "tp": position.tp,
        "symbol": position.symbol,
        "type": position.type,
        "volume": position.volume,
    }

    result = mt5.order_send(request)

def modify_tp(ticket, new_tp):

    position = mt5.positions_get(ticket=ticket)
    if not position:
        return False
    
    position = position[0]

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": position.sl,
        "tp": new_tp,
        "symbol": position.symbol,
        "type": position.type,
        "volume": position.volume,
    }

    result = mt5.order_send(request)

def pending_order(symbol , lot , order_type , price , sl = 0.0 , tp= 0.0 , comment = 'hashem'):
    request={
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl" : sl,
        "tp" : tp,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        }
    order = mt5.order_send(request)
    return order

def remove_order(ticket):
    request={
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
    }
    res = mt5.order_send(request)
    return res
 
def close_all_pending_orders():
    positions = mt5.orders_get()
    if positions is None:
        return

    for position in positions:
        p_ticket = position.ticket
        remove_order(p_ticket)

def close_half_with_comment(comment):
  
    positions = mt5.positions_get()
    
    positions_with_comment = [pos for pos in positions if pos.comment == comment]
    
    half_count = len(positions_with_comment) // 2

    for i, position in enumerate(positions_with_comment):
        if i >= half_count:
            break
         
        p_ticket = position.ticket
       
        close_order(p_ticket)

def close_all_with_comment(comment):
  
    positions = mt5.positions_get()
    
    positions_with_comment = [pos for pos in positions if pos.comment == comment]
    
    for position in positions_with_comment :
         
        p_ticket = position.ticket
      
        close_order(p_ticket)

def fvg(symbol , tf):
    candles = candle(symbol , tf )
    if candles[-2]['high'] < candles[-4]['low'] and check_candle(symbol ,tf , -2 ) == 'short' and check_candle(symbol ,tf , -3) == 'short' :
        return True
    elif candles[-2]['low'] > candles[-4]['high'] and check_candle(symbol ,tf , -2) == 'long' and check_candle(symbol ,tf , -3) == 'long' :
        return True
    else:
        return False
    
    
#news --------------------------


cache = {
    'news_data': None,
    'last_updated': None
}

def fetch_economic_news(currency='USD'):
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    response = requests.get(url)
    data = response.json()
    
    news_data = []
    for event in data:
        if event['country'] == currency and event['impact'] == 'High':
            event_date = event['date']
            event_time = datetime.datetime.strptime(event_date, "%Y-%m-%dT%H:%M:%S%z")
            news_data.append({
                'time': event_time,
                'event': event['title']
            })
    
    return news_data

def is_during_important_news(news_data, check_time):
    for news in news_data:
        news_time = news['time']
        if check_time <= news_time < (check_time + datetime.timedelta(minutes=30)):
            return True
    return False

def is_upcoming_news(news_data, check_time):
    for news in news_data:
        news_time = news['time']
        if datetime.timedelta(0) < (news_time - check_time) <= datetime.timedelta(hours=1):
            return True
    return False

def is_holiday_or_bank_holiday(news_data, check_time):
    for news in news_data:
        event_title = news['event'].lower()
        news_time = news['time']
        
        if 'holiday' in event_title or 'bank holiday' in event_title:
            time_diff = abs((news_time - check_time).total_seconds())
            if time_diff <= 12 * 3600: 
                return True
    return False

def is_news(currency='USD'):
    global cache
    current_time = datetime.datetime.now(datetime.timezone.utc)
    
    if cache['last_updated'] is None or (current_time - cache['last_updated']).total_seconds() > 1800:
        cache['news_data'] = fetch_economic_news(currency)
        cache['last_updated'] = current_time
    
    news_data = cache['news_data']
    
    if (is_during_important_news(news_data, current_time) or 
        is_upcoming_news(news_data, current_time) or 
        is_holiday_or_bank_holiday(news_data, current_time)):
        return True
    
    return False

def get_news_status_details(currency='USD'):
    global cache
    current_time = datetime.datetime.now(datetime.timezone.utc)
    
    if cache['last_updated'] is None or (current_time - cache['last_updated']).total_seconds() > 1800:
        cache['news_data'] = fetch_economic_news(currency)
        cache['last_updated'] = current_time
    
    news_data = cache['news_data']
    
    status = {
        'during_news': is_during_important_news(news_data, current_time),
        'upcoming_news': is_upcoming_news(news_data, current_time),
        'holiday': is_holiday_or_bank_holiday(news_data, current_time),
        'should_avoid_trading': False
    }
    
    status['should_avoid_trading'] = any([
        status['during_news'],
        status['upcoming_news'],
        status['holiday']
    ])
    
    return status


#end news ----------------



def lot_calculator(symbol: str, risk: int, open_price: float, stop_loss: float) -> float:
    import math
    account_balance = mt5.account_info().balance
    amount_of_risk = account_balance * (risk / 100)
    
    price_distance = abs(stop_loss - open_price)
    
    base_symbol = symbol.replace('.', '').replace('_i', '')
    
    raw_lot_size = 0
    
    if 'XAU' in base_symbol:
        raw_lot_size = amount_of_risk / (price_distance * 100)
    
    elif 'JPY' in base_symbol:
        pip_size = 0.01
        stop_pips = price_distance / pip_size
        pip_value = (amount_of_risk / stop_pips) * stop_loss
        raw_lot_size = pip_value / 1000
    
    elif 'BTC' in base_symbol:
        pip_size = 1.00
        stop_pips = price_distance / pip_size
        raw_lot_size = amount_of_risk / stop_pips
    
    elif base_symbol == 'USDCAD':
        pip_size = 0.0001
        stop_pips = price_distance / pip_size
        pip_value = (amount_of_risk / stop_pips) * stop_loss
        raw_lot_size = pip_value / 10
    
    elif base_symbol in ['EURUSD', 'GBPUSD', 'USDCHF', 'AUDUSD', 'NZDUSD', 'EURGBP', 'EURJPY', 'GBPJPY']:
        pip_size = 0.0001
        stop_pips = price_distance / pip_size
        pip_value = amount_of_risk / stop_pips
        raw_lot_size = pip_value / 10
    
    else:
        return 0.01
    
    lot_size = math.floor(raw_lot_size * 100) / 100.0
    
    if lot_size < 0.01:
        lot_size = 0.01
    
    return lot_size



def pnl_today() : 
    def broker_now(h = 0 ) : 
        custom_utc_offset = datetime.timedelta(hours=h)
        custom_timezone = pytz.FixedOffset(custom_utc_offset.total_seconds() // 60)

        return datetime.datetime.now(custom_timezone)


    profit = 0

    now = broker_now(get_broker_offset())
    from_time = datetime.datetime(now.year , now.month , now.day , 0 , 0 , 0 , 0)
    to_time =  from_time + datetime.timedelta(days=1)

    history = mt5.history_deals_get(from_time ,to_time )

    for position in history : 
        profit += position.commission
        profit += position.swap
        profit += position.profit
        profit += position.fee

    
    positions = mt5.positions_get()

    for i in positions : 
        position = i._asdict()
        profit += position['swap']
        profit += position['profit']


    return round(profit , 2)




def daily_draw_down_checker(Start_balance , daily_drow_down) : 
    pnl = pnl_today()
    if pnl < 0 : 
        if (abs(pnl)) >= (Start_balance * (daily_drow_down / 100)) : 
            return True
        else : 
            return False
    else : 
        return False




def total_draw_down(total_bls = 5000 , full_drow_down = 12):
    equity = mt5.account_info().equity
    if equity - total_bls < 0 : 
        if abs(equity - total_bls) >= (total_bls * (full_drow_down / 100)) : 
            return True
        else : 
            return False
    else : 
        return False
    
    
    

def count_position_now(type , symbol):
    positions = mt5.positions_get()
    buy = 0
    sell = 0
    for position in positions :
        if position.type == 0 and position.symbol == symbol :
            buy += 1

        if position.type == 1 and position.symbol == symbol :
            sell += 1
    if type == 'buy':
        return buy
    else:
        return sell



def risk_corrector(risk ,starting_balance , rr = 2 ,max_risk = 100) :
    
    total_trades = count_tp() + 1
    
    initial_risk_amount = starting_balance * (risk / 100)
    target_total_profit = initial_risk_amount * rr * total_trades
    
    current_profit = profit_today()
    profit_deficit = target_total_profit - current_profit
    
    if profit_deficit <= 0:
        return risk
    
    adjusted_risk_amount = profit_deficit / rr
    adjusted_risk_percentage = (adjusted_risk_amount / starting_balance) * 100

    adjusted_risk_percentage = round(adjusted_risk_percentage, 2)
    
    adjusted_risk_percentage = max(adjusted_risk_percentage, risk)  
    adjusted_risk_percentage = min(adjusted_risk_percentage, max_risk)  
       
    
    return adjusted_risk_percentage



def risk_corrector_comment(comment , risk ,starting_balance , rr = 2 ,max_risk = 100) :
    
    total_trades = count_org_tp_comment(comment) + 1
    
    initial_risk_amount = starting_balance * (risk / 100)
    target_total_profit = initial_risk_amount * rr * total_trades
    
    current_profit = total_profit_today_with_comment(comment)
    profit_deficit = target_total_profit - current_profit
    
    if profit_deficit <= 0:
        return risk
    
    adjusted_risk_amount = profit_deficit / rr
    adjusted_risk_percentage = (adjusted_risk_amount / starting_balance) * 100

    adjusted_risk_percentage = round(adjusted_risk_percentage, 2)
    
    adjusted_risk_percentage = max(adjusted_risk_percentage, risk)  
    adjusted_risk_percentage = min(adjusted_risk_percentage, max_risk)  
       
    
    return adjusted_risk_percentage


def total_position_comment(comment):
    positions = mt5.positions_get()
    total = 0
    for position in positions :
        if position.comment == comment :
            total += 1

    return total


def count_sl_between_hours(comment, start_hour, end_hour):
    mt5_now = datetime.datetime.now(datetime.timezone.utc)
    today = mt5_now.date()
    
    broker_offset = get_broker_offset()
    
    start_hour_adjusted = (start_hour + broker_offset) % 24
    start_day_offset = (start_hour + broker_offset) // 24
    
    end_hour_adjusted = (end_hour + broker_offset) % 24
    end_day_offset = (end_hour + broker_offset) // 24
    
    start_time = datetime.datetime.combine(
        today + datetime.timedelta(days=start_day_offset), 
        datetime.time(hour=start_hour_adjusted)
    ).replace(tzinfo=datetime.timezone.utc)
    
    end_time = datetime.datetime.combine(
        today + datetime.timedelta(days=end_day_offset), 
        datetime.time(hour=end_hour_adjusted)
    ).replace(tzinfo=datetime.timezone.utc)
    
    deals = mt5.history_deals_get(start_time, end_time)
    
    if deals is None:
        print("No deals found.")
        return 0
    
    position_ids = set(
        deal.position_id for deal in deals 
        if deal.comment == comment and deal.type in (mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_SELL)
    )
    
    stop_count = sum(
        1 for deal in deals 
        if deal.position_id in position_ids and deal.profit < 0
    )
    
    return stop_count



def close_all_pending_orders_with_type(type = 'buy'):
    positions = mt5.orders_get()
    if positions is None:
        return

    for position in positions:
        if type == 'buy' and position.type == 2 :
            p_ticket = position.ticket
            remove_order(p_ticket)
        if type == 'sell' and position.type == 3 :
            p_ticket = position.ticket
            remove_order(p_ticket) 
