from .hashem_backtest import *
from .indicators import *
import itertools
import hashlib
from tqdm import tqdm
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import os


DEFAULT_PARAMS = {
    'ema': {
        'window': [5 , 10 , 15, 20 , 30 , 40, 50 , 70, 100 , 150 , 170 , 200]
    },
    'ema_cross': {
        'fast_period': [10,15, 20,25 , 30 , 35 ,40 , 45, 50],
        'slow_period': [20 , 30 , 40, 50, 70 , 90 , 100,130 , 150, 170 , 200]
    },
    'macd': {
        'fast': [10 , 12 , 15, 17 , 20],
        'slow': [10 , 21, 26, 34 , 50],
        'signal': [5, 9, 13]
    },
    'super_trend': {
        'atr_period': [5, 10 , 12 ,13 ,14, 15, 20],
        'multiplier': [2.0, 3.0, 4.0 , 5.0]
    },
    'ut_bot': {
        'key_value': [2, 3, 4, 5 , 6, 7],
        'atr_period': [8, 10, 12, 14 , 16]
    },
    'kalman_trend': {
        'sell_len': [5 , 10 , 20 , 30 ,40 , 50 , 60, 70 , 80],
        'buy_len': [50 ,70 ,100, 150, 200]
    },
    'trend_ali': {
        'length': [60],
        'length_mult': [6.0],
        'mode': ['Hma']
    },
    'half_trend': {
        'amplitude': [2, 3, 4 , 5 ,6],
        'channel_deviation': [2, 3]
    },
    'volumatic_vidya': {
        'vidya_length': [8, 10, 12],
        'vidya_momentum': [15, 20, 25],
        'band_distance': [1.5, 2.0, 2.5]
    },
    'deviation_trend': {
        'sma_length': [10 , 20 ,30, 40 , 50, 70]
    },
    'stoch_rsi': {
        'rsi_length': [9, 14, 21],
        'stoch_length': [9, 14, 21],
        'k_period': [3, 5, 7],
        'd_period': [3, 5, 7]
    }
}


def get_indicator_signals(df, symbol, tf , indicator_name, params):
    try:
        if indicator_name == 'ema':
            window = params.get('window', 20)
            signals = backtest_ema(symbol, tf, window, len(df))
            confirmation = signals
            
        elif indicator_name == 'ema_cross':
            fast_period = params.get('fast_period', 20)
            slow_period = params.get('slow_period', 50)
            
            # Skip invalid combinations
            if fast_period >= slow_period:
                return None, None
                
            result = backtest_ema_cross(symbol, tf, len(df), fast_period, slow_period)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'macd':
            fast = params.get('fast', 12)
            slow = params.get('slow', 26)
            signal_length = params.get('signal', 9)
            
            # Skip invalid combinations
            if fast >= slow:
                return None, None
                
            result = backtest_macd(symbol, tf, len(df), fast, slow, signal_length)
            signals = ['buy' if hist > 0 else 'sell' if hist < 0 else 'hold' 
                      for hist in result['histogram']]
            confirmation = signals
            
        elif indicator_name == 'supertrend':
            atr_period = params.get('atr_period', 10)
            multiplier = params.get('multiplier', 3.0)
            result = backtest_supertrend(symbol, tf, len(df), atr_period, multiplier)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'ut_bot':
            key_value = params.get('key_value', 3)
            atr_period = params.get('atr_period', 10)
            result = backtest_ut_bot(symbol, tf, len(df), key_value, atr_period)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'kalman_trend':
            sell_len = params.get('sell_len', 50)
            buy_len = params.get('buy_len', 150)
            
            if sell_len >= buy_len:
                return None, None
                
            result = backtest_kalman_trend_levels(symbol, tf, len(df), sell_len, buy_len)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'trend_ali':
            length = params.get('length', 60)
            length_mult = params.get('length_mult', 6.0)
            mode = params.get('mode', 'Hma')
            result = backtest_trend_ali(symbol, tf, len(df), length, length_mult, mode)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'half_trend':
            amplitude = params.get('amplitude', 2)
            channel_deviation = params.get('channel_deviation', 2)
            result = backtest_half_trend(symbol, tf, len(df), amplitude, channel_deviation)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'volumatic_vidya':
            vidya_length = params.get('vidya_length', 10)
            vidya_momentum = params.get('vidya_momentum', 20)
            band_distance = params.get('band_distance', 2)
            result = backtest_volumatic_vidya(symbol, tf, len(df), vidya_length, vidya_momentum, band_distance)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'deviation_trend':
            sma_length = params.get('sma_length', 50)
            result = backtest_deviation_trend_signals(symbol, tf, len(df), sma_length)
            signals = result['signal']
            confirmation = result['trend']
            
        elif indicator_name == 'stochrsi':
            rsi_length = params.get('rsi_length', 14)
            stoch_length = params.get('stoch_length', 14)
            k_period = params.get('k_period', 3)
            d_period = params.get('d_period', 3)
            k_line = backtest_stochrsi(symbol, tf, len(df), 'blue', rsi_length, stoch_length, k_period, d_period)
            d_line = backtest_stochrsi(symbol, tf, len(df), 'red', rsi_length, stoch_length, k_period, d_period)
            signals = ['buy' if k > d else 'sell' if k < d else 'hold' 
                      for k, d in zip(k_line, d_line)]
            confirmation = signals
            
        else:
            raise ValueError(f"Indicator {indicator_name} not supported")
            
        return signals, confirmation
        
    except Exception as e:
        return None, None


