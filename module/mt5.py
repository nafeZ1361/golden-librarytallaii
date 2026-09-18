import datetime
import pandas as pd
import MetaTrader5 as mt5
import ta
import pytz
import requests
import logging
import numpy as np
from .execution import ExecutionEngine
from .config import MAGIC_NUMBER
from .paper import PaperBroker
from .risk import bounded_risk_percent

logger = logging.getLogger(__name__)


buy = mt5.ORDER_TYPE_BUY
buy_limit = mt5.ORDER_TYPE_BUY_LIMIT
buy_stop = mt5.ORDER_TYPE_BUY_STOP
sell = mt5.ORDER_TYPE_SELL
sell_limit = mt5.ORDER_TYPE_SELL_LIMIT
sell_stop = mt5.ORDER_TYPE_SELL_STOP
paper_broker = PaperBroker("paper_state.json", magic_number=MAGIC_NUMBER)
execution_engine = ExecutionEngine(mt5, paper_broker=paper_broker)


def get_broker_offset():
    today = datetime.datetime.today().strftime('%A')
    symbol = None
    if today != 'Sunday' and today != 'Saturday':
        symbols = mt5.symbols_get()
        if not symbols:
            return None
        for i in symbols:
            if "xauusd" in i.name.lower():
                symbol = i.name
        if symbol is None:
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

    if not sorted_active_sessions:
        return None

    result = sorted_active_sessions[-1]['name'] 
    

    return result

def create_order(symbol, lot, order_type, sl=0.0, tp=0.0, comment='hashem', trade_id=None, magic=None, daily_profit=0.0, open_positions=0):
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"نماد {symbol} پیدا نشد")
        return None
    
    filling_mode = symbol_info.filling_mode
    if filling_mode == 1:
        filling_mode = mt5.ORDER_FILLING_FOK
    elif filling_mode == 2:
        filling_mode = mt5.ORDER_FILLING_IOC
    else:
        filling_mode = mt5.ORDER_FILLING_FOK 
    
    price_info = mt5.symbol_info_tick(symbol)
    if price_info is None:
        print(f"قیمت لحظه‌ای برای {symbol} دریافت نشد")
        return None
    price = price_info.ask if order_type == buy else price_info.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "order_type": "buy" if str(order_type).lower() in {"0", "buy"} else "sell",
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "comment": comment,
        "magic": int(magic if magic is not None else MAGIC_NUMBER),
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }
    if trade_id:
        request["trade_id"] = str(trade_id)
    
    result = execution_engine.send(request, daily_profit=daily_profit, open_positions=open_positions)
    if result is None:
        print("ارسال سفارش بدون پاسخ از MT5 برگشت")
        return None
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
    if price_info is None:
        print(f"قیمت لحظه‌ای برای بستن {symbol} دریافت نشد")
        return None
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
            "magic": MAGIC_NUMBER,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        result = execution_engine.send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            return result

    print(f"بستن پوزیشن {ticket} ناموفق بود")
    return None

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
    if price_info is None:
        print(f"قیمت لحظه‌ای برای بستن {symbol} دریافت نشد")
        return None
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
            "magic": MAGIC_NUMBER,
            "comment": "Close position",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        result = execution_engine.send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            return result

    print(f"بستن نیمی از پوزیشن {ticket} ناموفق بود")
    return None
     
def close_all_positions():
    positions = mt5.positions_get()
    if not positions:
        return

    for position in positions:
        if getattr(position, "magic", MAGIC_NUMBER) != MAGIC_NUMBER:
            continue
        p_ticket = position._asdict()['ticket']
        close_order(p_ticket)

def close_half_positions():
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return

    half_count = len(positions) // 2

    for i, position in enumerate([p for p in positions if getattr(p, "magic", MAGIC_NUMBER) == MAGIC_NUMBER]):
        if i >= half_count:
            break
        p_ticket = position._asdict()['ticket']
        
        close_order(p_ticket)

