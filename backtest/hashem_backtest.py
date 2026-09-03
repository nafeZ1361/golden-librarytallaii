import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import itertools
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import pandas as pd
from datetime import datetime
import warnings
import sys
import io
import yfinance as yf
import re
from datetime import datetime, timedelta
import os
import MetaTrader5 as mt5
warnings.filterwarnings('ignore')


def backtest(df, trigger_signals, confirmation_signals, symbol, tf, 
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
        raise ValueError(f"Length of dataframe and signal lists must match df : {len(df)}, trigger_signals : {len(trigger_signals)}, confirmation_signals : {len(confirmation_signals)}")
    
    positions = []
    current_position = None
    consecutive_sl = 0
    consecutive_tp = 0
    max_consecutive_sl = 0
    max_consecutive_tp = 0
    
    balance = initial_balance
    balance_history = [initial_balance]
    balance_times = [df.iloc[0]['time']]
    peak_balance = initial_balance
    max_drawdown = 0
    max_drawdown_percent = 0
    current_trade_lowest_balance = initial_balance
    
    daily_start_balance = {}
    max_daily_drawdown = 0
    max_daily_drawdown_percent = 0
    
    for i in range(len(df)):
        current_bar = df.iloc[i]
        current_date = pd.to_datetime(current_bar['time']).date()
        
        if current_date not in daily_start_balance:
            daily_start_balance[current_date] = balance
        
        new_buy_signal = trigger_signals[i] == 'buy' and confirmation_signals[i] == 'buy'
        new_sell_signal = trigger_signals[i] == 'sell' and confirmation_signals[i] == 'sell'
        
        if close_opposite_position and current_position is not None:
            if (current_position['type'] == 'buy' and new_sell_signal) or \
               (current_position['type'] == 'sell' and new_buy_signal):
                exit_price = current_bar['close']
                pips = calculate_pips(current_position['entry_price'], exit_price,
                                     current_position['type'], pip)
                
                profit_usd = pips * current_position['pip_value_usd']
                
                if profit_usd < 0:
                    exit_reason = 'SL'
                    consecutive_sl += 1
                    consecutive_tp = 0
                    max_consecutive_sl = max(max_consecutive_sl, consecutive_sl)
                else:
                    exit_reason = 'Manual Close'
                    consecutive_tp = 0
                    consecutive_sl = 0
                
                current_position.update({
                    'exit_index': i,
                    'exit_time': current_bar['time'],
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'profit_usd': profit_usd
                })
                
                positions.append(current_position)
                
                balance += profit_usd
                balance_history.append(balance)
                balance_times.append(current_bar['time'])
                
                current_trade_lowest_balance = balance
                
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
            
            current_trade_lowest_balance = min(current_trade_lowest_balance, current_equity)
            
            if current_equity < peak_balance:
                current_drawdown = peak_balance - current_equity
                current_drawdown_percent = (current_drawdown / peak_balance * 100) if peak_balance > 0 else 0
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                    max_drawdown_percent = current_drawdown_percent
            
            day_start = daily_start_balance.get(current_date, initial_balance)
            if current_equity < day_start:
                daily_dd = day_start - current_equity
                daily_dd_percent = (daily_dd / day_start * 100) if day_start > 0 else 0
                if daily_dd > max_daily_drawdown:
                    max_daily_drawdown = daily_dd
                    max_daily_drawdown_percent = daily_dd_percent
            
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
                balance_history.append(balance)
                balance_times.append(current_bar['time'])
                
                current_trade_lowest_balance = balance
                
                if balance > peak_balance:
                    peak_balance = balance
                current_drawdown = peak_balance - balance
                current_drawdown_percent = (current_drawdown / peak_balance * 100) if peak_balance > 0 else 0
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                    max_drawdown_percent = current_drawdown_percent
                
                if exit_reason == 'SL' and profit_usd < 0:
                    consecutive_sl += 1
                    consecutive_tp = 0
                    max_consecutive_sl = max(max_consecutive_sl, consecutive_sl)
                elif exit_reason == 'TP':
                    consecutive_tp += 1
                    consecutive_sl = 0
                    max_consecutive_tp = max(max_consecutive_tp, consecutive_tp)
                
                current_position = None
    
    if len(positions) == 0:
        print("No trades executed")
        return None
    
    total_trades = len(positions)
    print(f"\n{'='*80}")
    print(f"BACKTEST COMPLETED - TRADE STATISTICS")
    print(f"{'='*80}")
    print(f"Total Trades Executed: {total_trades}")
    
    winning_trades = [p for p in positions if p['profit_usd'] > 0]
    losing_trades = [p for p in positions if p['profit_usd'] < 0]
    breakeven_trades = [p for p in positions if p['profit_usd'] == 0]
    
    total_profit_usd = sum(p['profit_usd'] for p in positions)
    final_balance = initial_balance + total_profit_usd
    
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    print(f"Winning Trades: {len(winning_trades)}")
    print(f"Losing Trades: {len(losing_trades)}")
    print(f"Breakeven Trades: {len(breakeven_trades)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total Profit: ${total_profit_usd:.2f}")
    print(f"Final Balance: ${final_balance:.2f}")
    print(f"ROI: {((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0:.2f}%")
    print(f"{'='*80}\n")
    
    non_breakeven_trades = [p for p in positions if p['profit_usd'] != 0]
    win_rate_no_breakeven = 0
    if len(non_breakeven_trades) > 0:
        winning_no_breakeven = [p for p in non_breakeven_trades if p['profit_usd'] > 0]
        win_rate_no_breakeven = (len(winning_no_breakeven) / len(non_breakeven_trades) * 100)
    
    total_tp = len([p for p in positions if p['exit_reason'] == 'TP'])
    total_sl = len([p for p in positions if p['exit_reason'] == 'SL' and p['profit_usd'] < 0])
    total_manual_close = len([p for p in positions if p['exit_reason'] == 'Manual Close'])
    
    gross_profit_usd = sum(p['profit_usd'] for p in winning_trades) if winning_trades else 0
    gross_loss_usd = abs(sum(p['profit_usd'] for p in losing_trades)) if losing_trades else 0
    
    avg_win_usd = (gross_profit_usd / len(winning_trades)) if winning_trades else 0
    avg_loss_usd = (gross_loss_usd / len(losing_trades)) if losing_trades else 0
    
    roi = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0
    
    profit_factor_usd = (gross_profit_usd / gross_loss_usd) if gross_loss_usd > 0 else float('inf')
    
    avg_lot_size = sum(p['lot_size'] for p in positions) / len(positions) if positions else 0
    
    returns = [p['profit_usd'] for p in positions]
    avg_return = np.mean(returns) if returns else 0
    std_return = np.std(returns) if len(returns) > 1 else 0
    sharpe_ratio = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
    
    weekday_analysis = None
    if analyze_weekdays:
        weekday_profits = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        weekday_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
        
        for p in positions:
            try:
                trade_date = pd.to_datetime(p['entry_time'])
                weekday = trade_date.weekday()
                weekday_profits[weekday] += p['profit_usd']
                weekday_counts[weekday] += 1
            except:
                pass
        
        weekday_analysis = {
            'profits': weekday_profits,
            'counts': weekday_counts
        }
    
    time_session_analysis = None
    if analyze_time_sessions and session_duration_hours >= 0.5:
        session_duration_minutes = int(session_duration_hours * 60)
        
        start_times = []
        for hour in range(24):
            start_times.append(hour * 60)
            if hour < 23 or session_duration_minutes <= 30:
                start_times.append(hour * 60 + 30)
        
        session_profits = {}
        for start_min in start_times:
            end_min = start_min + session_duration_minutes
            if end_min > 24 * 60:
                continue
            
            start_hour = start_min // 60
            start_minute = start_min % 60
            end_hour = end_min // 60
            end_minute = end_min % 60
            
            session_key = f"{start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d}"
            session_profit = 0
            session_count = 0
            
            for p in positions:
                try:
                    entry_time = pd.to_datetime(p['entry_time'])
                    trade_minutes = entry_time.hour * 60 + entry_time.minute
                    
                    if start_min <= trade_minutes < end_min:
                        session_profit += p['profit_usd']
                        session_count += 1
                except:
                    pass
            
            session_profits[session_key] = {
                'profit': session_profit,
                'count': session_count
            }
        
        best_session = max(session_profits.items(), key=lambda x: x[1]['profit']) if session_profits else None
        worst_session = min(session_profits.items(), key=lambda x: x[1]['profit']) if session_profits else None
        
        time_session_analysis = {
            'all_sessions': session_profits,
            'best_session': best_session,
            'worst_session': worst_session
        }
    
    fig_price = go.Figure()
    
    fig_price.add_trace(go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ))
    
    buy_entries = [p for p in positions if p['type'] == 'buy']
    sell_entries = [p for p in positions if p['type'] == 'sell']
    
    if buy_entries:
        fig_price.add_trace(go.Scatter(
            x=[df.iloc[p['entry_index']]['time'] for p in buy_entries],
            y=[p['entry_price'] for p in buy_entries],
            mode='markers',
            marker=dict(symbol='triangle-up', size=15, color='lime', line=dict(width=2, color='darkgreen')),
            name='Buy Entry',
            hovertemplate='Buy Entry<br>Price: %{y:.5f}<extra></extra>'
        ))
    
    if sell_entries:
        fig_price.add_trace(go.Scatter(
            x=[df.iloc[p['entry_index']]['time'] for p in sell_entries],
            y=[p['entry_price'] for p in sell_entries],
            mode='markers',
            marker=dict(symbol='triangle-down', size=15, color='red', line=dict(width=2, color='darkred')),
            name='Sell Entry',
            hovertemplate='Sell Entry<br>Price: %{y:.5f}<extra></extra>'
        ))
    
    tp_exits = [p for p in positions if p['exit_reason'] == 'TP']
    sl_exits = [p for p in positions if p['exit_reason'] == 'SL' and p['profit_usd'] < 0]
    manual_exits = [p for p in positions if p['exit_reason'] == 'Manual Close']
    
    if tp_exits:
        fig_price.add_trace(go.Scatter(
            x=[df.iloc[p['exit_index']]['time'] for p in tp_exits],
            y=[p['exit_price'] for p in tp_exits],
            mode='markers',
            marker=dict(symbol='star', size=12, color='gold', line=dict(width=1, color='orange')),
            name='Take Profit',
            hovertemplate='TP Exit<br>Price: %{y:.5f}<extra></extra>'
        ))
    
    if sl_exits:
        fig_price.add_trace(go.Scatter(
            x=[df.iloc[p['exit_index']]['time'] for p in sl_exits],
            y=[p['exit_price'] for p in sl_exits],
            mode='markers',
            marker=dict(symbol='x', size=12, color='purple', line=dict(width=2)),
            name='Stop Loss',
            hovertemplate='SL Exit<br>Price: %{y:.5f}<extra></extra>'
        ))
    
    if manual_exits:
        fig_price.add_trace(go.Scatter(
            x=[df.iloc[p['exit_index']]['time'] for p in manual_exits],
            y=[p['exit_price'] for p in manual_exits],
            mode='markers',
            marker=dict(symbol='circle-open', size=12, color='orange', line=dict(width=2)),
            name='Manual Close',
            hovertemplate='Manual Close<br>Price: %{y:.5f}<extra></extra>'
        ))
    
    fig_price.update_layout(
        title=f'{symbol} {tf} Price Chart',
        xaxis_title='Time',
        yaxis_title='Price',
        template='plotly_dark',
        height=600,
        xaxis_rangeslider_visible=False,
        hovermode='x unified'
    )
    
    fig_balance = go.Figure()
    
    fig_balance.add_trace(go.Scatter(
        x=balance_times,
        y=balance_history,
        mode='lines',
        name='Balance',
        line=dict(color='cyan', width=2),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 255, 0.1)',
        hovertemplate='Balance: $%{y:.2f}<extra></extra>'
    ))
    
    fig_balance.update_layout(
        title='Balance Curve',
        xaxis_title='Time',
        yaxis_title='Balance ($)',
        template='plotly_dark',
        height=400,
        hovermode='x unified'
    )
    
    fig_weekday_html = ""
    if weekday_analysis:
        fig_weekday = go.Figure()
        
        weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekday_profits_list = [weekday_analysis['profits'][i] for i in range(7)]
        weekday_colors = ['green' if p > 0 else 'red' for p in weekday_profits_list]
        
        fig_weekday.add_trace(go.Bar(
            x=weekday_names,
            y=weekday_profits_list,
            name='Profit by Day',
            marker=dict(color=weekday_colors),
            text=[f'${p:.2f}' for p in weekday_profits_list],
            textposition='outside',
            hovertemplate='%{x}<br>Profit: $%{y:.2f}<extra></extra>'
        ))
        
        fig_weekday.update_layout(
            title='Profit by Weekday',
            xaxis_title='Day of Week',
            yaxis_title='Profit ($)',
            template='plotly_dark',
            height=400,
            showlegend=False
        )
        
        fig_weekday_html = fig_weekday.to_html(include_plotlyjs=False, div_id='weekday_chart')
    
    fig_time_session_html = ""
    time_session_table_html = ""
    if time_session_analysis:
        sessions_data = time_session_analysis['all_sessions']
        
        sessions_with_trades = {k: v for k, v in sessions_data.items() if v['count'] > 0}
        
        if sessions_with_trades:
            sorted_sessions = sorted(sessions_with_trades.items(), key=lambda x: x[1]['profit'], reverse=True)
            
            top_sessions = sorted_sessions[:10]
            session_names = [s[0] for s in top_sessions]
            session_profits = [s[1]['profit'] for s in top_sessions]
            session_counts = [s[1]['count'] for s in top_sessions]
            session_colors = ['green' if p > 0 else 'red' for p in session_profits]
            
            fig_time_session = go.Figure()
            
            fig_time_session.add_trace(go.Bar(
                x=session_names,
                y=session_profits,
                name='Profit by Time Session',
                marker=dict(color=session_colors),
                text=[f'${p:.2f}<br>({c} trades)' for p, c in zip(session_profits, session_counts)],
                textposition='outside',
                hovertemplate='%{x}<br>Profit: $%{y:.2f}<extra></extra>'
            ))
            
            fig_time_session.update_layout(
                title=f'Top 10 Most Profitable Time Sessions ({session_duration_hours}h duration)',
                xaxis_title='Time Session',
                yaxis_title='Profit ($)',
                template='plotly_dark',
                height=500,
                showlegend=False,
                xaxis=dict(tickangle=-45)
            )
            
            fig_time_session_html = fig_time_session.to_html(include_plotlyjs=False, div_id='time_session_chart')
            
            time_session_table_html = '<h2>📊 Best Time Sessions Analysis</h2>'
            time_session_table_html += '<div class="table-container"><table>'
            time_session_table_html += '<thead><tr><th>Rank</th><th>Time Session</th><th>Total Profit</th><th>Trades</th><th>Avg Profit/Trade</th></tr></thead>'
            time_session_table_html += '<tbody>'
            
            for idx, (session, data) in enumerate(sorted_sessions[:15], 1):
                avg_profit = data['profit'] / data['count'] if data['count'] > 0 else 0
                profit_color = 'lime' if data['profit'] > 0 else 'red'
                time_session_table_html += f'''
                <tr>
                    <td>{idx}</td>
                    <td><strong>{session}</strong></td>
                    <td style="color: {profit_color}; font-weight: bold;">${data['profit']:.2f}</td>
                    <td>{data['count']}</td>
                    <td style="color: {profit_color};">${avg_profit:.2f}</td>
                </tr>'''
            
            time_session_table_html += '</tbody></table></div>'
            
            if time_session_analysis['best_session']:
                best = time_session_analysis['best_session']
                worst = time_session_analysis['worst_session']
                time_session_table_html += f'''
                <div class="stats-grid" style="margin-top: 20px;">
                    <div class="stat-card">
                        <div class="stat-label">🏆 Best Time Session</div>
                        <div class="stat-value positive">{best[0]}</div>
                        <div class="stat-label">Profit: ${best[1]['profit']:.2f} ({best[1]['count']} trades)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">⚠️ Worst Time Session</div>
                        <div class="stat-value negative">{worst[0]}</div>
                        <div class="stat-label">Loss: ${worst[1]['profit']:.2f} ({worst[1]['count']} trades)</div>
                    </div>
                </div>'''
    
    chart_price_html = fig_price.to_html(include_plotlyjs='cdn', div_id='price_chart')
    chart_balance_html = fig_balance.to_html(include_plotlyjs=False, div_id='balance_chart')
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Forex Backtest Report - {symbol}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); color: #fff; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); }}
        h1 {{ text-align: center; margin-bottom: 10px; font-size: 2.5em; background: linear-gradient(45deg, #FFD700, #FFA500); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .subtitle {{ text-align: center; color: #aaa; margin-bottom: 30px; font-size: 1.1em; }}
        .chart-container {{ background: rgba(255, 255, 255, 0.08); border-radius: 15px; padding: 20px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05)); border-radius: 15px; padding: 20px; border: 1px solid rgba(255, 255, 255, 0.1); transition: transform 0.3s; }}
        .stat-card:hover {{ transform: translateY(-5px); box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3); }}
        .stat-label {{ font-size: 0.9em; color: #aaa; margin-bottom: 10px; }}
        .stat-value {{ font-size: 2em; font-weight: bold; color: #fff; }}
        .stat-value.positive {{ color: #00ff88; }}
        .stat-value.negative {{ color: #ff4757; }}
        .table-container {{ background: rgba(255, 255, 255, 0.08); border-radius: 15px; padding: 20px; overflow-x: auto; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; color: #fff; }}
        th {{ background: rgba(255, 255, 255, 0.15); padding: 15px; text-align: center; font-weight: 600; border-bottom: 2px solid rgba(255, 255, 255, 0.2); }}
        td {{ padding: 12px; text-align: center; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }}
        tr:hover {{ background: rgba(255, 255, 255, 0.05); }}
        .badge {{ padding: 5px 12px; border-radius: 20px; font-size: 0.85em; font-weight: bold; display: inline-block; }}
        .badge-buy {{ background: linear-gradient(135deg, #00ff88, #00cc6a); color: #000; }}
        .badge-sell {{ background: linear-gradient(135deg, #ff4757, #cc3644); color: #fff; }}
        .badge-tp {{ background: linear-gradient(135deg, #ffd700, #ffa500); color: #000; }}
        .badge-sl {{ background: linear-gradient(135deg, #9b59b6, #8e44ad); color: #fff; }}
        .badge-manual {{ background: linear-gradient(135deg, #f39c12, #e67e22); color: #fff; }}
        h2 {{ margin: 30px 0 20px 0; color: #FFD700; font-size: 1.8em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Forex Backtest Report</h1>
        <div class="subtitle">{symbol} | {tf} | {backtest_days} days | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
        <div class="chart-container">{chart_price_html}</div>
        <div class="chart-container">{chart_balance_html}</div>
        {f'<div class="chart-container">{fig_weekday_html}</div>' if fig_weekday_html else ''}
        {f'<div class="chart-container">{fig_time_session_html}</div>' if fig_time_session_html else ''}
        {time_session_table_html}
        <h2>General Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-label">Initial Balance</div><div class="stat-value">${initial_balance:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Final Balance</div><div class="stat-value {'positive' if final_balance > initial_balance else 'negative'}">${final_balance:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Total Profit/Loss</div><div class="stat-value {'positive' if total_profit_usd > 0 else 'negative'}">${total_profit_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">ROI</div><div class="stat-value {'positive' if roi > 0 else 'negative'}">{roi:.2f}%</div></div>
            <div class="stat-card"><div class="stat-label">Max Drawdown</div><div class="stat-value negative">${max_drawdown:.2f} ({max_drawdown_percent:.2f}%)</div></div>
            <div class="stat-card"><div class="stat-label">Max Daily Drawdown</div><div class="stat-value negative">${max_daily_drawdown:.2f} ({max_daily_drawdown_percent:.2f}%)</div></div>
            <div class="stat-card"><div class="stat-label">Sharpe Ratio</div><div class="stat-value">{sharpe_ratio:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Total Trades</div><div class="stat-value">{total_trades}</div></div>
            <div class="stat-card"><div class="stat-label">Win Rate</div><div class="stat-value {'positive' if win_rate >= 50 else 'negative'}">{win_rate:.2f}%</div></div>
            <div class="stat-card"><div class="stat-label">Win Rate (No BE)</div><div class="stat-value">{win_rate_no_breakeven:.2f}%</div></div>
            <div class="stat-card"><div class="stat-label">Profit Factor</div><div class="stat-value">{profit_factor_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Winning Trades</div><div class="stat-value positive">{len(winning_trades)}</div></div>
            <div class="stat-card"><div class="stat-label">Losing Trades</div><div class="stat-value negative">{len(losing_trades)}</div></div>
            <div class="stat-card"><div class="stat-label">Average Win</div><div class="stat-value positive">${avg_win_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Average Loss</div><div class="stat-value negative">${avg_loss_usd:.2f}</div></div>
            <div class="stat-card"><div class="stat-label">Average Lot Size</div><div class="stat-value">{avg_lot_size:.2f}</div></div>
        </div>
        <h2>Trade Details</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>#</th><th>Type</th><th>Lot Size</th><th>Entry Time</th><th>Entry Price</th><th>Exit Time</th><th>Exit Price</th><th>Exit Reason</th><th>Profit/Loss</th></tr>
                </thead>
                <tbody>"""
    
    for idx, p in enumerate(positions, 1):
        usd_color = 'lime' if p['profit_usd'] > 0 else 'red' if p['profit_usd'] < 0 else 'gray'
        exit_badge = 'tp' if p['exit_reason'] == 'TP' else 'sl' if p['exit_reason'] == 'SL' else 'manual'
        html += f"""
                    <tr>
                        <td>{idx}</td>
                        <td><span class="badge badge-{p['type']}">{p['type'].upper()}</span></td>
                        <td>{p['lot_size']:.2f}</td>
                        <td>{p['entry_time']}</td>
                        <td>{p['entry_price']:.5f}</td>
                        <td>{p['exit_time']}</td>
                        <td>{p['exit_price']:.5f}</td>
                        <td><span class="badge badge-{exit_badge}">{p['exit_reason']}</span></td>
                        <td style="color: {usd_color}; font-weight: bold;">${p['profit_usd']:.2f}</td>
                    </tr>"""
    
    html += """
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>"""

    os.makedirs('backtest', exist_ok=True)
    filename = f"backtest/backtest_report_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Backtest completed! Report saved to: {filename}")
    
    return filename

def optimize_strategy(df, trigger_signals, confirmation_signals, symbol, tf,
                     backtest_days, initial_balance,
                     position_size_mode, fixed_lot_size,
                     risk_percent, risk_based_on,
                     optimization_params):
    
   
    use_risk_free_options = optimization_params.get('use_risk_free', [True, False])
    use_sl_options = optimization_params.get('use_sl', [True, False])
    use_tp_options = optimization_params.get('use_tp', [True, False])
    close_opposite_options = optimization_params.get('close_opposite_position', [True, False])
    
    risk_free_params = optimization_params.get('risk_free_distance_pips', {})
    risk_free_values = list(range(
        risk_free_params.get('start', 10),
        risk_free_params.get('end', 50) + 1,
        risk_free_params.get('step', 10)
    )) if risk_free_params else [20]
    
    sl_params = optimization_params.get('sl_pips', {})
    sl_values = list(range(
        sl_params.get('start', 20),
        sl_params.get('end', 100) + 1,
        sl_params.get('step', 20)
    )) if sl_params else [50]
    
    tp_params = optimization_params.get('tp_pips', {})
    tp_values = list(range(
        tp_params.get('start', 30),
        tp_params.get('end', 150) + 1,
        tp_params.get('step', 30)
    )) if tp_params else [100]
    
    param_combinations = []
    for use_rf in use_risk_free_options:
        for rf_dist in risk_free_values if use_rf else [0]:
            for use_sl_val in use_sl_options:
                for sl_val in sl_values if use_sl_val else [0]:
                    for use_tp_val in use_tp_options:
                        for tp_val in tp_values if use_tp_val else [0]:
                            for close_opp in close_opposite_options:
                                param_combinations.append({
                                    'use_risk_free': use_rf,
                                    'risk_free_distance_pips': rf_dist,
                                    'use_sl': use_sl_val,
                                    'sl_pips': sl_val,
                                    'use_tp': use_tp_val,
                                    'tp_pips': tp_val,
                                    'close_opposite_position': close_opp
                                })
    
    print(f"Starting optimization with {len(param_combinations)} combinations...")
    
    results = []
    total = len(param_combinations)
    
    for idx, params in enumerate(param_combinations, 1):
        try:
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            
            result_data = run_backtest(
                df.copy(),
                trigger_signals.copy(),
                confirmation_signals.copy(),
                symbol, tf, backtest_days,
                params['use_risk_free'],
                params['risk_free_distance_pips'],
                params['use_sl'],
                params['sl_pips'],
                params['use_tp'],
                params['tp_pips'],
                params['close_opposite_position'],
                initial_balance,
                position_size_mode,
                fixed_lot_size,
                risk_percent,
                risk_based_on
            )
            
            sys.stdout = old_stdout
            
            if result_data:
                results.append({
                    'params': params,
                    'metrics': result_data,
                    'status': 'success'
                })
            else:
                results.append({
                    'params': params,
                    'status': 'no_trades'
                })
            
            if idx % 10 == 0 or idx == total:
                print(f"Progress: {idx}/{total}")
                
        except Exception as e:
            sys.stdout = old_stdout
            print(f"Error in combo {idx}: {str(e)}")
            results.append({
                'params': params,
                'error': str(e),
                'status': 'failed'
            })
    
    print("Optimization completed!")
    
    analyze_results(results, symbol, tf, backtest_days)
    
    return results

def run_backtest(df, trigger_signals, confirmation_signals, symbol, tf, 
                backtest_days, use_risk_free, risk_free_distance_pips,
                use_sl, sl_pips, use_tp, tp_pips, close_opposite_position,
                initial_balance, position_size_mode, fixed_lot_size,
                risk_percent, risk_based_on):
    
    try:
        import MetaTrader5 as mt5
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
    
    positions = []
    current_position = None
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown = 0
    
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
                    'exit_price': exit_price,
                    'exit_reason': 'Manual Close',
                    'profit_usd': profit_usd
                })
                positions.append(current_position)
                balance += profit_usd
                
                if balance > peak_balance:
                    peak_balance = balance
                current_drawdown = peak_balance - balance
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                
                current_position = None
        
        if current_position is None:
            if new_buy_signal:
                lot_size = calculate_position_size(balance, symbol, sl_pips if use_sl else 50)
                pip_value = get_pip_value(symbol, lot_size)
                
                current_position = {
                    'type': 'buy',
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
                    'entry_price': current_bar['close'],
                    'risk_free_activated': False,
                    'sl_price': current_bar['close'] + (sl_pips * pip) if use_sl else None,
                    'tp_price': current_bar['close'] - (tp_pips * pip) if use_tp else None,
                    'lot_size': lot_size,
                    'pip_value_usd': pip_value
                }
        else:
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
                    'exit_price': exit_price,
                    'exit_reason': exit_reason,
                    'profit_usd': profit_usd
                })
                positions.append(current_position)
                balance += profit_usd
                
                if balance > peak_balance:
                    peak_balance = balance
                current_drawdown = peak_balance - balance
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
                
                current_position = None
    
    if len(positions) == 0:
        return None
    
    total_trades = len(positions)
    winning_trades = [p for p in positions if p['profit_usd'] > 0]
    losing_trades = [p for p in positions if p['profit_usd'] < 0]
    
    total_profit_usd = sum(p['profit_usd'] for p in positions)
    final_balance = initial_balance + total_profit_usd
    
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    gross_profit_usd = sum(p['profit_usd'] for p in winning_trades) if winning_trades else 0
    gross_loss_usd = abs(sum(p['profit_usd'] for p in losing_trades)) if losing_trades else 0
    
    roi = ((final_balance - initial_balance) / initial_balance * 100) if initial_balance > 0 else 0
    profit_factor_usd = (gross_profit_usd / gross_loss_usd) if gross_loss_usd > 0 else float('inf')
    max_drawdown_percent = (max_drawdown / peak_balance * 100) if peak_balance > 0 else 0
    
    return {
        'roi': roi,
        'winrate': win_rate,
        'total_trades': total_trades,
        'profit_factor': profit_factor_usd,
        'max_drawdown': max_drawdown_percent,
        'final_balance': final_balance,
        'total_profit': total_profit_usd
    }

def analyze_results(results, symbol, tf, backtest_days):
    
    data = []
    for i, res in enumerate(results, 1):
        if res['status'] != 'success':
            continue
            
        params = res['params']
        metrics = res['metrics']
        
        data.append({
            'id': i,
            'use_risk_free': params['use_risk_free'],
            'risk_free_pips': params['risk_free_distance_pips'],
            'use_sl': params['use_sl'],
            'sl_pips': params['sl_pips'],
            'use_tp': params['use_tp'],
            'tp_pips': params['tp_pips'],
            'close_opposite': params['close_opposite_position'],
            'roi': metrics['roi'],
            'winrate': metrics['winrate'],
            'total_trades': metrics['total_trades'],
            'profit_factor': metrics['profit_factor'],
            'max_drawdown': metrics['max_drawdown']
        })
    
    if len(data) == 0:
        print("No successful results found!")
        return None
    
    df_results = pd.DataFrame(data)
    
    top_roi = df_results.nlargest(5, 'roi')
    top_winrate = df_results.nlargest(5, 'winrate')
    
    common_ids = set(top_roi['id']).intersection(set(top_winrate['id']))
    best_setups = df_results[df_results['id'].isin(common_ids)]
    
    html = generate_optimization_report(df_results, top_roi, top_winrate, best_setups, symbol, tf, backtest_days)
    
    os.makedirs('optimize', exist_ok=True)
    filename = f"optimize/optimize_report_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Report saved: {filename}")
    return filename

def generate_optimization_report(df_all, top_roi, top_winrate, best_setups, symbol, tf, days):
    html = f"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Optimization Report - {symbol}</title>
<style>
* {{margin:0;padding:0;box-sizing:border-box}}
body {{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;background:linear-gradient(135deg,#0f2027 0%,#203a43 50%,#2c5364 100%);color:#fff;padding:20px}}
.container {{max-width:1800px;margin:0 auto;background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border-radius:20px;padding:30px;box-shadow:0 8px 32px rgba(0,0,0,0.4)}}
h1 {{text-align:center;margin-bottom:10px;font-size:3em;background:linear-gradient(45deg,#00f2fe,#4facfe);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.subtitle {{text-align:center;color:#aaa;margin-bottom:40px;font-size:1.2em}}
h2 {{margin:40px 0 20px 0;color:#00f2fe;font-size:2em;border-bottom:2px solid rgba(0,242,254,0.3);padding-bottom:10px}}
.section {{background:rgba(255,255,255,0.08);border-radius:15px;padding:25px;margin-bottom:30px;box-shadow:0 4px 15px rgba(0,0,0,0.3)}}
table {{width:100%;border-collapse:collapse;margin-top:20px;font-size:0.9em}}
th {{background:rgba(0,242,254,0.2);padding:12px 8px;text-align:center;font-weight:600;border-bottom:2px solid rgba(0,242,254,0.5);white-space:nowrap}}
td {{padding:10px 8px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.1)}}
tr:hover {{background:rgba(255,255,255,0.05)}}
.badge {{padding:5px 10px;border-radius:20px;font-size:0.8em;font-weight:bold;display:inline-block;white-space:nowrap}}
.badge-yes {{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#000}}
.badge-no {{background:linear-gradient(135deg,#ff4757,#cc3644);color:#fff}}
.stats-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:20px;margin-bottom:30px}}
.stat-card {{background:linear-gradient(135deg,rgba(0,242,254,0.15),rgba(79,172,254,0.1));border-radius:15px;padding:20px;border:1px solid rgba(0,242,254,0.3);transition:transform 0.3s}}
.stat-card:hover {{transform:translateY(-5px);box-shadow:0 8px 25px rgba(0,242,254,0.3)}}
.stat-label {{font-size:0.95em;color:#aaa;margin-bottom:10px}}
.stat-value {{font-size:2.5em;font-weight:bold;color:#00f2fe}}
.positive {{color:#00ff88!important}}
.negative {{color:#ff4757!important}}
.crown {{font-size:1.3em;margin-right:5px}}
</style>
</head>
<body>
<div class="container">
<h1>Strategy Optimization Report</h1>
<div class="subtitle">{symbol} | {tf} | {days} days | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
<div class="stats-grid">
<div class="stat-card"><div class="stat-label">Total Combinations</div><div class="stat-value">{len(df_all)}</div></div>
<div class="stat-card"><div class="stat-label">Best ROI</div><div class="stat-value positive">{top_roi.iloc[0]['roi']:.2f}%</div></div>
<div class="stat-card"><div class="stat-label">Best Win Rate</div><div class="stat-value positive">{top_winrate.iloc[0]['winrate']:.2f}%</div></div>
<div class="stat-card"><div class="stat-label">Common Best Setups</div><div class="stat-value" style="color:#ffd700">{len(best_setups)}</div></div>
</div>
<div class="section">
<h2>Top 5 Setups by ROI</h2>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>Rank</th>
<th>Risk Free</th>
<th>RF Pips</th>
<th>Stop Loss</th>
<th>SL Pips</th>
<th>Take Profit</th>
<th>TP Pips</th>
<th>Close Opposite</th>
<th>ROI</th>
<th>Win Rate</th>
<th>Trades</th>
<th>PF</th>
</tr>
</thead>
<tbody>"""
    
    for rank, (idx, row) in enumerate(top_roi.iterrows(), 1):
        html += f"""
<tr>
<td><span class="crown">{'👑' if rank==1 else '🏅'}</span>{rank}</td>
<td><span class="badge badge-{'yes' if row['use_risk_free'] else 'no'}">{'Yes' if row['use_risk_free'] else 'No'}</span></td>
<td>{row['risk_free_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['use_sl'] else 'no'}">{'Yes' if row['use_sl'] else 'No'}</span></td>
<td>{row['sl_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['use_tp'] else 'no'}">{'Yes' if row['use_tp'] else 'No'}</span></td>
<td>{row['tp_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['close_opposite'] else 'no'}">{'Yes' if row['close_opposite'] else 'No'}</span></td>
<td class="positive" style="font-weight:bold">{row['roi']:.2f}%</td>
<td>{row['winrate']:.2f}%</td>
<td>{row['total_trades']:.0f}</td>
<td>{row['profit_factor']:.2f}</td>
</tr>"""
    
    html += """
</tbody>
</table>
</div>
</div>
<div class="section">
<h2>Top 5 Setups by Win Rate</h2>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
<th>Rank</th>
<th>Risk Free</th>
<th>RF Pips</th>
<th>Stop Loss</th>
<th>SL Pips</th>
<th>Take Profit</th>
<th>TP Pips</th>
<th>Close Opposite</th>
<th>Win Rate</th>
<th>ROI</th>
<th>Trades</th>
<th>PF</th>
</tr>
</thead>
<tbody>"""
    
    for rank, (idx, row) in enumerate(top_winrate.iterrows(), 1):
        html += f"""
<tr>
<td><span class="crown">{'👑' if rank==1 else '🏅'}</span>{rank}</td>
<td><span class="badge badge-{'yes' if row['use_risk_free'] else 'no'}">{'Yes' if row['use_risk_free'] else 'No'}</span></td>
<td>{row['risk_free_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['use_sl'] else 'no'}">{'Yes' if row['use_sl'] else 'No'}</span></td>
<td>{row['sl_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['use_tp'] else 'no'}">{'Yes' if row['use_tp'] else 'No'}</span></td>
<td>{row['tp_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['close_opposite'] else 'no'}">{'Yes' if row['close_opposite'] else 'No'}</span></td>
<td class="positive" style="font-weight:bold">{row['winrate']:.2f}%</td>
<td>{row['roi']:.2f}%</td>
<td>{row['total_trades']:.0f}</td>
<td>{row['profit_factor']:.2f}</td>
</tr>"""
    
    html += """
</tbody>
</table>
</div>
</div>"""
    
    if len(best_setups) > 0:
        html += """
<div class="section">
<h2>Common Best Setups</h2>
<p style="color:#ffd700;margin-bottom:20px;font-size:1.1em">These setups have both high ROI and excellent Win Rate</p>
<div style="overflow-x:auto">
<table>
<thead>
<tr style="background:rgba(255,215,0,0.2)">
<th>Risk Free</th>
<th>RF Pips</th>
<th>Stop Loss</th>
<th>SL Pips</th>
<th>Take Profit</th>
<th>TP Pips</th>
<th>Close Opposite</th>
<th>ROI</th>
<th>Win Rate</th>
<th>Trades</th>
<th>PF</th>
<th>Max DD</th>
</tr>
</thead>
<tbody>"""
        
        for idx, row in best_setups.iterrows():
            html += f"""
<tr style="background:rgba(255,215,0,0.1)">
<td><span class="badge badge-{'yes' if row['use_risk_free'] else 'no'}">{'Yes' if row['use_risk_free'] else 'No'}</span></td>
<td>{row['risk_free_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['use_sl'] else 'no'}">{'Yes' if row['use_sl'] else 'No'}</span></td>
<td>{row['sl_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['use_tp'] else 'no'}">{'Yes' if row['use_tp'] else 'No'}</span></td>
<td>{row['tp_pips']:.0f}</td>
<td><span class="badge badge-{'yes' if row['close_opposite'] else 'no'}">{'Yes' if row['close_opposite'] else 'No'}</span></td>
<td class="positive" style="font-weight:bold">{row['roi']:.2f}%</td>
<td class="positive" style="font-weight:bold">{row['winrate']:.2f}%</td>
<td>{row['total_trades']:.0f}</td>
<td>{row['profit_factor']:.2f}</td>
<td class="negative">{row['max_drawdown']:.2f}%</td>
</tr>"""
        
        html += """
</tbody>
</table>
</div>
</div>"""
    else:
        html += """
<div class="section">
<h2>Common Best Setups</h2>
<p style="color:#ff4757;font-size:1.2em;text-align:center;padding:30px">No common setups found</p>
</div>"""
    
    html += """
</div>
</body>
</html>"""
    return html

def backtest_candle(symbol: str, timeframe: str = "1m", limit: int = 100, heikin_ashi: bool = False, data=None):
    
    tf_map = {
        '1m': mt5.TIMEFRAME_M1, '3m': mt5.TIMEFRAME_M3, '5m': mt5.TIMEFRAME_M5, 
        '15m': mt5.TIMEFRAME_M15, '30m': mt5.TIMEFRAME_M30, '1h': mt5.TIMEFRAME_H1,
        '4h': mt5.TIMEFRAME_H4, '1d': mt5.TIMEFRAME_D1, '1w': mt5.TIMEFRAME_W1
    }
    
    if timeframe not in tf_map:
        raise ValueError(f"Timeframe {timeframe} not supported. Use: {list(tf_map.keys())}")
    
    mt5_tf = tf_map[timeframe]
    
    if data is not None:
        # Phase-1 fix (coherent pairing): compute from caller-provided bars
        # instead of self-fetching the latest N bars from MT5.
        # `data` must be in MT5-raw format (epoch 'time' + 'tick_volume', ...).
        df = pd.DataFrame(data)
    else:
        mt5.initialize()
    
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, limit)
    
        if rates is None or len(rates) == 0:
            print(f"Warning: No data returned from MT5 for {symbol} on {timeframe}")
            return pd.DataFrame(columns=['time', 'open', 'high', 'low', 'close', 'tick_volume'])
    
        df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.rename(columns={'tick_volume': 'volume'}, inplace=True)
    
    result = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
    
    if heikin_ashi:
        ha_result = result.copy()
        
        ha_result['close'] = (result['open'] + result['high'] + result['low'] + result['close']) / 4
        
        ha_result['open'] = 0.0
        ha_result.iloc[0, ha_result.columns.get_loc('open')] = result['open'].iloc[0]
        
        for i in range(1, len(result)):
            ha_result.iloc[i, ha_result.columns.get_loc('open')] = (
                ha_result['open'].iloc[i-1] + ha_result['close'].iloc[i-1]
            ) / 2
        
        ha_result['high'] = ha_result[['open', 'close']].max(axis=1).combine(result['high'], max)
        ha_result['low'] = ha_result[['open', 'close']].min(axis=1).combine(result['low'], min)
        
        return ha_result
    
    return result

def extract_number(string):

    match = re.search(r'\d+', string)
    if match:
        return float(match.group())
    else:
        raise ValueError("no number found in string")