def backtest_opt(df, trigger_signals, confirmation_signals, symbol, tf, 
             backtest_days, use_risk_free, risk_free_distance_pips,
             use_sl, sl_pips, use_tp, tp_pips,
             close_opposite_position, initial_balance,
             position_size_mode, fixed_lot_size,
             risk_percent, risk_based_on,
             analyze_weekdays, analyze_time_sessions,
             session_duration_hours):
    
    try:
        mt5.initialize()
        symbol_info = mt5.symbol_info(symbol)
        digits = symbol_info.digits
    except:
        digits = 5
    
    pipet = 10 ** -digits
    pip = pipet * 10
    
    def get_pip_value(sym, lot=0.01):
        try:
            import MetaTrader5 as mt5
            info = mt5.symbol_info(sym)
            if info is None:
                raise ValueError(f"Symbol {sym} not found")
            tick_value = info.trade_tick_value
            tick_size = info.trade_tick_size
            digs = info.digits
            profit_currency = info.currency_profit
            pip_size = (10 ** -digs) * 10
            pip_value_in_quote = (pip_size / tick_size) * tick_value
            if profit_currency != "USD":
                convert_symbol_1 = profit_currency + "USD"
                convert_symbol_2 = "USD" + profit_currency
                if mt5.symbol_info(convert_symbol_1):
                    rate = mt5.symbol_info_tick(convert_symbol_1).bid
                    pip_value_in_usd = pip_value_in_quote * rate
                elif mt5.symbol_info(convert_symbol_2):
                    rate = mt5.symbol_info_tick(convert_symbol_2).bid
                    pip_value_in_usd = pip_value_in_quote / rate
                else:
                    raise RuntimeError(f"Cannot find USD conversion rate for {profit_currency}")
            else:
                pip_value_in_usd = pip_value_in_quote
            pip_value_final = pip_value_in_usd * lot
            return round(pip_value_final, 3)
        except:
            pip_values = {
                'XAUUSD': 0.10 * lot / 0.01,
                'EURUSD': 0.10 * lot / 0.01,
                'GBPUSD': 0.10 * lot / 0.01,
                'USDJPY': 0.09 * lot / 0.01,
            }
            return pip_values.get(sym, 0.10 * lot / 0.01)
    
    def calculate_pips(entry_price, exit_price, position_type, pip_value):
        if position_type == 'buy':
            return (exit_price - entry_price) / pip_value
        else:
            return (entry_price - exit_price) / pip_value
    
    def calculate_position_size(balance, sym, sl_pips_val):
        if position_size_mode == 'fixed':
            return fixed_lot_size
        elif position_size_mode == 'risk_percent':
            risk_balance = initial_balance if risk_based_on == 'initial' else balance
            risk_amount = risk_balance * (risk_percent / 100)
            pip_value_per_lot = get_pip_value(sym, 1.0)
            if sl_pips_val > 0 and pip_value_per_lot > 0:
                lot_size = risk_amount / (sl_pips_val * pip_value_per_lot)
                lot_size = max(0.01, round(lot_size, 2))
                return lot_size
            else:
                return fixed_lot_size
        else:
            return fixed_lot_size
    
    if len(df) != len(trigger_signals) or len(df) != len(confirmation_signals):
        return None
    
    positions = []
    current_position = None
    
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown = 0
    max_drawdown_percent = 0
    
    for i in range(len(df)):
        current_bar = df.iloc[i]
        
        new_buy_signal = trigger_signals[i] == 'buy' and confirmation_signals[i] == 'buy'
        new_sell_signal = trigger_signals[i] == 'sell' and confirmation_signals[i] == 'sell'
        
        if close_opposite_position and current_position is not None:
            if (current_position['type'] == 'buy' and new_sell_signal) or \
               (current_position['type'] == 'sell' and new_buy_signal):
                exit_price = current_bar['close']
                pips = calculate_pips(current_position['entry_price'], exit_price,
                                     current_position['type'], pip)
                
                profit_usd = pips * current_position['pip_value_usd']
                
                current_position.update({
                    'exit_index': i,
                    'exit_time': current_bar['time'],
                    'exit_price': exit_price,
                    'exit_reason': 'Manual Close',
                    'profit_usd': profit_usd
                })
                
                positions.append(current_position)
                balance += profit_usd
                
                if balance > peak_balance:
                    peak_balance = balance
                current_drawdown = peak_balance - balance
                current_drawdown_percent = (current_drawdown / peak_balance * 100) if peak_balance > 0 else 0
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                    max_drawdown_percent = current_drawdown_percent
                
                current_position = None
        
        if current_position is None:
            if new_buy_signal:
                lot_size = calculate_position_size(balance, symbol, sl_pips if use_sl else 50)
                pip_value = get_pip_value(symbol, lot_size)
                
                current_position = {
                    'type': 'buy',
                    'entry_index': i,
                    'entry_time': current_bar['time'],
                    'entry_price': current_bar['close'],
                    'risk_free_activated': False,
                    'sl_price': current_bar['close'] - (sl_pips * pip) if use_sl else None,
                    'tp_price': current_bar['close'] + (tp_pips * pip) if use_tp else None,
                    'lot_size': lot_size,
                    'pip_value_usd': pip_value
                }
            elif new_sell_signal:
                lot_size = calculate_position_size(balance, symbol, sl_pips if use_sl else 50)
                pip_value = get_pip_value(symbol, lot_size)
                
                current_position = {
                    'type': 'sell',
                    'entry_index': i,
                    'entry_time': current_bar['time'],
                    'entry_price': current_bar['close'],
                    'risk_free_activated': False,
                    'sl_price': current_bar['close'] + (sl_pips * pip) if use_sl else None,
                    'tp_price': current_bar['close'] - (tp_pips * pip) if use_tp else None,
                    'lot_size': lot_size,
                    'pip_value_usd': pip_value
                }
        
        else:
            unrealized_pips = calculate_pips(current_position['entry_price'], current_bar['close'],
                                             current_position['type'], pip)
            unrealized_profit = unrealized_pips * current_position['pip_value_usd']
            current_equity = balance + unrealized_profit
            
            if current_equity < peak_balance:
                current_drawdown = peak_balance - current_equity
                current_drawdown_percent = (current_drawdown / peak_balance * 100) if peak_balance > 0 else 0
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                    max_drawdown_percent = current_drawdown_percent
            
            if use_risk_free and not current_position['risk_free_activated']:
                if current_position['type'] == 'buy':
                    if current_bar['high'] >= current_position['entry_price'] + (risk_free_distance_pips * pip):
                        current_position['sl_price'] = current_position['entry_price']
                        current_position['risk_free_activated'] = True
                else:
                    if current_bar['low'] <= current_position['entry_price'] - (risk_free_distance_pips * pip):
                        current_position['sl_price'] = current_position['entry_price']
                        current_position['risk_free_activated'] = True
            
            exit_reason = None
            exit_price = None
            
            if current_position['type'] == 'buy':
                if use_tp and current_bar['high'] >= current_position['tp_price']:
                    exit_reason = 'TP'
                    exit_price = current_position['tp_price']
                elif current_position['sl_price'] is not None and current_bar['low'] <= current_position['sl_price']:
                    exit_reason = 'SL'
                    exit_price = current_position['sl_price']
            else:
                if use_tp and current_bar['low'] <= current_position['tp_price']:
                    exit_reason = 'TP'
                    exit_price = current_position['tp_price']
                elif current_position['sl_price'] is not None and current_bar['high'] >= current_position['sl_price']:
                    exit_reason = 'SL'
                    exit_price = current_position['sl_price']
            
            if exit_reason:
                pips = calculate_pips(current_position['entry_price'], exit_price, 
                                     current_position['type'], pip)
                
                profit_usd = pips * current_position['pip_value_usd']
                
                current_position.update({
                    'exit_index': i,
                    'exit_time': current_bar['time'],
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'profit_usd': profit_usd
                })
                
                positions.append(current_position)
                balance += profit_usd
                
                if balance > peak_balance:
                    peak_balance = balance
                current_drawdown = peak_balance - balance
                current_drawdown_percent = (current_drawdown / peak_balance * 100) if peak_balance > 0 else 0
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                    max_drawdown_percent = current_drawdown_percent
                
                current_position = None
    
    if len(positions) == 0:
        return None
    
    total_trades = len(positions)
    winning_trades = [p for p in positions if p['profit_usd'] > 0]
    
    total_profit_usd = sum(p['profit_usd'] for p in positions)
    final_balance = initial_balance + total_profit_usd
    
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    roi = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0
    
    result_dict = {
        'win_rate': win_rate,
        'capital_increase_percent': roi,
        'total_trades': total_trades,
        'max_drawdown_percent': max_drawdown_percent,
        'final_balance': final_balance
    }
    return result_dict


