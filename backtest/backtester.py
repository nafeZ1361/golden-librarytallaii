from .hashem_backtest import *
from .indicators import *
from datetime import datetime
import MetaTrader5 as mt5

mt5.initialize()

symbol = 'XAUUSD.'
tf = '3m'
BACKTEST_DAYS = 30

USE_RISK_FREE = False
RISK_FREE_DISTANCE_PIPS = 50.0

USE_SL = True
SL_PIPS = 100.0

USE_TP = True
TP_PIPS = 200.0

CLOSE_OPPOSITE_POSITION = False  #بستن پوزیشن وقتی سیگنال مخالف صادر شه
INITIAL_BALANCE = 5000.0

POSITION_SIZE_MODE = 'risk_percent'  # 'fixed' or 'risk_percent' 
FIXED_LOT_SIZE = 0.01
RISK_PERCENT = 2
RISK_BASED_ON = 'initial'  # 'initial' or 'current'

ANALYZE_WEEKDAYS = True
ANALYZE_TIME_SESSIONS = True
SESSION_DURATION_HOURS = 4.0  # (minimum 0.5)


minutes = extract_number(tf)
limit = int(BACKTEST_DAYS*1440/minutes)
df = backtest_candle(symbol, tf , limit)
limit = len(df)

signal = backtest_supertrend(symbol, tf, limit, atr_period=10, multiplier=3.0, candle_type='ha')['signal']
confirmation_result = backtest_trend_ali(symbol, tf, limit, length=60, length_mult=6.0, mode='Hma', candle_type='ha')['trend']
confirmation = confirmation_result




if len(signal) > len(df):
    signal = signal[-len(df):]
if len(confirmation) > len(df):
    confirmation = confirmation[-len(df):]
if len(signal) < len(df):
    signal = signal + ['hold'] * (len(df) - len(signal))
if len(confirmation) < len(df):
    confirmation = confirmation + ['hold'] * (len(df) - len(confirmation))

backtest(df, signal, confirmation, symbol=symbol, tf=tf, backtest_days=BACKTEST_DAYS,
         use_risk_free=USE_RISK_FREE, risk_free_distance_pips=RISK_FREE_DISTANCE_PIPS,
         use_sl=USE_SL, sl_pips=SL_PIPS, use_tp=USE_TP, tp_pips=TP_PIPS,
         close_opposite_position=CLOSE_OPPOSITE_POSITION, initial_balance=INITIAL_BALANCE,
         position_size_mode=POSITION_SIZE_MODE, fixed_lot_size=FIXED_LOT_SIZE,
         risk_percent=RISK_PERCENT, risk_based_on=RISK_BASED_ON, analyze_weekdays=ANALYZE_WEEKDAYS,
         analyze_time_sessions=ANALYZE_TIME_SESSIONS, session_duration_hours=SESSION_DURATION_HOURS)