def total_positons():
    positions_total=mt5.positions_total()
    return positions_total

def balance():
    account = mt5.account_info()
    return account.balance if account is not None else 0.0

def profit():
    positions = mt5.positions_get()
    profit = 0
    if not positions:
        return profit
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
    """Fetch M1 and resample; this is the canonical live/backtest data path."""
    from .timeframe_data import fetch_m1_resampled
    return fetch_m1_resampled(mt5, symbol, tf, limit).iloc

def heikin_ashi(symbol='XAUUSD', tf='3m', limit=100):
    """Build Heikin-Ashi from the same canonical M1-resampled candles."""
    from .timeframe_data import fetch_m1_resampled
    df = fetch_m1_resampled(mt5, symbol, tf, limit)
    if df.empty:
        return df
    ha = df.copy()
    ha["close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ha["open"] = 0.0
    ha.iloc[0, ha.columns.get_loc("open")] = df["open"].iloc[0]
    for i in range(1, len(ha)):
        ha.iloc[i, ha.columns.get_loc("open")] = (ha["open"].iloc[i-1] + ha["close"].iloc[i-1]) / 2
    ha["high"] = ha[["open", "close", "high"]].max(axis=1)
    ha["low"] = ha[["open", "close", "low"]].min(axis=1)
    return ha

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
        "risk_exempt": True,
    }

    result = execution_engine.send(request)
    return result

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
        "risk_exempt": True,
    }

    result = execution_engine.send(request)
    return result

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
        "magic": MAGIC_NUMBER,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
        }
    order = execution_engine.send(request)
    return order

def remove_order(ticket):
    request={
        "action": mt5.TRADE_ACTION_REMOVE,
        "order": ticket,
        "risk_exempt": True,
    }
    res = execution_engine.send(request)
    return res
 
def close_all_pending_orders():
    positions = mt5.orders_get()
    if not positions:
        return

    for position in positions:
        if getattr(position, "magic", MAGIC_NUMBER) != MAGIC_NUMBER:
            continue
        p_ticket = position.ticket
        remove_order(p_ticket)

def close_half_with_comment(comment):
  
    positions = mt5.positions_get()
    
    positions_with_comment = [pos for pos in positions if pos.comment == comment and getattr(pos, "magic", MAGIC_NUMBER) == MAGIC_NUMBER]
    
    half_count = len(positions_with_comment) // 2

    for i, position in enumerate(positions_with_comment):
        if i >= half_count:
            break
         
        p_ticket = position.ticket
       
        close_order(p_ticket)

def close_all_with_comment(comment):
  
    positions = mt5.positions_get()
    
    positions_with_comment = [pos for pos in positions if pos.comment == comment and getattr(pos, "magic", MAGIC_NUMBER) == MAGIC_NUMBER]
    
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



def risk_corrector(risk, starting_balance, rr=2, max_risk=100):
    """Legacy compatibility wrapper with a hard non-martingale cap."""
    capped = bounded_risk_percent(risk, max_risk=min(float(max_risk), 2.0))
    if capped != float(risk):
        logger.warning("risk_corrector capped requested risk from %s%% to %s%%", risk, capped)
    return capped


def risk_corrector_comment(comment, risk, starting_balance, rr=2, max_risk=100):
    """Legacy compatibility wrapper; comment-based loss chasing is disabled."""
    capped = bounded_risk_percent(risk, max_risk=min(float(max_risk), 2.0))
    if capped != float(risk):
        logger.warning("risk_corrector_comment capped comment=%s from %s%% to %s%%", comment, risk, capped)
    return capped


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
        pass

    for position in positions:
        if type == 'buy' and position.type == 2 :
            p_ticket = position.ticket
            remove_order(p_ticket)
        if type == 'sell' and position.type == 3 :
            p_ticket = position.ticket
            remove_order(p_ticket) 