def test_single_combination(args):
    df, symbol, tf, entry_indicator, entry_combo, entry_param_names, conf_indicator, fixed_conf_params, backtest_params = args
    
    entry_params_dict = dict(zip(entry_param_names, entry_combo))
    
    try:
        entry_signals, _ = get_indicator_signals(df, symbol, tf, entry_indicator, entry_params_dict)
        
        if entry_signals is None:
            return None
        
        if conf_indicator and fixed_conf_params:
            _, confirmation = get_indicator_signals(df, symbol, tf, conf_indicator, fixed_conf_params)
        else:
            confirmation = entry_signals
        
        if confirmation is None:
            return None
        
        min_len = min(len(entry_signals), len(confirmation), len(df))
        entry_signals = entry_signals[-min_len:]
        confirmation = confirmation[-min_len:]
        df_sliced = df.iloc[-min_len:].reset_index(drop=True)
        
        result = backtest_opt(df_sliced, entry_signals, confirmation, **backtest_params)
        
        if result is None:
            return None
        
        return {
            'params': entry_params_dict,
            'win_rate': result['win_rate'],
            'roi': result['capital_increase_percent'],
            'total_trades': result['total_trades'],
            'max_drawdown': result['max_drawdown_percent'],
            'final_balance': result['final_balance']
        }
        
    except Exception as e:
        return None


def optimizer(symbol, tf , backtest_days, entry_indicator, entry_params=None, conf_indicator=None, fixed_conf_params=None, max_workers=4):
    
    print("\n" + "="*80)
    print(f"🚀 OPTIMIZER STARTED")
    print("="*80)
    print(f"Symbol: {symbol} | Timeframe: {tf} | Backtest Days: {backtest_days}")
    print(f"Entry Indicator: {entry_indicator}")
    if conf_indicator:
        print(f"Confirmation Indicator: {conf_indicator}")
    print("="*80 + "\n")
    
    # Load data
    minutes = extract_number(tf)
    limit = backtest_days * 1440 / minutes
    
    print("📊 Loading market data...")
    df = backtest_candle(symbol, tf, int(limit))
    print(f"✅ Loaded {len(df)} candles\n")
    
    # Prepare parameters
    if entry_params is None:
        entry_params = DEFAULT_PARAMS.get(entry_indicator, {})
    
    entry_param_names = list(entry_params.keys())
    entry_param_values = list(entry_params.values())
    entry_combinations = list(itertools.product(*entry_param_values))
    
    total_combinations = len(entry_combinations)
    print(f"🔍 Total combinations to test: {total_combinations}\n")
    
    # H3: Effective optimization cap - max 50 combinations
    MAX_TRIALS = 50
    if total_combinations > MAX_TRIALS:
        # Canonical representation + SHA-256 ranking for deterministic selection
        study_seed = f"{symbol}|{tf}|{entry_indicator}"
        combo_with_hashes = []
        for combo in entry_combinations:
            canonical_repr = tuple(str(v) for v in combo)
            hash_input = f"{study_seed}:{canonical_repr}"
            hash_val = hashlib.sha256(hash_input.encode()).hexdigest()
            combo_with_hashes.append((hash_val, combo))
        # Sort by hash for ordering-independent selection
        combo_with_hashes.sort(key=lambda x: x[0])
        # Select exactly MAX_TRIALS combinations
        entry_combinations = [combo for _, combo in combo_with_hashes[:MAX_TRIALS]]
        print(f"[H3] Cap enforced: selected {MAX_TRIALS} of {total_combinations} combinations\n")
    selected_combinations = len(entry_combinations)
    
    # Prepare backtest parameters
    backtest_params = {
        'symbol': symbol,
        'tf': tf,
        'backtest_days': backtest_days,
        'use_risk_free': False,
        'risk_free_distance_pips': 50,
        'use_sl': True,
        'sl_pips': 500,
        'use_tp': True,
        'tp_pips': 1000,
        'close_opposite_position': False,
        'initial_balance': 5000,
        'position_size_mode': 'risk_percent',
        'fixed_lot_size': 0.01,
        'risk_percent': 2,
        'risk_based_on': 'initial',
        'analyze_weekdays': False,
        'analyze_time_sessions': False,
        'session_duration_hours': 4.0
    }
    
    best_result = {
        'params': None,
        'win_rate': -1,
        'roi': -float('inf'),
        'total_trades': 0,
        'max_drawdown': 0,
        'final_balance': 0
    }
    
    valid_results = 0
    
    # Multi-threaded execution
    print(f"⚡ Starting optimization with {max_workers} workers...\n")
    
    args_list = [
        (df, symbol, tf, entry_indicator, combo, entry_param_names, conf_indicator, fixed_conf_params, backtest_params)
        for combo in entry_combinations
    ]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_combination, args): args for args in args_list}
        
        with tqdm(total=selected_combinations, desc="Testing combinations", ncols=100) as pbar:
            for future in as_completed(futures):
                result = future.result()
                
                if result is not None:
                    valid_results += 1
                    
                    # Update best result
                    if result['roi'] > best_result['roi'] or \
                       (result['roi'] == best_result['roi'] and result['win_rate'] > best_result['win_rate']):
                        best_result = result
                        
                        # Update progress bar with best result
                        pbar.set_postfix({
                            'Best ROI': f"{best_result['roi']:.2f}%",
                            'Win Rate': f"{best_result['win_rate']:.1f}%",
                            'Valid': valid_results
                        })
                
                pbar.update(1)
    
    print("\n" + "="*80)
    
    if best_result['params'] is None:
        print("❌ No valid results found!")
        print("="*80 + "\n")
        return {'error': 'هیچ نتیجه معتبری یافت نشد'}
    
    # Save results
    result_data = {
        'symbol': symbol,
        'timeframe': tf,
        'backtest_days': backtest_days,
        'entry_indicator': entry_indicator,
        'confirmation_indicator': conf_indicator,
        'best_parameters': best_result['params'],
        'win_rate': best_result['win_rate'],
        'roi': best_result['roi'],
        'total_trades': best_result['total_trades'],
        'max_drawdown': best_result['max_drawdown'],
        'final_balance': best_result['final_balance'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_combinations_tested': total_combinations,
        'valid_results': valid_results
    }
    
    # Save to JSON
    os.makedirs('optimizer_results', exist_ok=True)
    filename = f"optimizer_results/best_params_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4, ensure_ascii=False)
    
    # Print results
    print("✅ OPTIMIZATION COMPLETED!")
    print("="*80)
    print(f"📊 Results Summary:")
    print(f"   Valid combinations tested: {valid_results}/{total_combinations}")
    print(f"\n🏆 Best Parameters:")
    for key, value in best_result['params'].items():
        print(f"   {key}: {value}")
    print(f"\n📈 Performance Metrics:")
    print(f"   Win Rate: {best_result['win_rate']:.2f}%")
    print(f"   ROI: {best_result['roi']:.2f}%")
    print(f"   Total Trades: {best_result['total_trades']}")
    print(f"   Max Drawdown: {best_result['max_drawdown']:.2f}%")
    print(f"   Final Balance: ${best_result['final_balance']:.2f}")
    print(f"\n💾 Results saved to: {filename}")
    print("="*80 + "\n")
    
    # Return best parameters (same as before)
    return best_result['params']


if __name__ == "__main__":
    
    symbol = 'XAUUSD.'
    tf = '3m'
    BACKTEST_DAYS = 30
    
    # Optional: Fixed confirmation parameters
    # config = {
    #     'amplitude': 2,
    #     'channel_deviation': 2
    # }
    
    result = optimizer(
        symbol=symbol,
        tf=tf,
        backtest_days=BACKTEST_DAYS,
        entry_indicator='kalman_trend',
        conf_indicator='trend_ali',
        # fixed_conf_params=config,
    )
    
    print("🎯 Final Output (Best Parameters):")
    print(result)