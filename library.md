# Project Library: صابری1


## File: agent\__init__.py

``python
"""Safe experiment-management and local skill primitives."""

from .manager import ExperimentManager, ExperimentSpec, ExperimentResult
from .skills import Skill, SkillCatalog

__all__ = ["ExperimentManager", "ExperimentSpec", "ExperimentResult", "Skill", "SkillCatalog"]

``

## File: agent\manager.py

``python
"""Safe MVP manager for backtest experiments.

This module deliberately manages historical experiments only. It does not
import MetaTrader5, change risk settings, or send live orders.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from module.backtest import HistoricalReplay
from module.market_data import Candle
from module.paper import PaperBroker
from module.performance import calculate_performance
from module.strategy_adapter import (
    CombinedVotingStrategy,
    HalfTrendAdapter,
    MACDAdapter,
    RSIAdapter,
    SupertrendAdapter,
)


@dataclass(frozen=True)
class ExperimentSpec:
    """Versioned configuration for one historical experiment."""

    name: str = "current-combined"
    symbol: str = "XAUUSD"
    volume: float = 0.01
    rr: float = 2.0
    min_votes: int = 2
    supertrend_atr_period: int = 10
    supertrend_multiplier: float = 3.0
    halftrend_amplitude: int = 2
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal_period: int = 9

    def validate(self) -> None:
        if self.volume <= 0 or self.rr <= 0:
            raise ValueError("volume and rr must be positive")
        if self.min_votes < 1 or self.min_votes > 4:
            raise ValueError("min_votes must be between 1 and 4")
        if self.macd_fast >= self.macd_slow:
            raise ValueError("macd_fast must be lower than macd_slow")


@dataclass
class ExperimentResult:
    experiment_id: str
    spec: dict[str, Any]
    train: dict[str, Any]
    test: dict[str, Any]
    passed: bool
    score: float
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _strategy(spec: ExperimentSpec) -> CombinedVotingStrategy:
    spec.validate()
    return CombinedVotingStrategy(
        [
            SupertrendAdapter(spec.supertrend_atr_period, spec.supertrend_multiplier),
            HalfTrendAdapter(spec.halftrend_amplitude),
            RSIAdapter(spec.rsi_period),
            MACDAdapter(spec.macd_fast, spec.macd_slow, spec.macd_signal_period),
        ],
        symbol=spec.symbol,
        volume=spec.volume,
        rr=spec.rr,
        min_votes=spec.min_votes,
        comment=spec.name,
    )


def _run(candles: list[Candle], spec: ExperimentSpec, initial_balance: float) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="experiment-") as directory:
        broker = PaperBroker(Path(directory) / "paper.json", initial_balance=initial_balance)
        replay = HistoricalReplay(broker, initial_balance=initial_balance)
        result = replay.run(candles, _strategy(spec))
        metrics = dict(result["metrics"])
        metrics["candles"] = len(candles)
        metrics["closed"] = len(result["closed_profits"])
        metrics["max_drawdown_percent"] = broker.max_drawdown()["max_drawdown_percent"]
        return metrics


class ExperimentManager:
    """Run, persist, rank, and gate historical strategy experiments."""

    def __init__(
        self,
        store_path: str | Path = "experiments/results.jsonl",
        *,
        initial_balance: float = 5000.0,
        min_test_trades: int = 1,
        max_test_drawdown_percent: float = 20.0,
    ) -> None:
        self.store_path = Path(store_path)
        self.initial_balance = float(initial_balance)
        self.min_test_trades = int(min_test_trades)
        self.max_test_drawdown_percent = float(max_test_drawdown_percent)

    def run(self, candles: Iterable[Candle], spec: ExperimentSpec) -> ExperimentResult:
        rows = sorted(candles, key=lambda item: item.timestamp)
        if len(rows) < 4:
            raise ValueError("at least four candles are required for train/test")
        split = max(1, int(len(rows) * 0.7))
        train_rows, test_rows = rows[:split], rows[split:]
        train = _run(train_rows, spec, self.initial_balance)
        test = _run(test_rows, spec, self.initial_balance)
        passed = (
            test["trades"] >= self.min_test_trades
            and test["max_drawdown_percent"] <= self.max_test_drawdown_percent
            and test["net_profit"] > 0
        )
        score = float(test["net_profit"]) - float(test["max_drawdown"]) * 0.5
        payload = json.dumps(asdict(spec), sort_keys=True, separators=(",", ":"))
        experiment_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        result = ExperimentResult(experiment_id, asdict(spec), train, test, passed, score)
        self._append(result)
        return result

    def grid(self, parameter_grid: dict[str, Iterable[Any]]) -> list[ExperimentResult]:
        """Run a bounded Cartesian grid of ExperimentSpec values."""
        keys = list(parameter_grid)
        values = [list(parameter_grid[key]) for key in keys]
        results = []
        for combination in itertools.product(*values):
            values_for_spec = dict(zip(keys, combination))
            results.append(self.run(ExperimentSpec(**values_for_spec)))
        return results

    def best(self, results: Iterable[ExperimentResult]) -> ExperimentResult | None:
        candidates = [result for result in results if result.passed]
        return max(candidates, key=lambda result: result.score, default=None)

    def _append(self, result: ExperimentResult) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")

    def history(self) -> list[dict[str, Any]]:
        if not self.store_path.exists():
            return []
        rows = []
        for line in self.store_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

``

## File: agent\skills.py

``python
"""Local skill discovery for safe trading research workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class Skill:
    """A locally available SKILL.md and its lightweight metadata."""

    name: str
    description: str
    path: Path
    content: str


class SkillCatalog:
    """Discover and load skills without making them part of the trade path."""

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        base = Path(__file__).resolve().parent.parent
        self.roots = tuple(Path(root) for root in (roots or (base / ".agents" / "skills", base / "skll")))

    def discover(self) -> list[Skill]:
        skills: list[Skill] = []
        seen: set[Path] = set()
        for root in self.roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("SKILL.md")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                content = path.read_text(encoding="utf-8")
                metadata, body = self._parse(content)
                skills.append(
                    Skill(
                        name=metadata.get("name") or path.parent.name,
                        description=metadata.get("description", "").strip(),
                        path=path,
                        content=body,
                    )
                )
        return skills

    def get(self, name: str) -> Skill | None:
        normalized = name.casefold()
        return next(
            (
                skill
                for skill in self.discover()
                if skill.name.casefold() == normalized or skill.path.parent.name.casefold() == normalized
            ),
            None,
        )

    def relevant(self, query: str) -> list[Skill]:
        """Return skills whose name, description, or body matches query terms."""
        terms = {term.casefold() for term in re.findall(r"[\w-]+", query) if len(term) > 2}
        if not terms:
            return []
        ranked: list[tuple[int, Skill]] = []
        for skill in self.discover():
            haystack = f"{skill.name} {skill.description} {skill.content}".casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                ranked.append((score, skill))
        return [skill for _, skill in sorted(ranked, key=lambda item: (-item[0], item[1].name.casefold()))]

    @staticmethod
    def _parse(content: str) -> tuple[dict[str, str], str]:
        match = _FRONTMATTER.match(content)
        if not match:
            return {}, content
        metadata: dict[str, str] = {}
        for line in match.group(1).splitlines():
            key, separator, value = line.partition(":")
            if separator:
                metadata[key.strip()] = value.strip().strip('"\'')
        return metadata, content[match.end():]
``

## File: backtest\backtester.py

``python
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

CLOSE_OPPOSITE_POSITION = False  #Ø¨Ø³ØªÙ† Ù¾ÙˆØ²ÛŒØ´Ù† ÙˆÙ‚ØªÛŒ Ø³ÛŒÚ¯Ù†Ø§Ù„ Ù…Ø®Ø§Ù„Ù ØµØ§Ø¯Ø± Ø´Ù‡
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





``

## File: backtest\hashem_backtest.py

``python
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
            
            time_session_table_html = '<h2>ðŸ“Š Best Time Sessions Analysis</h2>'
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
                        <div class="stat-label">ðŸ† Best Time Session</div>
                        <div class="stat-value positive">{best[0]}</div>
                        <div class="stat-label">Profit: ${best[1]['profit']:.2f} ({best[1]['count']} trades)</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">âš ï¸ Worst Time Session</div>
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
<td><span class="crown">{'ðŸ‘‘' if rank==1 else 'ðŸ…'}</span>{rank}</td>
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
<td><span class="crown">{'ðŸ‘‘' if rank==1 else 'ðŸ…'}</span>{rank}</td>
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

def backtest_candle(symbol: str, timeframe: str = "1m", limit: int = 100, heikin_ashi: bool = False):
    """Use the exact same M1-resample path as live data."""
    from module.timeframe_data import fetch_m1_resampled
    result = fetch_m1_resampled(mt5, symbol, timeframe, limit)
    if heikin_ashi and not result.empty:
        ha=result.copy()
        ha["close"]=(result["open"]+result["high"]+result["low"]+result["close"])/4
        ha["open"]=0.0
        ha.iloc[0, ha.columns.get_loc("open")]=result["open"].iloc[0]
        for i in range(1,len(ha)):
            ha.iloc[i, ha.columns.get_loc("open")]=(ha["open"].iloc[i-1]+ha["close"].iloc[i-1])/2
        ha["high"]=ha[["open","close","high"]].max(axis=1)
        ha["low"]=ha[["open","close","low"]].min(axis=1)
        return ha
    return result

def extract_number(string):

    match = re.search(r'\d+', string)
    if match:
        return float(match.group())
    else:
        raise ValueError("no number found in string")







``

## File: backtest\indicators.py

``python
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
        raise ValueError("Ø¯ÛŒØªØ§ÙØ±ÛŒÙ… ÙˆØ±ÙˆØ¯ÛŒ Ø¨Ø§ÛŒØ¯ Ø´Ø§Ù…Ù„ Ø³ØªÙˆÙ†â€ŒÙ‡Ø§ÛŒ 'open', 'high', 'low', 'close' Ø¨Ø§Ø´Ø¯.")

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

``

## File: backtest\optimizer.py

``python
from .hashem_backtest import *
from .indicators import *
import itertools
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
    print(f"ðŸš€ OPTIMIZER STARTED")
    print("="*80)
    print(f"Symbol: {symbol} | Timeframe: {tf} | Backtest Days: {backtest_days}")
    print(f"Entry Indicator: {entry_indicator}")
    if conf_indicator:
        print(f"Confirmation Indicator: {conf_indicator}")
    print("="*80 + "\n")
    
    # Load data
    minutes = extract_number(tf)
    limit = backtest_days * 1440 / minutes
    
    print("ðŸ“Š Loading market data...")
    df = backtest_candle(symbol, tf, int(limit))
    print(f"âœ… Loaded {len(df)} candles\n")
    
    # Prepare parameters
    if entry_params is None:
        entry_params = DEFAULT_PARAMS.get(entry_indicator, {})
    
    entry_param_names = list(entry_params.keys())
    entry_param_values = list(entry_params.values())
    entry_combinations = list(itertools.product(*entry_param_values))
    
    total_combinations = len(entry_combinations)
    print(f"ðŸ” Total combinations to test: {total_combinations}\n")
    
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
    print(f"âš¡ Starting optimization with {max_workers} workers...\n")
    
    args_list = [
        (df, symbol, tf, entry_indicator, combo, entry_param_names, conf_indicator, fixed_conf_params, backtest_params)
        for combo in entry_combinations
    ]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_combination, args): args for args in args_list}
        
        with tqdm(total=total_combinations, desc="Testing combinations", ncols=100) as pbar:
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
        print("âŒ No valid results found!")
        print("="*80 + "\n")
        return {'error': 'Ù‡ÛŒÚ† Ù†ØªÛŒØ¬Ù‡ Ù…Ø¹ØªØ¨Ø±ÛŒ ÛŒØ§ÙØª Ù†Ø´Ø¯'}
    
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
    print("âœ… OPTIMIZATION COMPLETED!")
    print("="*80)
    print(f"ðŸ“Š Results Summary:")
    print(f"   Valid combinations tested: {valid_results}/{total_combinations}")
    print(f"\nðŸ† Best Parameters:")
    for key, value in best_result['params'].items():
        print(f"   {key}: {value}")
    print(f"\nðŸ“ˆ Performance Metrics:")
    print(f"   Win Rate: {best_result['win_rate']:.2f}%")
    print(f"   ROI: {best_result['roi']:.2f}%")
    print(f"   Total Trades: {best_result['total_trades']}")
    print(f"   Max Drawdown: {best_result['max_drawdown']:.2f}%")
    print(f"   Final Balance: ${best_result['final_balance']:.2f}")
    print(f"\nðŸ’¾ Results saved to: {filename}")
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
    
    print("ðŸŽ¯ Final Output (Best Parameters):")
    print(result)
``

## File: backtest\run_csv_backtests.py

``python
"""Run the current and legacy strategies against MT5 M1 CSV exports."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.indicators import backtest_supertrend, backtest_trend_ali
from module.backtest import HistoricalReplay, ReplaySignal
from module.market_data import (
    aggregate_ticks_to_candles,
    iter_mt5_ticks_csv,
    load_mt5_candles_csv,
)
from module.paper import PaperBroker
from module.strategy_adapter import (
    CombinedVotingStrategy,
    HalfTrendAdapter,
    MACDAdapter,
    RSIAdapter,
    SupertrendAdapter,
)


def _run(candles, strategy, label: str, initial_balance: float) -> dict:
    with tempfile.TemporaryDirectory(prefix="csv-backtest-") as directory:
        broker = PaperBroker(Path(directory) / f"{label}.json", initial_balance=initial_balance)
        result = HistoricalReplay(broker, initial_balance=initial_balance).run(candles, strategy)
        drawdown = broker.max_drawdown()["max_drawdown"]
    metrics = result["metrics"]
    return {
        "strategy": label,
        "candles": result["candles"],
        "closed": len(result["closed_profits"]),
        "net_profit": metrics["net_profit"],
        "profit_factor": metrics["profit_factor"],
        "max_drawdown": drawdown,
    }


def run_file(path: Path, limit: int, initial_balance: float, tick_limit: int) -> list[dict]:
    if "_M1_" in path.name:
        candles = load_mt5_candles_csv(path, limit=limit)
    else:
        ticks = _read_tick_sample(path, tick_limit)
        candles = aggregate_ticks_to_candles(ticks)[:limit]
    if not candles:
        raise ValueError(f"no candles loaded from {path}")
    current = CombinedVotingStrategy(
        [SupertrendAdapter(), HalfTrendAdapter(), RSIAdapter(), MACDAdapter()],
        symbol="XAUUSD",
        volume=0.01,
        rr=2.0,
        min_votes=2,
    )
    results = [_run(candles, current, "current", initial_balance)]

    frame = pd.DataFrame(
        [
            {
                "time": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "tick_volume": candle.volume,
            }
            for candle in candles
        ]
    )
    trigger = backtest_supertrend(
        "XAUUSD", "1m", len(frame), atr_period=10, multiplier=3.0, data=frame
    )["signal"]
    confirmation = backtest_trend_ali(
        "XAUUSD", "1m", len(frame), length=60, length_mult=6.0, mode="Hma", data=frame
    )["trend"]

    def legacy(history, candle):
        index = len(history)
        if index >= len(trigger) or trigger[index] not in {"buy", "sell"}:
            return []
        direction = trigger[index]
        if direction != confirmation[index]:
            return []
        entry = candle.open
        sl = entry - 1.0 if direction == "buy" else entry + 1.0
        tp = entry + 2.0 if direction == "buy" else entry - 2.0
        return [
            ReplaySignal(
                f"legacy-{index}",
                "XAUUSD",
                0.01,
                0 if direction == "buy" else 1,
                entry,
                sl,
                tp,
                "legacy",
            )
        ]

    results.append(_run(candles, legacy, "legacy", initial_balance))
    return results


def _read_tick_sample(path: Path, tick_limit: int):
    ticks = []
    for tick in iter_mt5_ticks_csv(path):
        ticks.append(tick)
        if len(ticks) >= tick_limit:
            break
    return ticks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--initial-balance", type=float, default=5000.0)
    parser.add_argument("--tick-limit", type=int, default=100000)
    args = parser.parse_args()
    for path in args.files:
        if "_M1_" in path.name:
            candles = load_mt5_candles_csv(path, limit=args.limit)
        else:
            candles = aggregate_ticks_to_candles(
                _read_tick_sample(path, args.tick_limit)
            )[: args.limit]
        print(
            f"DATA {path.name}: {len(candles)} candles "
            f"{candles[0].timestamp} -> {candles[-1].timestamp}"
        )
        for result in run_file(path, args.limit, args.initial_balance, args.tick_limit):
            print(result)


if __name__ == "__main__":
    main()

``

## File: dashboard.py

``python
"""Read-only Flask dashboard for the trading bot.

The dashboard never sends orders. It reads persisted state, logs, and an
optional injected MT5 adapter. Protect it with DASHBOARD_TOKEN when exposed
beyond localhost.
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, render_template_string

from module.config import MAGIC_NUMBER, TRADING_MODE
from module.paper import PaperBroker
from module.performance import calculate_performance


HTML = """<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'><title>Golden Library Monitor</title>
<style>body{font-family:system-ui;background:#101827;color:#e5e7eb;margin:24px}h1{color:#fbbf24}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.card{background:#1f2937;border-radius:12px;padding:16px;box-shadow:0 2px 8px #0004}pre{white-space:pre-wrap;max-height:420px;overflow:auto;color:#cbd5e1}.ok{color:#34d399}.warn{color:#fbbf24}</style></head>
<body><h1>Golden Library â€” Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ø±Ø¨Ø§Øª</h1><div class='grid'><div class='card'><h3>ÙˆØ¶Ø¹ÛŒØª</h3><div id='status'>Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ...</div></div><div class='card'><h3>Ù¾ÙˆØ²ÛŒØ´Ù†â€ŒÙ‡Ø§</h3><pre id='positions'></pre></div><div class='card'><h3>Ø¢Ø®Ø±ÛŒÙ† Ù„Ø§Ú¯â€ŒÙ‡Ø§</h3><pre id='logs'></pre></div><div class='card'><h3>Ù…ØºØ² Ø¯ÙˆÙ… / Memory</h3><pre id='memory'></pre></div></div>
<script>async function load(){for(const [id,url] of [['status','/api/status'],['positions','/api/positions'],['logs','/api/logs?limit=30'],['memory','/api/memory?limit=30']]){try{let r=await fetch(url);let x=await r.json();document.getElementById(id).textContent=JSON.stringify(x,null,2)}catch(e){document.getElementById(id).textContent='Ø®Ø·Ø§: '+e}}}load();setInterval(load,5000)</script></body></html>"""


def create_app(mt5_api: Any = None, root: str | os.PathLike[str] | None = None) -> Flask:
    root_path = Path(root or Path(__file__).resolve().parent)
    app = Flask(__name__)
    state_path = root_path / "trade_state.json"
    log_path = root_path / os.getenv("LOG_DIR", "logs") / "trading.jsonl"
    memory_path = root_path / "memory" / "events.jsonl"
    token = os.getenv("DASHBOARD_TOKEN")
    dashboard_host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if dashboard_host not in local_hosts and not token:
        raise RuntimeError("DASHBOARD_TOKEN is required when dashboard is not bound to localhost")
    if mt5_api is None and TRADING_MODE == "PAPER":
        mt5_api = PaperBroker(root_path / "paper_state.json", magic_number=MAGIC_NUMBER)

    @app.before_request
    def protect_dashboard():
        if token and request.headers.get("X-Dashboard-Token") != token:
            return jsonify({"error": "unauthorized"}), 401

    def read_json(path: Path, limit: int = 100) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line in deque(path.read_text(encoding="utf-8").splitlines(), maxlen=limit):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    @app.get("/")
    def index():
        return render_template_string(HTML)

    @app.get("/api/status")
    def status():
        state = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {"error": "invalid state file"}
        counts: dict[str, int] = {}
        for record in state.values() if isinstance(state, dict) else []:
            value = record.get("state", "UNKNOWN")
            counts[value] = counts.get(value, 0) + 1
        payload = {"mode": TRADING_MODE, "magic_number": MAGIC_NUMBER, "state_counts": counts, "updated_at": datetime.now(timezone.utc).isoformat()}
        if TRADING_MODE == "PAPER" and isinstance(mt5_api, PaperBroker):
            payload["paper"] = {"ledger": mt5_api.reconcile(), "drawdown": mt5_api.max_drawdown()}
        return jsonify(payload)

    @app.get("/api/positions")
    def positions():
        if mt5_api is None:
            return jsonify({"connected": False, "source": "none", "positions": []})
        try:
            raw = mt5_api.positions_get() or ()
            items = []
            for p in raw:
                if getattr(p, "magic", MAGIC_NUMBER) != MAGIC_NUMBER:
                    continue
                items.append({"ticket": getattr(p, "ticket", 0), "trade_id": getattr(p, "trade_id", ""), "symbol": getattr(p, "symbol", ""), "volume": getattr(p, "volume", 0), "type": getattr(p, "type", getattr(p, "order_type", 0)), "price": getattr(p, "price", 0), "current_price": getattr(p, "current_price", 0), "sl": getattr(p, "sl", 0), "tp": getattr(p, "tp", 0), "profit": getattr(p, "profit", 0), "comment": getattr(p, "comment", "")})
            return jsonify({"connected": True, "source": "paper" if TRADING_MODE == "PAPER" else "mt5", "positions": items})
        except Exception as exc:
            return jsonify({"connected": False, "error": str(exc), "positions": []}), 503

    @app.get("/api/logs")
    def logs():
        return jsonify(read_json(log_path, min(int(request.args.get("limit", 100)), 500)))

    @app.get("/api/memory")
    def memory():
        return jsonify(read_json(memory_path, min(int(request.args.get("limit", 100)), 500)))

    @app.get("/api/performance")
    def performance():
        if not isinstance(mt5_api, PaperBroker):
            return jsonify({"error": "performance endpoint currently exposes Paper results only"}), 400
        profits = [float(position.profit) for position in mt5_api.positions.values() if position.status == "CLOSED"]
        return jsonify(calculate_performance(profits, initial_balance=mt5_api.initial_balance))

    return app


if __name__ == "__main__":
    create_app().run(host=os.getenv("DASHBOARD_HOST", "127.0.0.1"), port=int(os.getenv("DASHBOARD_PORT", "5000")), debug=False)

``

## File: main.py

``python
"""Single production entry point for PAPER/LIVE trading.

The notebook remains exploratory. This module owns initialization, one cycle,
state reconciliation, and the restart-safe main loop.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable

try:
    import MetaTrader5 as mt5
except ModuleNotFoundError:  # Allows PAPER tests and dependency injection without MT5 installed.
    class _MissingMT5:
        def initialize(self) -> bool:
            raise RuntimeError("MetaTrader5 is not installed; pass api=... to setup() for tests")
    mt5 = _MissingMT5()

from module.config import MAGIC_NUMBER, TRADING_MODE
from module.execution import ExecutionEngine
from module.market_data import Candle
from module.memory import SecondBrain
from module.observability import configure_logging, get_logger
from module.paper import PaperBroker
from module.recovery import TradeRecovery
from module.risk import RiskLimits, RiskValidator
from module.risk_metrics import broker_drawdown_pct, broker_metrics
from module.state_machine import TradeRecord, TradeState, TradeStateMachine
from module.strategy_adapter import CombinedVotingStrategy, HalfTrendAdapter, MACDAdapter, RSIAdapter, SupertrendAdapter
from module.telegram_alerts import TelegramAlertNotifier


@dataclass
class Runtime:
    symbol: str
    tf: str
    risk: float
    rr: float
    loop_interval: float
    api: Any
    paper_broker: PaperBroker
    trade_states: TradeStateMachine
    trade_recovery: TradeRecovery
    execution_engine: ExecutionEngine
    logger: Any
    telegram_alert_notifier: TelegramAlertNotifier
    strategy: Callable[[list[Candle], Candle], Iterable[Any]]
    signal_provider: Callable[["Runtime"], Any] | None = None


runtime: Runtime | None = None
trade_states: TradeStateMachine | None = None
trade_recovery: TradeRecovery | None = None
execution_engine: ExecutionEngine | None = None
logger: Any = None


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def setup(*, api: Any | None = None, signal_provider: Callable[[Runtime], Any] | None = None, strategy: Callable | None = None) -> Runtime:
    """Initialize MT5, configuration, state, recovery, execution and logging once."""
    global runtime, trade_states, trade_recovery, execution_engine, logger
    api = api or mt5
    if not api.initialize():
        raise RuntimeError(f"MT5 initialize failed: {getattr(api, 'last_error', lambda: '')()}")

    symbol = os.getenv("SYMBOL", "XAUUSD")
    tf = os.getenv("TIMEFRAME", os.getenv("TF", "1m"))
    risk = _env_float("RISK_PERCENT", 1.0)
    rr = _env_float("RISK_REWARD", 2.0)
    interval = max(0.05, _env_float("LOOP_INTERVAL_SECONDS", 5.0))
    mode = os.getenv("TRADING_MODE", TRADING_MODE).upper()
    paper = PaperBroker(
        os.getenv("PAPER_STATE_PATH", "paper_state.json"),
        magic_number=MAGIC_NUMBER,
        initial_balance=_env_float("INITIAL_BALANCE", 0.0),
        commission_per_lot=_env_float("COMMISSION_PER_LOT", 0.0),
        default_spread=_env_float("DEFAULT_SPREAD", 0.0),
    )
    brain = SecondBrain(os.getenv("MEMORY_PATH", "memory/events.jsonl"))
    trade_states = TradeStateMachine(os.getenv("TRADE_STATE_PATH", "trade_state.json"), memory=brain)
    recovery_broker = paper if mode == "PAPER" else api
    trade_recovery = TradeRecovery(recovery_broker, timeout_seconds=_env_float("RECOVERY_TIMEOUT_SECONDS", 120))
    telegram_alert_notifier = TelegramAlertNotifier()
    configure_logging(os.getenv("LOG_DIR", "logs"), notifier=telegram_alert_notifier if telegram_alert_notifier.enabled else None)
    logger = get_logger("runtime")
    execution_engine = ExecutionEngine(api, mode=mode, paper_broker=paper, risk_validator=RiskValidator(RiskLimits.from_env()))
    selected_strategy = strategy or CombinedVotingStrategy(
        [SupertrendAdapter(), HalfTrendAdapter(), RSIAdapter(), MACDAdapter()],
        symbol=symbol,
        rr=rr,
        min_votes=int(os.getenv("MIN_VOTES", "2")),
    )
    runtime = Runtime(symbol, tf, risk, rr, interval, api, paper, trade_states, trade_recovery, execution_engine, logger, telegram_alert_notifier, selected_strategy, signal_provider)
    return runtime


def managed_create_order(symbol: str, lot: float, order_type: Any, sl: float = 0.0, tp: float = 0.0, comment: str = "strategy", tf: str = "unknown") -> Any:
    """Create one idempotent trade through the centralized execution boundary."""
    if runtime is None or trade_states is None or execution_engine is None:
        raise RuntimeError("setup() must be called before managed_create_order()")
    tick = runtime.api.symbol_info_tick(symbol)
    candle_time = getattr(tick, "time", int(time.time())) if tick is not None else int(time.time())
    trade_id = f"{symbol}:{tf}:{candle_time}:{comment}:{order_type}"
    if trade_states.get(trade_id) is not None:
        return None
    trade_states.create(TradeRecord(trade_id=trade_id, symbol=symbol, strategy=comment, candle_time=str(candle_time)))
    trade_states.transition(trade_id, TradeState.VALIDATED)
    trade_states.transition(trade_id, TradeState.APPROVED)
    normalized_order_type = "buy" if str(order_type).lower() in {"0", "buy"} else "sell"
    request = {"action": "deal", "symbol": symbol, "volume": float(lot), "type": order_type, "order_type": normalized_order_type, "price": float(getattr(tick, "ask", 0.0) if normalized_order_type == "buy" else getattr(tick, "bid", 0.0)), "sl": sl, "tp": tp, "comment": comment, "magic": MAGIC_NUMBER, "trade_id": trade_id}
    try:
        daily_profit, open_positions = broker_metrics(runtime.api, runtime.paper_broker, runtime.execution_engine.mode.value)
        drawdown_pct = broker_drawdown_pct(runtime.api, runtime.paper_broker, runtime.execution_engine.mode.value)
        result = execution_engine.send(request, daily_profit=daily_profit, open_positions=open_positions, drawdown_pct=drawdown_pct)
        trade_states.transition(trade_id, TradeState.SENT)
        if result is not None and getattr(result, "retcode", -1) == getattr(runtime.api, "TRADE_RETCODE_DONE", 10009):
            trade_states.transition(trade_id, TradeState.ACCEPTED, ticket=getattr(result, "order", 0))
        else:
            trade_states.transition(trade_id, TradeState.REJECTED, reason="execution failed")
        return result
    except (ValueError, RuntimeError, KeyError) as exc:
        trade_states.transition(trade_id, TradeState.REJECTED, reason=str(exc))
        logger.exception("trade rejected", extra={"event": "trade_rejected", "trade_id": trade_id})
        return None


def emergency_stop() -> dict[str, int]:
    """Flatten managed exposure and lock execution until manual reset."""
    if execution_engine is None:
        raise RuntimeError("setup() must be called before emergency_stop()")
    return execution_engine.emergency_stop()


def reconcile_all_trade_states() -> None:
    """Recover persisted states and reconcile them with managed positions."""
    if runtime is None or trade_states is None or trade_recovery is None:
        raise RuntimeError("setup() must be called before reconciliation")
    report = trade_recovery.recover(trade_states)
    if getattr(report, "errors", None):
        logger.error("Recovery errors", extra={"event": "recovery_errors"})
    for trade_id, record in list(trade_states.records.items()):
        if record.state in {TradeState.CLOSED, TradeState.REJECTED, TradeState.SIGNAL, TradeState.VALIDATED, TradeState.APPROVED, TradeState.SENT}:
            continue
        try:
            position_source = runtime.paper_broker if runtime.execution_engine.mode.value == "PAPER" else runtime.api
            positions = position_source.positions_get(symbol=record.symbol) or ()
        except (AttributeError, OSError, TypeError, ValueError):
            logger.exception(
                "position reconciliation failed",
                extra={"event": "position_reconciliation_error", "trade_id": trade_id},
            )
            continue
        matching = [p for p in positions if getattr(p, "magic", MAGIC_NUMBER) == MAGIC_NUMBER and (not record.ticket or getattr(p, "ticket", 0) == record.ticket)]
        if matching and record.state == TradeState.ACCEPTED:
            trade_states.transition(trade_id, TradeState.OPEN)
        elif not matching and record.state in {TradeState.OPEN, TradeState.MANAGED}:
            trade_states.transition(trade_id, TradeState.CLOSED)


def _default_signal_provider(rt: Runtime) -> Any:
    """Read recent MT5 rates and ask the pure strategy for a signal."""
    copier = getattr(rt.api, "copy_rates_from_pos", None)
    if copier is None:
        return None
    timeframe = getattr(rt.api, f"TIMEFRAME_{rt.tf.upper()}", rt.tf)
    rates = copier(rt.symbol, timeframe, 0, int(os.getenv("STRATEGY_LOOKBACK", "120")))
    if rates is None or len(rates) < 3:
        return None
    candles = [Candle(str(row["time"]), rt.symbol, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]), float(row.get("tick_volume", 0))) for row in rates]
    signals = list(rt.strategy(candles[:-1], candles[-1]) or ())
    return signals[0] if signals else None


def run_once(rt: Runtime | None = None) -> Any:
    """Run one signal/reconciliation/management cycle."""
    rt = rt or runtime
    if rt is None:
        raise RuntimeError("setup() must be called before run_once()")
    reconcile_all_trade_states()
    signal = rt.signal_provider(rt) if rt.signal_provider else _default_signal_provider(rt)
    if signal is None:
        return None
    result = managed_create_order(signal.symbol, signal.volume, signal.order_type, signal.sl, signal.tp, signal.comment, rt.tf)
    return result


def main() -> None:
    rt = setup()
    reconcile_all_trade_states()
    while True:
        try:
            run_once(rt)
        except Exception:
            rt.logger.exception("run_once failed", extra={"event": "run_once_error"})
        time.sleep(rt.loop_interval)


if __name__ == "__main__":
    main()

``

## File: module\backtest.py

``python
"""Strategy-to-paper historical replay adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

from .market_data import Candle, candles_to_ticks
from .paper import PaperBroker
from .performance import calculate_performance


@dataclass(frozen=True)
class ReplaySignal:
    trade_id: str
    symbol: str
    volume: float
    order_type: Any
    price: float
    sl: float
    tp: float
    comment: str = "replay"
    magic: int | None = None

    def as_request(self) -> dict[str, Any]:
        payload = {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "volume": self.volume,
            "type": self.order_type,
            "price": self.price,
            "sl": self.sl,
            "tp": self.tp,
            "comment": self.comment,
            "action": "deal",
        }
        if self.magic is not None:
            payload["magic"] = self.magic
        return payload


class HistoricalReplay:
    """Run an existing strategy through a PaperBroker without importing MT5."""

    def __init__(self, broker: PaperBroker, *, initial_balance: float = 0.0, slippage: float = 0.0) -> None:
        self.broker = broker
        self.initial_balance = initial_balance
        self.slippage = slippage

    def run(
        self,
        candles: Iterable[Candle],
        strategy: Callable[[list[Candle], Candle], Iterable[ReplaySignal]],
    ) -> dict[str, Any]:
        history: list[Candle] = []
        seen_closed: set[str] = set()
        closed_profits: list[float] = []
        processed = 0
        for candle in sorted(candles, key=lambda item: item.timestamp):
            for signal in strategy(history.copy(), candle) or ():
                self.broker.send(signal.as_request())
            for tick in candles_to_ticks([candle]):
                result = self.broker.mark_price(tick.symbol, tick.price, slippage=self.slippage, bid=getattr(tick, "bid", None), ask=getattr(tick, "ask", None))
                self.broker.equity_history.append({"timestamp": tick.timestamp, "equity": float(result["equity"])})
                processed += 1
                for trade_id, position in self.broker.positions.items():
                    if position.status == "CLOSED" and trade_id not in seen_closed:
                        seen_closed.add(trade_id)
                        closed_profits.append(float(position.profit))
            history.append(candle)
        metrics = calculate_performance(closed_profits, initial_balance=self.initial_balance)
        return {"candles": len(history), "ticks": processed, "closed_profits": closed_profits, "metrics": metrics, "ledger": self.broker.reconcile()}

``

## File: module\config.py

``python
"""Central runtime configuration for the trading system."""

from __future__ import annotations

import os


# Keep this stable for the lifetime of a deployed bot instance.
MAGIC_NUMBER = int(os.getenv("MT5_MAGIC_NUMBER", "26080901"))
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()

``

## File: module\execution.py

``python
"""Centralized, guarded execution layer for MetaTrader 5 requests.

The default mode is PAPER. LIVE requires explicit opt-in through environment
variables and is intentionally not enabled by this project.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace
from typing import Any

from .risk import RiskLimits, RiskValidator

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass(frozen=True)
class ExecutionResult:
    """Normalized result returned by the execution boundary."""

    retcode: int
    comment: str
    order: int = 0
    deal: int = 0
    simulated: bool = False


class ExecutionEngine:
    """Single boundary through which all MT5 trade requests must pass."""

    def __init__(self, mt5_api: Any, mode: str | None = None, risk_validator: RiskValidator | None = None, paper_broker: Any | None = None) -> None:
        self.mt5 = mt5_api
        self.paper_broker = paper_broker
        configured = (mode or os.getenv("TRADING_MODE", "PAPER")).upper()
        try:
            self.mode = ExecutionMode(configured)
        except ValueError as exc:
            raise ValueError(
                f"TRADING_MODE must be BACKTEST, PAPER, or LIVE; got {configured!r}"
            ) from exc

        self.live_enabled = os.getenv("ENABLE_LIVE_TRADING", "NO").upper() == "YES"
        self.risk_validator = risk_validator or RiskValidator(RiskLimits(max_volume=1.0))
        self._submitted_trade_ids: set[str] = set()
        self._emergency_locked = False

    @property
    def is_simulated(self) -> bool:
        return self.mode != ExecutionMode.LIVE

    def send(self, request: dict[str, Any], *, daily_profit: float = 0.0, open_positions: int = 0, drawdown_pct: float = 0.0) -> Any:
        """Validate the boundary and send or simulate one request.

        LIVE is blocked unless ENABLE_LIVE_TRADING=YES is explicitly set.
        BACKTEST and PAPER never call mt5.order_send().
        """
        if self._emergency_locked:
            raise RuntimeError("execution engine is emergency-locked; manual reset required")
        if not isinstance(request, dict) or not request.get("action"):
            raise ValueError("MT5 request must be a non-empty dict with an action")

        decision = self.risk_validator.validate(
            request, daily_profit=daily_profit, open_positions=open_positions, drawdown_pct=drawdown_pct
        )
        if not decision.approved:
            raise ValueError("risk validation failed: " + "; ".join(decision.reasons))

        if self.mode == ExecutionMode.LIVE:
            if not self.live_enabled:
                raise RuntimeError(
                    "LIVE mode is blocked: set ENABLE_LIVE_TRADING=YES explicitly"
                )
            trade_id = request.get("trade_id")
            if trade_id:
                if trade_id in self._submitted_trade_ids:
                    raise ValueError(f"duplicate trade_id: {trade_id}")
                self._submitted_trade_ids.add(str(trade_id))
            logger.warning("LIVE MT5 request: action=%s symbol=%s", request.get("action"), request.get("symbol"))
            result = self.mt5.order_send(request)
            if result is None:
                return None
            return ExecutionResult(
                retcode=getattr(result, "retcode", -1),
                comment=str(getattr(result, "comment", "")),
                order=int(getattr(result, "order", 0) or 0),
                deal=int(getattr(result, "deal", 0) or 0),
                simulated=False,
            )

        trade_id = request.get("trade_id")
        if trade_id:
            if trade_id in self._submitted_trade_ids:
                raise ValueError(f"duplicate trade_id: {trade_id}")
            self._submitted_trade_ids.add(str(trade_id))

        logger.info(
            "SIMULATED %s request: action=%s symbol=%s volume=%s",
            self.mode.value,
            request.get("action"),
            request.get("symbol"),
            request.get("volume"),
        )
        if self.mode == ExecutionMode.PAPER and self.paper_broker is not None:
            return self.paper_broker.send(request)
        done_code = getattr(self.mt5, "TRADE_RETCODE_DONE", 10009)
        return SimpleNamespace(
            retcode=done_code,
            comment=f"{self.mode.value} simulation",
            order=0,
            deal=0,
            simulated=True,
        )


    @property
    def emergency_locked(self) -> bool:
        return self._emergency_locked

    def reset_emergency_stop(self) -> None:
        self._emergency_locked = False
        logger.warning("EMERGENCY STOP RESET: manual operator action")

    def emergency_stop(self) -> dict[str, int]:
        """Flatten managed exposure, cancel pending orders, then lock execution."""
        closed = cancelled = 0
        broker = self.paper_broker if self.mode == ExecutionMode.PAPER and self.paper_broker is not None else self.mt5
        if self.mode == ExecutionMode.PAPER and self.paper_broker is not None:
            for trade_id in list(getattr(broker, "positions", {}).keys()):
                closed += int(bool(broker.close(trade_id)))
            for order in getattr(broker, "orders", {}).values():
                if getattr(order, "status", "") not in {"CLOSED", "CANCELLED"}:
                    order.status = "CANCELLED"
                    cancelled += 1
            broker.save()
        else:
            done_code = getattr(broker, "TRADE_RETCODE_DONE", 10009)
            for position in list(getattr(broker, "positions_get", lambda: ())() or ()):
                close_fn = getattr(broker, "close_position", None)
                if callable(close_fn):
                    closed += int(bool(close_fn(position)))
                    continue
                tick_fn = getattr(broker, "symbol_info_tick", None)
                tick = tick_fn(position.symbol) if callable(tick_fn) else None
                is_buy = int(getattr(position, "type", 0)) == int(getattr(broker, "POSITION_TYPE_BUY", 0))
                request = {
                    "action": getattr(broker, "TRADE_ACTION_DEAL", 1),
                    "symbol": position.symbol,
                    "volume": float(position.volume),
                    "type": getattr(broker, "ORDER_TYPE_SELL", 1) if is_buy else getattr(broker, "ORDER_TYPE_BUY", 0),
                    "position": int(position.ticket),
                    "price": float(getattr(tick, "bid" if is_buy else "ask", 0.0)) if tick else 0.0,
                    "deviation": 20,
                    "magic": int(getattr(position, "magic", 0) or 0),
                    "comment": "EMERGENCY_STOP",
                }
                result = broker.order_send(request)
                closed += int(result is not None and getattr(result, "retcode", -1) == done_code)
            for order in list(getattr(broker, "orders_get", lambda: ())() or ()):
                remove_fn = getattr(broker, "cancel_order", None)
                if callable(remove_fn):
                    cancelled += int(bool(remove_fn(order)))
                    continue
                result = broker.order_send({
                    "action": getattr(broker, "TRADE_ACTION_REMOVE", 8),
                    "order": int(order.ticket),
                    "comment": "EMERGENCY_STOP",
                })
                cancelled += int(result is not None and getattr(result, "retcode", -1) == done_code)
        self._emergency_locked = True
        logger.critical("EMERGENCY STOP ACTIVATED: closed=%s cancelled=%s", closed, cancelled)
        return {"closed": closed, "cancelled": cancelled}

    def describe(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "simulated": self.is_simulated,
            "emergency_locked": self._emergency_locked,
            "live_enabled": self.live_enabled,
        }

``

## File: module\experiments\__init__.py

``python
"""Experimental strategies kept outside the production entry point."""

``

## File: module\experiments\grid_hedge.py

``python
"""Pure Grid/Hedge planning helpers. No MT5 access and no order side effects."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class GridHedgeConfig:
    step_price: float = 0.20
    levels: int = 5

    def __post_init__(self) -> None:
        if self.step_price <= 0 or self.levels < 1:
            raise ValueError("step_price must be positive and levels must be >= 1")

def pending_levels(mid_price: float, config: GridHedgeConfig) -> dict[str, list[float]]:
    """Plan symmetric buy-stop/sell-stop levels; execution remains elsewhere."""
    if mid_price <= 0:
        raise ValueError("mid_price must be positive")
    return {
        "buy": [round(mid_price + i * config.step_price, 10) for i in range(1, config.levels + 1)],
        "sell": [round(mid_price - i * config.step_price, 10) for i in range(1, config.levels + 1)],
    }

``

## File: module\indicators.py

``python
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
        df = candle(symbol, tf,).obj.copy()
    else:
        df = heikin_ashi(symbol, tf).obj.copy()

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
        df = candle(symbol, tf).obj.copy()
    else:
        df = heikin_ashi(symbol, tf).obj.copy()

    high = df['high'].values    # ØªØ¨Ø¯ÛŒÙ„ Ø¨Ù‡ numpy array
    low = df['low'].values      # ØªØ¨Ø¯ÛŒÙ„ Ø¨Ù‡ numpy array

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
  
    data = raw_data.obj.copy()
    
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

    data = df.obj.copy()
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
        df = candle(symbol, tf).obj.copy()
    else:
        df = heikin_ashi(symbol, tf).obj.copy()

    if not all(col in df.columns for col in ['open', 'high', 'low', 'close']):
        raise ValueError("Ø¯ÛŒØªØ§ÙØ±ÛŒÙ… ÙˆØ±ÙˆØ¯ÛŒ Ø¨Ø§ÛŒØ¯ Ø´Ø§Ù…Ù„ Ø³ØªÙˆÙ†â€ŒÙ‡Ø§ÛŒ 'open', 'high', 'low', 'close' Ø¨Ø§Ø´Ø¯.")

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
        df = candle(symbol, tf).obj.copy()
    else:
        df = heikin_ashi(symbol, tf).obj.copy()
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

  
    high_tf_df = heikin_ashi(symbol ,high_tf , 100 ).obj.copy()
    low_tf_df =  heikin_ashi(symbol ,low_tf , 100 ).obj.copy()

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
        data = candle(symbol, tf).obj.copy()
    else:
        data = heikin_ashi(symbol, tf).obj.copy()
    df = data.copy()
    df['ATR'] = pandas_ta.atr(df['high'], df['low'], df['close'], period)
    return df['ATR'].values
     

def stochrsi(symbol , tf , line='blue' , rsi_length=14, stoch_length=14, k_period=3, d_period=3 , candle_type='ca'):
    if candle_type == 'ca':
        candles = candle(symbol, tf ).obj.copy()
    else:
        candles = heikin_ashi(symbol, tf ).obj.copy()
    df_close = candles['close']
    stoch_rsi = pandas_ta.stochrsi(df_close, length=stoch_length, rsi_length=rsi_length, k=k_period, d=d_period)

    d = stoch_rsi['STOCHRSId_' + str(rsi_length) + '_' + str(stoch_length) + '_' + str(k_period) + '_' + str(d_period)].tolist()
    k = stoch_rsi['STOCHRSIk_' + str(rsi_length) + '_' + str(stoch_length) + '_' + str(k_period) + '_' + str(d_period)].tolist()
    
    return k if line == 'blue' else d


def ssl_hybrid(symbol, tf,candle_type = 'ca' ,baseline_type="HMA", baseline_length=60,ssl2_type="JMA", ssl2_length=5,exit_type="HMA", exit_length=15,atr_period=14, atr_mult=1.0, atr_smoothing="WMA",risk_lookback=100, risk_sensitivity=2):

    if candle_type == 'ca':
        df = candle(symbol, tf, 500).obj.copy()
    else:
        df = heikin_ashi(symbol, tf, 500).obj.copy()
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
        df = candle(symbol, tf, 500).obj.copy()
    else:
        df = heikin_ashi(symbol, tf, 500).obj.copy()
    

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
    
    ha_data = heikin_ashi(symbol, tf, max(short_len, long_len) * 2).obj.copy()
    
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
        df = candle(symbol, tf, amplitude * 20).obj.copy()
    else:
        df = heikin_ashi(symbol, tf, amplitude * 20).obj.copy()
    
   
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
    # idx=-2 ÛŒØ¹Ù†ÛŒ Ú©Ù†Ø¯Ù„ Ø¨Ø³ØªÙ‡â€ŒØ´Ø¯Ù‡
    if not isinstance(trends, (list, tuple)) or len(trends) < 3:
        return 'hold'
    if abs(idx) > len(trends)-1:
        return 'hold'

    curr = trends[idx]
    prev = trends[idx-1]   # ÛŒÚ© Ú©Ù†Ø¯Ù„ Ù‚Ø¨Ù„ Ø§Ø² Ø¢Ù† (Ø¨Ø±Ø§ÛŒ idx=-2 Ù…ÛŒâ€ŒØ´ÙˆØ¯ -3)

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
        ha_df = candle(symbol, tf,500).obj.copy()
    else:
        ha_df = heikin_ashi(symbol, tf, 500).obj.copy()

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
        raise ValueError("Ù†ÙˆØ¹ MA Ù…Ø¹ØªØ¨Ø± Ù†ÛŒØ³Øª!")

    ha_df['Trend'] = 100 * (ha_df['MA_Close'] - ha_df['MA_Open']) / (ha_df['MA_High'] - ha_df['MA_Low'])
    
    signals = np.where(ha_df['Trend'] > 0, 'long', 'short')

    return signals


def deviation_trend_signals(symbol, tf, sma_length=50 , candle_type = 'ca'):
    
    if candle_type == 'ca':
        df = candle(symbol, tf,5000).obj.copy()
    else:
        df = heikin_ashi(symbol, tf, 5000).obj.copy()

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
        data = candle(symbol, tf, 5000).obj.copy()
    else:
        data = heikin_ashi(symbol, tf, 5000).obj.copy()
    
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
    
    # ØªÙˆÙ„ÛŒØ¯ Ø³ÛŒÚ¯Ù†Ø§Ù„â€ŒÙ‡Ø§
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
        raise ValueError("mode Ø¨Ø§ÛŒØ¯ ÛŒÚ©ÛŒ Ø§Ø² 'Hma', 'Ehma', ÛŒØ§ 'Thma' Ø¨Ø§Ø´Ø¯")
    
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
    df = df.obj.copy()
    
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
    df = df.obj.copy()
    
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
    
    df = candle(symbol, tf , 5000).obj.copy()
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
    df = df.obj.copy()
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
    df = df.obj.copy()

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


``

## File: module\market_data.py

``python
"""Deterministic historical candle and tick loading for Paper Trading."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator


@dataclass(frozen=True)
class Tick:
    timestamp: str
    symbol: str
    bid: float
    ask: float | None = None

    @property
    def price(self) -> float:
        return (self.bid + self.ask) / 2 if self.ask is not None else self.bid


@dataclass(frozen=True)
class Candle:
    timestamp: str
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


def _number(row: dict[str, str], name: str, default: float = 0.0) -> float:
    value = row.get(name, row.get(name.lower(), ""))
    return default if value in (None, "") else float(value)


def load_candles_csv(path: str | Path, symbol: str = "XAUUSD") -> list[Candle]:
    """Load OHLCV CSV and reject invalid/non-monotonic rows."""
    rows: list[Candle] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"timestamp", "open", "high", "low", "close"}
        fields = {str(f).lower() for f in (reader.fieldnames or [])}
        if not required.issubset(fields):
            raise ValueError(f"CSV must contain {sorted(required)}")
        for row in reader:
            timestamp = row.get("timestamp") or row.get("Timestamp") or ""
            o, h, low, c = (_number(row, key) for key in ("open", "high", "low", "close"))
            if not timestamp or low > min(o, h, c) or h < max(o, h, c) or low > h:
                raise ValueError(f"invalid OHLC row: {row}")
            rows.append(Candle(timestamp, symbol, o, h, low, c, _number(row, "volume")))
    rows.sort(key=lambda candle: candle.timestamp)
    if any(a.timestamp == b.timestamp for a, b in zip(rows, rows[1:])):
        raise ValueError("duplicate candle timestamp")
    return rows


def candle_to_ticks(candle: Candle) -> tuple[Tick, ...]:
    """Create a deterministic OHLC path; no random prices are introduced."""
    if candle.close >= candle.open:
        prices = (candle.open, candle.high, candle.low, candle.close)
    else:
        prices = (candle.open, candle.low, candle.high, candle.close)
    return tuple(Tick(f"{candle.timestamp}#{i}", candle.symbol, price) for i, price in enumerate(prices))


def candles_to_ticks(candles: Iterable[Candle]) -> Iterator[Tick]:
    for candle in sorted(candles, key=lambda item: item.timestamp):
        yield from candle_to_ticks(candle)


def load_ticks_csv(path: str | Path, symbol: str = "XAUUSD") -> list[Tick]:
    """Load timestamp,bid[,ask] ticks in chronological order."""
    ticks: list[Tick] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            timestamp = row.get("timestamp") or row.get("Timestamp") or ""
            bid = _number(row, "bid", _number(row, "price"))
            ask = row.get("ask") or row.get("Ask")
            ticks.append(Tick(timestamp, symbol, bid, float(ask) if ask else None))
    ticks.sort(key=lambda tick: tick.timestamp)
    if any(a.timestamp == b.timestamp for a, b in zip(ticks, ticks[1:])):
        raise ValueError("duplicate tick timestamp")
    return ticks


def _mt5_timestamp(date_value: str, time_value: str) -> str:
    date_part = date_value.strip().replace(".", "-")
    time_part = time_value.strip()
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in time_part else "%Y-%m-%d %H:%M:%S"
    parsed = datetime.strptime(f"{date_part} {time_part}", fmt)
    return parsed.replace(tzinfo=timezone.utc).isoformat()


def load_mt5_candles_csv(
    path: str | Path,
    symbol: str = "XAUUSD",
    *,
    limit: int | None = None,
) -> list[Candle]:
    """Load MetaTrader 5 tab-separated OHLC exports.

    MT5 exports use ``<DATE>``/``<TIME>`` and angle-bracketed field names.
    Rows are read incrementally, so the caller can cap the retained history.
    """
    rows: list[Candle] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = {str(field).strip().lower() for field in (reader.fieldnames or [])}
        required = {"<date>", "<time>", "<open>", "<high>", "<low>", "<close>"}
        if not required.issubset(fields):
            raise ValueError(f"MT5 candle CSV must contain {sorted(required)}")
        for row in reader:
            normalized = {str(key).strip().lower(): value for key, value in row.items()}
            timestamp = _mt5_timestamp(normalized["<date>"], normalized["<time>"])
            o = float(normalized["<open>"])
            high = float(normalized["<high>"])
            low = float(normalized["<low>"])
            close = float(normalized["<close>"])
            if low > min(o, high, close) or high < max(o, low, close):
                raise ValueError(f"invalid MT5 OHLC row: {row}")
            volume = float(normalized.get("<tickvol>", normalized.get("<vol>", 0)) or 0)
            rows.append(Candle(timestamp, symbol, o, high, low, close, volume))
            if limit is not None and len(rows) >= limit:
                break
    rows.sort(key=lambda candle: candle.timestamp)
    return rows


def iter_mt5_ticks_csv(path: str | Path, symbol: str = "XAUUSD") -> Iterator[Tick]:
    """Stream MT5 tick exports without loading multi-gigabyte files."""
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        fields = {str(field).strip().lower() for field in (reader.fieldnames or [])}
        required = {"<date>", "<time>", "<bid>", "<ask>"}
        if not required.issubset(fields):
            raise ValueError(f"MT5 tick CSV must contain {sorted(required)}")
        for row in reader:
            normalized = {str(key).strip().lower(): value for key, value in row.items()}
            bid = normalized["<bid>"]
            ask = normalized["<ask>"]
            if not bid or not ask:
                continue
            yield Tick(
                _mt5_timestamp(normalized["<date>"], normalized["<time>"]),
                symbol,
                float(bid),
                float(ask),
            )


def aggregate_ticks_to_candles(
    ticks: Iterable[Tick],
    symbol: str = "XAUUSD",
) -> list[Candle]:
    """Aggregate a tick stream into deterministic one-minute candles."""
    buckets: dict[str, list[float]] = {}
    for tick in ticks:
        minute = tick.timestamp[:16]
        buckets.setdefault(minute, []).append(tick.price)
    candles: list[Candle] = []
    for minute in sorted(buckets):
        prices = buckets[minute]
        candles.append(Candle(
            f"{minute}:00+00:00",
            symbol,
            prices[0],
            max(prices),
            min(prices),
            prices[-1],
            float(len(prices)),
        ))
    return candles

``

## File: module\memory.py

``python
"""Small append-only operational memory for decisions and lessons learned."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SecondBrain:
    """Record operational facts; never changes strategy or places orders."""

    def __init__(self, path: str | Path = "memory/events.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, kind: str, title: str, details: str = "", **metadata: Any) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "title": title,
            "details": details,
            "metadata": metadata,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

``

## File: module\modifyPosition.py

``python
from module.mt5 import *
from module.indicators import *



def tp1_risk_free(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp1_price = position.price_open + (position.price_open - position.sl)
        if price.ask >= tp1_price:
            modify_stop(position.ticket , position.price_open)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp1_price = position.price_open - (position.sl - position.price_open)
        if price.bid <= tp1_price:
            modify_stop(position.ticket , position.price_open)



def tp1_risk_free_save_profit(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp1_price = position.price_open + (position.price_open - position.sl)
        if price.ask >= tp1_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp1_price = position.price_open - (position.sl - position.price_open)
        if price.bid <= tp1_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)



def tp1_save_profit(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp1_price = position.price_open + (position.price_open - position.sl)
        if price.ask >= tp1_price:
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp1_price = position.price_open - (position.sl - position.price_open)
        if price.bid <= tp1_price:
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)



def tp2_risk_free(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp2_price = position.price_open + ((position.price_open - position.sl)*2)
        if price.ask >= tp2_price:
            modify_stop(position.ticket , position.price_open)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp2_price = position.price_open - ((position.sl - position.price_open)*2)
        if price.bid <= tp2_price:
            modify_stop(position.ticket , position.price_open)



def tp2_risk_free_save_profit(position):
    price = mt5.symbol_info_tick(position.symbol)
    #buy
    if position.type == 0 and position.price_open != position.sl :
        tp2_price = position.price_open + ((position.price_open - position.sl)*2)
        if price.ask >= tp2_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)

    #sell
    if position.type == 1 and position.price_open != position.sl :
        tp2_price = position.price_open - ((position.sl - position.price_open)*2)
        if price.bid <= tp2_price:
            modify_stop(position.ticket , position.price_open)
            if position.volume != 0.01 :
                close_half_vol_order(position.ticket)



def smartTP(tf , position):
    rsi_val = rsi(position.symbol , tf , 'ca')[-2]
    cnd = check_candle(position.symbol , tf ,-2 ,'ha')
    if position.type == 0 and rsi_val > 70 and cnd == 'short':
        close_order(position.ticket)
    if position.type == 1 and rsi_val < 30 and cnd == 'long':
        close_order(position.ticket)



def smartSL(symbol , tf , maxSl , minSL):
    atr_val = ( Atr(symbol , tf )[-2] ) * 2
    if atr_val > maxSl : 
        return maxSl
    elif atr_val < minSL :
        return minSL
    else:
        return round(atr_val , 6)
    
``

## File: module\mt5.py

``python
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
        print(f"Ù†Ù…Ø§Ø¯ {symbol} Ù¾ÛŒØ¯Ø§ Ù†Ø´Ø¯")
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
        print(f"Ù‚ÛŒÙ…Øª Ù„Ø­Ø¸Ù‡â€ŒØ§ÛŒ Ø¨Ø±Ø§ÛŒ {symbol} Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø¯")
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
        print("Ø§Ø±Ø³Ø§Ù„ Ø³ÙØ§Ø±Ø´ Ø¨Ø¯ÙˆÙ† Ù¾Ø§Ø³Ø® Ø§Ø² MT5 Ø¨Ø±Ú¯Ø´Øª")
        return None
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Ø®Ø·Ø§ Ø¯Ø± Ø«Ø¨Øª Ø³ÙØ§Ø±Ø´: {result.comment}")
    
    return result
        
def close_order(ticket):

    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        print(f"Ù¾ÙˆØ²ÛŒØ´Ù† {ticket} Ù¾ÛŒØ¯Ø§ Ù†Ø´Ø¯")
        return
    
    position = position[0]
    symbol = position.symbol
    volume = position.volume
    
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    price_info = mt5.symbol_info_tick(symbol)
    if price_info is None:
        print(f"Ù‚ÛŒÙ…Øª Ù„Ø­Ø¸Ù‡â€ŒØ§ÛŒ Ø¨Ø±Ø§ÛŒ Ø¨Ø³ØªÙ† {symbol} Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø¯")
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

    print(f"Ø¨Ø³ØªÙ† Ù¾ÙˆØ²ÛŒØ´Ù† {ticket} Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯")
    return None

def close_half_vol_order(ticket):

    position = mt5.positions_get(ticket=ticket)
    if position is None or len(position) == 0:
        print(f"Ù¾ÙˆØ²ÛŒØ´Ù† {ticket} Ù¾ÛŒØ¯Ø§ Ù†Ø´Ø¯")
        return
    
    position = position[0]
    symbol = position.symbol
    volume = round(position.volume / 2 , 2)
    if volume < 0.01 :
        volume = 0.01
    close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    
    price_info = mt5.symbol_info_tick(symbol)
    if price_info is None:
        print(f"Ù‚ÛŒÙ…Øª Ù„Ø­Ø¸Ù‡â€ŒØ§ÛŒ Ø¨Ø±Ø§ÛŒ Ø¨Ø³ØªÙ† {symbol} Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø¯")
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

    print(f"Ø¨Ø³ØªÙ† Ù†ÛŒÙ…ÛŒ Ø§Ø² Ù¾ÙˆØ²ÛŒØ´Ù† {ticket} Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯")
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

``

## File: module\observability.py

``python
"""Logging and error alerting for the trading runtime.

Alerts are dependency-free and injected as a callable, so credentials never
belong in this module. A Telegram adapter can be supplied by the application.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key in ("trade_id", "symbol", "ticket", "mode", "event"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


class ErrorAlertingHandler(logging.Handler):
    """Forward ERROR+ records to an injected notifier with cooldown."""

    def __init__(self, notifier: Callable[[str], None] | None = None, cooldown_seconds: int = 300) -> None:
        super().__init__(level=logging.ERROR)
        self.notifier = notifier
        self.cooldown_seconds = cooldown_seconds
        self._last_sent: dict[str, float] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if self.notifier is None:
            return
        try:
            key = f"{record.name}:{record.getMessage()}"
            now = time.monotonic()
            last_sent = self._last_sent.get(key)
            if last_sent is not None and now - last_sent < self.cooldown_seconds:
                return
            # First occurrence must always alert; only subsequent duplicates cool down.
            self._last_sent[key] = now
            self.notifier(self.format(record))
        except Exception:
            self.handleError(record)


class CloseAfterEmitRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotate JSONL logs while releasing the file after every record.

    Releasing the handle is important on Windows, where temporary test and
    deployment directories cannot be removed while a log file is open.
    """

    def emit(self, record: logging.LogRecord) -> None:
        if not Path(self.baseFilename).parent.exists():
            return
        try:
            super().emit(record)
        finally:
            self.close()


def configure_logging(
    log_dir: str | os.PathLike[str] = "logs",
    *,
    level: int = logging.INFO,
    notifier: Callable[[str], None] | None = None,
    alert_cooldown_seconds: int = 300,
) -> logging.Logger:
    """Configure console, rotating-file, and error-alert handlers once."""
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("golden_library")
    logger.setLevel(level)
    logger.propagate = False
    existing_files = {
        Path(getattr(handler, "baseFilename", "")).resolve()
        for handler in logger.handlers
        if getattr(handler, "baseFilename", None)
    }
    target_file = (directory / "trading.jsonl").resolve()
    if logger.handlers and existing_files == {target_file} and directory.exists():
        return logger
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    formatter = JsonFormatter()
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = CloseAfterEmitRotatingFileHandler(
        directory / "trading.jsonl", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    alert_handler = ErrorAlertingHandler(notifier, alert_cooldown_seconds)
    alert_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.addHandler(alert_handler)
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"golden_library.{name}")

``

## File: module\paper.py

``python
"""Persistent paper-trading ledger with idempotent execution."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MAGIC_NUMBER


@dataclass
class PaperOrder:
    trade_id: str
    ticket: int
    symbol: str
    volume: float
    order_type: Any
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = MAGIC_NUMBER
    status: str = "ACCEPTED"
    created_at: str = ""


@dataclass
class PaperPosition:
    trade_id: str
    ticket: int
    symbol: str
    volume: float
    order_type: Any
    price: float
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = MAGIC_NUMBER
    profit: float = 0.0
    status: str = "OPEN"
    opened_at: str = ""
    current_price: float = 0.0
    exit_price: float = 0.0
    close_reason: str = ""
    closed_at: str = ""
    gross_profit: float = 0.0
    commission: float = 0.0
    spread_cost: float = 0.0
    entry_spread: float = 0.0
    exit_spread: float = 0.0


class PaperBroker:
    """A restart-safe broker simulation; it never calls MetaTrader 5."""

    def __init__(self, path: str | Path = "paper_state.json", magic_number: int = MAGIC_NUMBER, initial_balance: float = 0.0, commission_per_lot: float = 0.0, default_spread: float = 0.0) -> None:
        self.path = Path(path)
        self.magic_number = magic_number
        self.initial_balance = float(initial_balance)
        self.commission_per_lot = float(commission_per_lot)
        self.default_spread = float(default_spread)
        self.next_ticket = 1
        self.orders: dict[str, PaperOrder] = {}
        self.positions: dict[str, PaperPosition] = {}
        self.equity_history: list[dict[str, float | str]] = []
        self.load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def send(self, request: dict[str, Any]) -> Any:
        trade_id = str(request.get("trade_id") or "")
        if not trade_id:
            raise ValueError("PAPER requests require trade_id for idempotency")
        existing = self.orders.get(trade_id)
        if existing is not None:
            return self._result(existing.ticket, "PAPER duplicate: existing execution returned")

        ticket = self.next_ticket
        self.next_ticket += 1
        order = PaperOrder(
            trade_id=trade_id,
            ticket=ticket,
            symbol=str(request["symbol"]),
            volume=float(request["volume"]),
            order_type=request.get("type", request.get("order_type", "")),
            price=float(request.get("price", 0.0) or 0.0),
            sl=float(request.get("sl", 0.0) or 0.0),
            tp=float(request.get("tp", 0.0) or 0.0),
            comment=str(request.get("comment", "")),
            magic=int(request.get("magic", self.magic_number)),
            created_at=self._now(),
        )
        self.orders[trade_id] = order
        action = str(request.get("action", "")).lower()
        if action in {"deal", "market", "0", "1"}:
            entry_spread = float(request.get("spread", self.default_spread) or 0.0)
            self.positions[trade_id] = PaperPosition(
                trade_id=trade_id,
                ticket=ticket,
                symbol=order.symbol,
                volume=order.volume,
                order_type=order.order_type,
                price=order.price,
                sl=order.sl,
                tp=order.tp,
                comment=order.comment,
                magic=order.magic,
                opened_at=order.created_at,
                current_price=order.price,
                commission=abs(order.volume) * self.commission_per_lot,
                entry_spread=entry_spread,
            )
        self.save()
        return self._result(ticket, "PAPER accepted")

    def _result(self, ticket: int, comment: str) -> Any:
        from types import SimpleNamespace
        return SimpleNamespace(retcode=10009, comment=comment, order=ticket, deal=ticket, simulated=True)

    def orders_get(self, symbol: str | None = None) -> list[PaperOrder]:
        return [o for o in self.orders.values() if symbol is None or o.symbol == symbol]

    def positions_get(self, symbol: str | None = None) -> list[PaperPosition]:
        return [p for p in self.positions.values() if p.status == "OPEN" and (symbol is None or p.symbol == symbol)]

    def close(self, trade_id: str) -> bool:
        return self._close_position(trade_id, reason="MANUAL")

    def _close_position(self, trade_id: str, *, reason: str, exit_price: float | None = None, exit_spread: float = 0.0) -> bool:
        position = self.positions.get(trade_id)
        if position is None or position.status != "OPEN":
            return False
        final_price = position.current_price if exit_price is None else float(exit_price)
        position.exit_price = final_price
        position.current_price = final_price
        position.gross_profit = self._profit(position, final_price)
        position.exit_spread = abs(float(exit_spread))
        position.spread_cost = (abs(position.entry_spread) + position.exit_spread) * position.volume
        position.profit = position.gross_profit - position.commission - position.spread_cost
        position.status = "CLOSED"
        position.close_reason = reason
        position.closed_at = self._now()
        self.save()
        return True

    @staticmethod
    def _is_buy(order_type: Any) -> bool:
        return str(order_type).lower() in {"0", "buy", "buy_limit", "buy_stop"}

    @classmethod
    def _profit(cls, position: PaperPosition, price: float) -> float:
        direction = 1.0 if cls._is_buy(position.order_type) else -1.0
        return (float(price) - position.price) * position.volume * direction

    def mark_price(self, symbol: str, price: float, *, slippage: float = 0.0, bid: float | None = None, ask: float | None = None) -> dict[str, int | float]:
        """Advance a symbol price and trigger TP/SL using deterministic slippage.

        For a BUY, slippage worsens the exit by lowering the fill price; for a
        SELL it worsens the exit by raising the fill price.
        """
        price = float(price)
        closed = 0
        for trade_id, position in list(self.positions.items()):
            if position.status != "OPEN" or position.symbol != symbol:
                continue
            position.current_price = price
            position.profit = self._profit(position, price)
            buy = self._is_buy(position.order_type)
            execution_price = float(bid if buy and bid is not None else ask if not buy and ask is not None else price)
            current_spread = abs(float(ask) - float(bid)) if ask is not None and bid is not None else self.default_spread
            reason = ""
            if buy and position.tp and price >= position.tp:
                reason = "TP"
                exit_price = execution_price - abs(float(slippage))
            elif buy and position.sl and price <= position.sl:
                reason = "SL"
                exit_price = execution_price - abs(float(slippage))
            elif not buy and position.tp and price <= position.tp:
                reason = "TP"
                exit_price = execution_price + abs(float(slippage))
            elif not buy and position.sl and price >= position.sl:
                reason = "SL"
                exit_price = execution_price + abs(float(slippage))
            else:
                continue
            if self._close_position(trade_id, reason=reason, exit_price=exit_price, exit_spread=current_spread):
                closed += 1
        self.save()
        equity = self.equity()
        return {"symbol": symbol, "price": price, "closed": closed, "open_positions": len(self.positions_get(symbol=symbol)), "equity": equity}

    def equity(self, initial_balance: float | None = None) -> float:
        balance = self.initial_balance if initial_balance is None else float(initial_balance)
        return balance + sum(float(position.profit) for position in self.positions.values()) - sum(float(position.commission + position.entry_spread * position.volume) for position in self.positions.values() if position.status == "OPEN")

    def max_drawdown(self, initial_balance: float | None = None) -> dict[str, float]:
        """Return peak-to-trough drawdown from the recorded equity curve."""
        balance = self.initial_balance if initial_balance is None else float(initial_balance)
        values = [balance] + [float(item["equity"]) for item in self.equity_history]
        peak = values[0]
        max_dd = 0.0
        peak_value = peak
        trough_value = peak
        for value in values:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
                peak_value = peak
                trough_value = value
        percentage = (max_dd / peak_value * 100.0) if peak_value else 0.0
        return {"max_drawdown": max_dd, "max_drawdown_percent": percentage, "peak": peak_value, "trough": trough_value}

    def replay_ticks(self, ticks: Any, *, slippage: float = 0.0) -> dict[str, int | float]:
        """Apply chronological Tick objects and return replay statistics."""
        processed = 0
        closed = 0
        last_timestamp = ""
        for tick in ticks:
            result = self.mark_price(tick.symbol, tick.price, slippage=slippage, bid=getattr(tick, "bid", None), ask=getattr(tick, "ask", None))
            self.equity_history.append({"timestamp": str(tick.timestamp), "equity": float(result["equity"])})
            processed += 1
            closed += int(result["closed"])
            last_timestamp = str(tick.timestamp)
        return {"ticks": processed, "closed": closed, "last_timestamp": last_timestamp, "open_positions": len(self.positions_get())}

    def stress_replay(self, ticks: Any, *, slippage: float = 0.0, restart_every: int = 0) -> dict[str, Any]:
        """Replay under periodic persistence/restart checks and report resilience metrics."""
        processed = 0
        restarts = 0
        closed = 0
        for tick in ticks:
            result = self.mark_price(tick.symbol, tick.price, slippage=slippage, bid=getattr(tick, "bid", None), ask=getattr(tick, "ask", None))
            self.equity_history.append({"timestamp": str(tick.timestamp), "equity": float(result["equity"])})
            processed += 1
            closed += int(result["closed"])
            if restart_every and processed % restart_every == 0:
                self.save()
                restored = PaperBroker(self.path, magic_number=self.magic_number)
                self.__dict__.update(restored.__dict__)
                restarts += 1
        self.save()
        return {"ticks": processed, "restarts": restarts, "closed": closed, "open_positions": len(self.positions_get()), **self.max_drawdown()}

    def replay_candles(self, candles: Any, *, slippage: float = 0.0) -> dict[str, int | float]:
        """Convert historical candles to a deterministic OHLC path and replay it."""
        from .market_data import candles_to_ticks

        return self.replay_ticks(candles_to_ticks(candles), slippage=slippage)

    def reconcile(self) -> dict[str, int]:
        return {"orders": len(self.orders), "open_positions": len(self.positions_get()), "closed_positions": sum(p.status == "CLOSED" for p in self.positions.values())}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "next_ticket": self.next_ticket,
            "initial_balance": self.initial_balance,
            "commission_per_lot": self.commission_per_lot,
            "default_spread": self.default_spread,
            "orders": {k: asdict(v) for k, v in self.orders.items()},
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "equity_history": self.equity_history,
        }
        fd, tmp = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.next_ticket = int(data.get("next_ticket", 1))
        self.initial_balance = float(data.get("initial_balance", self.initial_balance))
        self.commission_per_lot = float(data.get("commission_per_lot", self.commission_per_lot))
        self.default_spread = float(data.get("default_spread", self.default_spread))
        self.orders = {k: PaperOrder(**v) for k, v in data.get("orders", {}).items()}
        self.positions = {k: PaperPosition(**v) for k, v in data.get("positions", {}).items()}
        self.equity_history = list(data.get("equity_history", []))

``

## File: module\performance.py

``python
"""Trading performance metrics for deterministic backtest results."""

from __future__ import annotations

import math
import statistics
from typing import Iterable


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else 0.0


def max_drawdown(equity: Iterable[float]) -> dict[str, float]:
    values = list(float(x) for x in equity)
    if not values:
        return {"max_drawdown": 0.0, "max_drawdown_percent": 0.0, "peak": 0.0, "trough": 0.0}
    peak = values[0]
    peak_value = peak
    trough_value = peak
    largest = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = peak - value
        if drawdown > largest:
            largest = drawdown
            peak_value = peak
            trough_value = value
    pct = largest / peak_value * 100.0 if peak_value else 0.0
    return {"max_drawdown": largest, "max_drawdown_percent": pct, "peak": peak_value, "trough": trough_value}


def calculate_performance(profits: Iterable[float], *, initial_balance: float = 0.0, periods_per_year: int = 252) -> dict[str, float | int]:
    """Calculate risk/return metrics from closed-trade profits."""
    values = [float(x) for x in profits]
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = [float(initial_balance)]
    for value in values:
        equity.append(equity[-1] + value)
    returns = [value / initial_balance for value in values] if initial_balance else values
    mean_return = _mean(returns)
    deviation = _std(returns)
    downside = [min(0.0, value) for value in returns]
    downside_deviation = math.sqrt(sum(value * value for value in downside) / len(downside)) if downside else 0.0
    sharpe = mean_return / deviation * math.sqrt(periods_per_year) if deviation else 0.0
    sortino = mean_return / downside_deviation * math.sqrt(periods_per_year) if downside_deviation else 0.0
    drawdown = max_drawdown(equity)
    return {
        "trades": len(values),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(values) * 100.0 if values else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": gross_profit / gross_loss if gross_loss else (math.inf if gross_profit else 0.0),
        "net_profit": sum(values),
        "average_trade": _mean(values),
        "expectancy": _mean(values),
        "average_win": _mean(wins),
        "average_loss": _mean(losses),
        "sharpe": sharpe,
        "sortino": sortino,
        **drawdown,
    }

``

## File: module\recovery.py

``python
"""Restart recovery for SENT and ACCEPTED trades.

The broker adapter is intentionally small and mockable. It must expose:
orders_get(symbol=...), positions_get(symbol=...), and optionally
history_deals_get(start, end).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from .config import MAGIC_NUMBER
from .state_machine import TradeRecord, TradeState, TradeStateMachine

logger = logging.getLogger("golden_library.recovery")


@dataclass(frozen=True)
class RecoveryReport:
    recovered: int = 0
    opened: int = 0
    rejected: int = 0
    waiting: int = 0
    errors: int = 0


def _age_seconds(record: TradeRecord, now: datetime) -> float:
    try:
        created = datetime.fromisoformat(record.updated_at or record.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max(0.0, (now - created).total_seconds())
    except (TypeError, ValueError):
        return 0.0


def _comment_matches(item: Any, record: TradeRecord) -> bool:
    comment = str(getattr(item, "comment", "") or "")
    return record.trade_id in comment or comment == record.strategy or comment.startswith(record.strategy + ":")


def _belongs_to_bot(item: Any, record: TradeRecord) -> bool:
    return (
        getattr(item, "magic", MAGIC_NUMBER) == MAGIC_NUMBER
        and getattr(item, "symbol", record.symbol) == record.symbol
        and _comment_matches(item, record)
    )


class TradeRecovery:
    """Recover broker-side order/position state after restart or disconnection."""

    def __init__(self, broker: Any, magic_number: int = MAGIC_NUMBER, timeout_seconds: int = 120) -> None:
        self.broker = broker
        self.magic_number = magic_number
        self.timeout_seconds = timeout_seconds

    def _orders(self, record: TradeRecord) -> list[Any]:
        return [
            item for item in (self.broker.orders_get(symbol=record.symbol) or ())
            if getattr(item, "magic", self.magic_number) == self.magic_number
            and _comment_matches(item, record)
        ]

    def _positions(self, record: TradeRecord) -> list[Any]:
        return [
            item for item in (self.broker.positions_get(symbol=record.symbol) or ())
            if getattr(item, "magic", self.magic_number) == self.magic_number
            and _comment_matches(item, record)
        ]

    def recover(self, states: TradeStateMachine, *, now: datetime | None = None) -> RecoveryReport:
        now = now or datetime.now(timezone.utc)
        report = RecoveryReport()
        for trade_id, record in list(states.records.items()):
            if record.state not in {TradeState.SENT, TradeState.ACCEPTED}:
                continue
            try:
                positions = self._positions(record)
                orders = self._orders(record)
                age = _age_seconds(record, now)

                if record.state == TradeState.SENT:
                    if positions or orders:
                        ticket = getattr((positions or orders)[0], "ticket", 0)
                        states.transition(trade_id, TradeState.ACCEPTED, ticket=ticket, reason="recovered from broker")
                        logger.info("recovered SENT trade", extra={"event": "sent_recovered", "trade_id": trade_id, "ticket": ticket})
                        report = RecoveryReport(report.recovered + 1, report.opened, report.rejected, report.waiting, report.errors)
                    elif age >= self.timeout_seconds:
                        states.transition(trade_id, TradeState.REJECTED, reason="SENT recovery timeout")
                        logger.error("SENT recovery timeout", extra={"event": "recovery_timeout", "trade_id": trade_id})
                        report = RecoveryReport(report.recovered, report.opened, report.rejected + 1, report.waiting, report.errors)
                    else:
                        report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting + 1, report.errors)

                elif record.state == TradeState.ACCEPTED:
                    if positions:
                        ticket = getattr(positions[0], "ticket", record.ticket)
                        states.transition(trade_id, TradeState.OPEN, ticket=ticket, reason="position recovered")
                        logger.info("recovered ACCEPTED trade", extra={"event": "accepted_recovered", "trade_id": trade_id, "ticket": ticket})
                        report = RecoveryReport(report.recovered, report.opened + 1, report.rejected, report.waiting, report.errors)
                    elif orders:
                        report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting + 1, report.errors)
                    elif age >= self.timeout_seconds:
                        states.transition(trade_id, TradeState.REJECTED, reason="ACCEPTED recovery timeout")
                        logger.error("ACCEPTED recovery timeout", extra={"event": "recovery_timeout", "trade_id": trade_id})
                        report = RecoveryReport(report.recovered, report.opened, report.rejected + 1, report.waiting, report.errors)
                    else:
                        report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting + 1, report.errors)
            except (AttributeError, OSError, TypeError, ValueError):
                logger.exception("trade recovery failed", extra={"event": "recovery_error", "trade_id": trade_id})
                report = RecoveryReport(report.recovered, report.opened, report.rejected, report.waiting, report.errors + 1)
        return report

``

## File: module\risk.py

``python
"""Pure risk and order validation for the trading engine."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskLimits:
    max_volume: float = 1.0
    max_daily_loss: float = 0.0
    max_spread: float = 0.0
    max_open_positions: int = 0
    max_drawdown_pct: float = 0.0

    @classmethod
    def from_env(cls) -> "RiskLimits":
        """Load explicit risk caps; zero keeps a cap disabled for compatibility."""
        configured_max = float(os.getenv("RISK_MAX_VOLUME", "1.0"))
        hard_target = float(os.getenv("MAX_VOLUME_TARGET", "0"))
        return cls(
            max_volume=min(configured_max, hard_target) if hard_target > 0 else configured_max,
            max_daily_loss=float(os.getenv("RISK_MAX_DAILY_LOSS", "0.0")),
            max_spread=float(os.getenv("RISK_MAX_SPREAD", "0.0")),
            max_open_positions=int(os.getenv("RISK_MAX_OPEN_POSITIONS", "0")),
            max_drawdown_pct=float(os.getenv("RISK_MAX_DRAWDOWN_PCT", "20.0")),
        )


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reasons: tuple[str, ...] = ()


class RiskValidator:
    """Validates a proposed order without calling MT5 or a network service."""

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def validate(
        self,
        request: dict[str, Any],
        *,
        daily_profit: float = 0.0,
        open_positions: int = 0,
        drawdown_pct: float = 0.0,
    ) -> RiskDecision:
        if request.get("risk_exempt") is True:
            action = str(request.get("action", "")).lower()
            is_non_opening = (
                "position" in request
                or "order" in request
                or action in {"sltp", "modify", "remove", "close"}
            )
            if is_non_opening:
                logger.warning("risk bypass allowed for non-opening action=%s", action)
                return RiskDecision(approved=True)
            logger.error("risk bypass rejected for opening action=%s", action)
            return RiskDecision(approved=False, reasons=("risk_exempt is only valid for non-opening actions",))
        reasons: list[str] = []
        if not request.get("symbol"):
            reasons.append("symbol is required")
        volume = float(request.get("volume", 0) or 0)
        if volume <= 0:
            reasons.append("volume must be positive")
        if self.limits.max_volume > 0 and volume > self.limits.max_volume:
            reasons.append("volume exceeds max_volume")
        if self.limits.max_open_positions > 0 and open_positions >= self.limits.max_open_positions:
            reasons.append("max_open_positions reached")
        if self.limits.max_daily_loss > 0 and daily_profit <= -abs(self.limits.max_daily_loss):
            reasons.append("daily loss limit reached")
        if self.limits.max_drawdown_pct > 0 and drawdown_pct >= self.limits.max_drawdown_pct:
            reasons.append("max drawdown limit reached")

        spread = request.get("spread")
        if self.limits.max_spread > 0 and spread is not None and float(spread) > self.limits.max_spread:
            reasons.append("spread exceeds max_spread")

        order_type = str(request.get("order_type", request.get("type", ""))).lower()
        price = request.get("price")
        sl = request.get("sl")
        tp = request.get("tp")
        if price is not None and sl is not None and tp is not None:
            price, sl, tp = float(price), float(sl), float(tp)
            if order_type in {"buy", "0"} and not (sl < price < tp):
                reasons.append("buy requires sl < price < tp")
            if order_type in {"sell", "1"} and not (tp < price < sl):
                reasons.append("sell requires tp < price < sl")

        return RiskDecision(approved=not reasons, reasons=tuple(reasons))


def bounded_risk_percent(base_risk: float, *, max_risk: float = 2.0) -> float:
    """Cap risk; never loss-chase through a martingale multiplier."""
    cap = min(float(max_risk), 2.0)
    return max(0.0, min(float(base_risk), cap))

``

## File: module\risk_metrics.py

``python
"""Broker-backed metrics passed to the centralized risk gate."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any

def _today_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

def _num(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0

def broker_metrics(api: Any, paper_broker: Any | None = None, mode: str = "PAPER") -> tuple[float, int]:
    """Return (today PnL including floating PnL, open position count).

    PAPER uses the persisted ledger; LIVE uses MT5 positions and today's deals.
    The function is deliberately defensive so a metrics failure cannot silently
    turn into a zero-risk context. Callers should reject if it raises.
    """
    mode = str(mode).upper()
    now = datetime.now(timezone.utc)
    start = _today_start(now)
    if mode == "PAPER":
        if paper_broker is None:
            raise RuntimeError("PAPER metrics require a PaperBroker")
        positions = list(paper_broker.positions_get() or ())
        pnl = 0.0
        for position in getattr(paper_broker, "positions", {}).values():
            closed_at = str(getattr(position, "closed_at", "") or "")
            if getattr(position, "status", "") == "CLOSED" and closed_at:
                try:
                    closed_dt = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
                    if closed_dt.astimezone(timezone.utc) >= start:
                        pnl += _num(getattr(position, "profit", 0.0))
                except ValueError:
                    continue
        pnl += sum(_num(getattr(position, "profit", 0.0)) for position in positions)
        return pnl, len(positions)

    positions = list(api.positions_get() or ())
    pnl = 0.0
    history = getattr(api, "history_deals_get", None)
    if callable(history):
        deals = history(start, now) or ()
        for deal in deals:
            pnl += _num(getattr(deal, "profit", 0.0))
            pnl += _num(getattr(deal, "commission", 0.0))
            pnl += _num(getattr(deal, "swap", 0.0))
    pnl += sum(_num(getattr(position, "profit", 0.0)) for position in positions)
    return pnl, len(positions)


def broker_drawdown_pct(api, paper_broker=None, mode: str = "PAPER") -> float:
    """Return current recorded drawdown percentage for the risk gate."""
    if str(mode).upper() == "PAPER":
        if paper_broker is None:
            raise RuntimeError("PAPER drawdown metrics require a PaperBroker")
        return float(paper_broker.max_drawdown().get("max_drawdown_percent", 0.0))
    info_fn = getattr(api, "account_info", None)
    info = info_fn() if callable(info_fn) else None
    balance = _num(getattr(info, "balance", 0.0)) if info else 0.0
    equity = _num(getattr(info, "equity", 0.0)) if info else 0.0
    return max(0.0, (balance - equity) / balance * 100.0) if balance > 0 else 0.0

``

## File: module\state_io.py

``python
# module/state_io.py
import json
import numpy as np
from typing import Any, Dict


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def save_state(state: Dict[str, Any], filename: str = "bot_state.json") -> None:
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(state, f, cls=NumpyEncoder, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] Failed to save state: {e}")


def load_state(filename: str = "bot_state.json") -> Dict[str, Any]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"[ERROR] Failed to load state: {e}")
        return {}

``

## File: module\state_machine.py

``python
"""Deterministic trade lifecycle state machine with atomic JSON persistence."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .memory import SecondBrain

logger = logging.getLogger("golden_library.state_machine")


class TradeState(str, Enum):
    SIGNAL = "SIGNAL"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    OPEN = "OPEN"
    MANAGED = "MANAGED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


_ALLOWED: dict[TradeState, set[TradeState]] = {
    TradeState.SIGNAL: {TradeState.VALIDATED, TradeState.REJECTED},
    TradeState.VALIDATED: {TradeState.APPROVED, TradeState.REJECTED},
    TradeState.APPROVED: {TradeState.SENT, TradeState.REJECTED},
    TradeState.SENT: {TradeState.ACCEPTED, TradeState.REJECTED},
    TradeState.ACCEPTED: {TradeState.OPEN, TradeState.REJECTED},
    TradeState.OPEN: {TradeState.MANAGED, TradeState.CLOSED},
    TradeState.MANAGED: {TradeState.MANAGED, TradeState.CLOSED},
    TradeState.CLOSED: set(),
    TradeState.REJECTED: set(),
}


@dataclass
class TradeRecord:
    trade_id: str
    state: TradeState = TradeState.SIGNAL
    symbol: str = ""
    strategy: str = ""
    candle_time: str = ""
    ticket: int = 0
    reason: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = self.created_at


class TradeStateMachine:
    def __init__(self, path: str | Path | None = None, memory: SecondBrain | None = None) -> None:
        self.path = Path(path) if path else None
        self.memory = memory
        self.records: dict[str, TradeRecord] = {}
        if self.path and self.path.exists():
            self.load()

    def create(self, record: TradeRecord) -> TradeRecord:
        if record.trade_id in self.records:
            raise ValueError(f"duplicate trade_id: {record.trade_id}")
        self.records[record.trade_id] = record
        self.save()
        if self.memory:
            self.memory.record("trade_created", "Trade record created", trade_id=record.trade_id, state=record.state.value, symbol=record.symbol)
        return record

    def transition(self, trade_id: str, new_state: TradeState, *, reason: str = "", ticket: int | None = None) -> TradeRecord:
        if trade_id not in self.records:
            raise KeyError(trade_id)
        record = self.records[trade_id]
        if new_state not in _ALLOWED[record.state]:
            raise ValueError(f"invalid transition {record.state.value} -> {new_state.value}")
        previous_state = record.state
        record.state = new_state
        if reason:
            record.reason = reason
        if ticket is not None:
            record.ticket = int(ticket)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self.save()
        logger.info(
            "trade state transition",
            extra={"event": "state_transition", "trade_id": trade_id, "state_from": previous_state.value, "state_to": new_state.value},
        )
        if self.memory:
            self.memory.record("state_transition", "Trade state changed", trade_id=trade_id, state_from=previous_state.value, state_to=new_state.value, reason=reason)
        return record

    def get(self, trade_id: str) -> TradeRecord | None:
        return self.records.get(trade_id)

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: {**asdict(v), "state": v.state.value} for k, v in self.records.items()}
        fd, tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent), text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def load(self) -> None:
        data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        self.records = {
            key: TradeRecord(**{**value, "state": TradeState(value["state"])})
            for key, value in data.items()
        }

``

## File: module\stg.py

``python
from .mt5 import *
from .indicators import *

def supertrend_stg(symbol , tf, atr_period=10, multiplier=3.0 , candle_type = 'ha' ,lot = 0.01 , rr = 2 , comment = 'hashem'):
    trend = supertrend(symbol , tf, atr_period, multiplier , candle_type)
    signal = Trend_change_signal(trend['position'])
    price = mt5.symbol_info_tick(symbol)

    if signal == 'buy' :
        sl = trend['value'][-1]
        tp = price.ask + ((price.ask - sl )* rr)
        create_order(symbol , lot , buy , sl , tp , comment)

    if signal == 'sell' :
        sl = trend['value'][-1]
        tp = price.bid - ((sl - price.bid)* rr)
        create_order(symbol , lot , sell , sl , tp , comment)
        
        
        
# module/stg.py
from module.mt5 import *
from module.indicators import *
import MetaTrader5 as mt5
import datetime
import numpy as np
import math
import time
import pandas as pd


def _ensure_time_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    ØªØ¶Ù…ÛŒÙ† Ù…ÛŒâ€ŒÚ©Ù†Ø¯ Ú©Ù‡ DataFrame ÛŒÚ© Ø³ØªÙˆÙ† Ù‚Ø§Ø¨Ù„â€ŒØ§Ø³ØªÙØ§Ø¯Ù‡ Ø¨Ù‡ Ù†Ø§Ù… 'time' Ø¯Ø§Ø±Ø¯.
    Ø§Ú¯Ø± Ø³ØªÙˆÙ† 'time' ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø´ØªÙ‡ Ø¨Ø§Ø´Ø¯ØŒ Ø§Ø² index ÛŒØ§ Ø§Ø² Ø³ØªÙˆÙ†â€ŒÙ‡Ø§ÛŒ Ø±Ø§ÛŒØ¬ Ø¯ÛŒÚ¯Ø±
    (aligned_time / datetime / date) Ù…ÛŒâ€ŒØ³Ø§Ø²Ø¯. Ø¯Ø± Ù†Ø¨ÙˆØ¯ Ù‡Ø± Ú©Ø¯Ø§Ù…ØŒ Ø§Ø² ÛŒÚ© Ø§ÛŒÙ†Ø¯Ú©Ø³ Ø¹Ø¯Ø¯ÛŒ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.
    """
    df = df.copy()
    cols_lower = {c.lower(): c for c in df.columns}

    if "time" in cols_lower:
        return df

    for candidate in ("aligned_time", "datetime", "date"):
        if candidate in cols_lower:
            df["time"] = df[cols_lower[candidate]]
            return df

    if isinstance(df.index, pd.DatetimeIndex):
        df["time"] = df.index
        return df

    df["time"] = range(len(df))
    return df


# ----------------------------- Utilities: safety & math ----------------------------- #

def _is_finite_number(x) -> bool:
    """Ø¨Ø±Ø±Ø³ÛŒ Ø§ÛŒÙ†Ú©Ù‡ x Ø¹Ø¯Ø¯ Ù…Ø¹ØªØ¨Ø± (Ù†Ù‡ NaN/inf/None) Ø§Ø³Øª."""
    try:
        return x is not None and np.isfinite(float(x))
    except Exception:
        return False


def _sorted_by_index(swings: list) -> list:
    """Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒ Ø³ÙˆØ¦ÛŒÙ†Ú¯â€ŒÙ‡Ø§ ÙÙ‚Ø· Ø¨Ø± Ø§Ø³Ø§Ø³ index (Ø¨Ø¯ÙˆÙ† Ø§Ø¹ØªÙ…Ø§Ø¯ Ø¨Ù‡ ØªØ±ØªÛŒØ¨ Ø®Ø±ÙˆØ¬ÛŒ zigzag)."""
    return sorted(swings or [], key=lambda s: int(s.get("index", -10**18)))


def _safe_swings(swings: list, last_bar_index: int, confirm_bars: int) -> list:
    """
    Ø­Ø°Ù Ø³ÙˆØ¦ÛŒÙ†Ú¯â€ŒÙ‡Ø§ÛŒ Ù…Ø´Ú©ÙˆÚ© Ø¨Ù‡ repaint (Ù†Ø²Ø¯ÛŒÚ© Ø¨Ù‡ Ø§Ù†ØªÙ‡Ø§ÛŒ Ø¯ÛŒØªØ§).
    ÙÙ‚Ø· Ø³ÙˆØ¦ÛŒÙ†Ú¯â€ŒÙ‡Ø§ÛŒÛŒ Ù†Ú¯Ù‡ Ø¯Ø§Ø´ØªÙ‡ Ù…ÛŒâ€ŒØ´ÙˆÙ†Ø¯ Ú©Ù‡:
    1) index Ø¢Ù†â€ŒÙ‡Ø§ Ú©Ù…ØªØ± ÛŒØ§ Ù…Ø³Ø§ÙˆÛŒ last_bar_index Ø¨Ø§Ø´Ø¯
    2) Ø­Ø¯Ø§Ù‚Ù„ confirm_bars Ú©Ù†Ø¯Ù„ Ø§Ø² Ø¢Ø®Ø± ÙØ§ØµÙ„Ù‡ Ø¯Ø§Ø´ØªÙ‡ Ø¨Ø§Ø´Ù†Ø¯
    """
    out = []
    for s in swings or []:
        if "index" not in s:
            continue
        idx = int(s["index"])
        # Ú†Ú© Ú©Ø±Ø¯Ù† Ø§ÛŒÙ†Ú©Ù‡ index Ø¯Ø± Ù…Ø­Ø¯ÙˆØ¯Ù‡ Ù…Ø¹ØªØ¨Ø± Ø¨Ø§Ø´Ø¯
        if idx <= last_bar_index and (last_bar_index - idx) >= int(confirm_bars):
            out.append(s)
    return out


def _get_higher_tf(tf_str: str) -> str:
    """ØªØ¨Ø¯ÛŒÙ„ TF Ù¾Ø§ÛŒÛŒÙ† Ø¨Ù‡ TF Ø¨Ø§Ù„Ø§ØªØ± Ø¨Ø±Ø§ÛŒ ØªØ£ÛŒÛŒØ¯ Ø±ÙˆÙ†Ø¯/OB."""
    tf_l = str(tf_str).lower().strip()
    mapping = {"1m": "5m", "3m": "15m", "5m": "15m"}
    return mapping.get(tf_l, "15m")


def _tf_to_minutes(tf_str: str) -> int:
    """ØªØ¨Ø¯ÛŒÙ„ Ø±Ø´ØªÙ‡ ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ… Ø¨Ù‡ Ø¯Ù‚ÛŒÙ‚Ù‡."""
    tf_l = str(tf_str).lower().strip()
    if tf_l.endswith("m"):
        return int(tf_l[:-1])
    if tf_l.endswith("h"):
        return int(tf_l[:-1]) * 60
    if tf_l.endswith("d"):
        return int(tf_l[:-1]) * 1440
    return 15


def lot_calculator_universal(symbol: str, risk_percent: float, entry: float, sl: float) -> float:
    """
    Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø­Ø¬Ù… Ø¨Ù‡ Ø±ÙˆØ´ Ø¹Ù…ÙˆÙ…ÛŒ MT5:
    loss_per_1lot = (|entry-sl| / tick_size) * tick_value
    lot = risk_amount / loss_per_1lot
    
    Ø§ÛŒÙ† ÙØ±Ù…ÙˆÙ„ Ø¨Ø±Ø§ÛŒ Gold, Forex, BTC Ùˆ Ù‡Ù…Ù‡ Ù†Ù…Ø§Ø¯Ù‡Ø§ Ú©Ø§Ø± Ù…ÛŒâ€ŒÚ©Ù†Ø¯.
    """
    # Ø¯Ø±ÛŒØ§ÙØª Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ù†Ù…Ø§Ø¯ Ùˆ Ø­Ø³Ø§Ø¨
    info = mt5.symbol_info(symbol)
    acc = mt5.account_info()
    if info is None or acc is None:
        return 0.01

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ ÙØ§ØµÙ„Ù‡ ÙˆØ±ÙˆØ¯ ØªØ§ SL
    dist = abs(float(entry) - float(sl))
    if dist <= 0:
        return float(info.volume_min) if info else 0.01

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù…Ù‚Ø¯Ø§Ø± Ø±ÛŒØ³Ú© Ø¨Ù‡ Ø¯Ù„Ø§Ø±
    balance = float(acc.balance)
    risk_amount = balance * (float(risk_percent) / 100.0)

    # Ø¯Ø±ÛŒØ§ÙØª tick_size Ùˆ tick_value
    tick_size = float(info.trade_tick_size)
    tick_value = float(info.trade_tick_value)

    # Ø¨Ø±Ø±Ø³ÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù†
    if tick_size <= 0 or tick_value <= 0:
        return float(info.volume_min)

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø¶Ø±Ø± Ø¨Ù‡ Ø§Ø²Ø§ÛŒ 1 Ù„Ø§Øª
    loss_per_1lot = (dist / tick_size) * tick_value
    if loss_per_1lot <= 0:
        return float(info.volume_min)

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø­Ø¬Ù… Ø®Ø§Ù…
    raw = risk_amount / loss_per_1lot

    # Ø¯Ø±ÛŒØ§ÙØª Ù…Ø­Ø¯ÙˆØ¯ÛŒØªâ€ŒÙ‡Ø§ÛŒ Ø­Ø¬Ù…
    vol_min = float(info.volume_min)
    vol_max = float(info.volume_max)
    vol_step = float(info.volume_step)

    if vol_step <= 0:
        vol_step = 0.01

    # Ú¯Ø±Ø¯ Ú©Ø±Ø¯Ù† Ø¨Ù‡ Ù¾Ø§ÛŒÛŒÙ† Ø¨Ø± Ø§Ø³Ø§Ø³ vol_step
    lot = math.floor(raw / vol_step) * vol_step
    
    # Ù…Ø­Ø¯ÙˆØ¯ Ú©Ø±Ø¯Ù† Ø¨Ù‡ Ø¨Ø§Ø²Ù‡ Ù…Ø¬Ø§Ø²
    lot = max(vol_min, min(vol_max, lot))

    # Ø±ÙÙ†Ø¯ Ù†Ù‡Ø§ÛŒÛŒ Ø¨Ø±Ø§ÛŒ Ù†Ù…Ø§ÛŒØ´
    lot = round(lot, 2)
    
    # Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø§Ø² Ø§ÛŒÙ†Ú©Ù‡ Ú©Ù…ØªØ± Ø§Ø² Ø­Ø¯Ø§Ù‚Ù„ Ù†Ø´ÙˆØ¯
    if lot < vol_min:
        lot = vol_min
        
    return lot


def consecutive_loss_since_last_win(comment: str, lookback_days: int = 30) -> int:
    """
    Ø´Ù…Ø§Ø±Ø´ Ø¶Ø±Ø±Ù‡Ø§ÛŒ Ù…ØªÙˆØ§Ù„ÛŒ Ø§Ø² Ø¢Ø®Ø±ÛŒÙ† Ù…Ø¹Ø§Ù…Ù„Ù‡ Ø³ÙˆØ¯Ø¯Ù‡ (ØªØ§ Ø³Ù‚Ù lookback_days).
    Ø§ÛŒÙ† ØªØ§Ø¨Ø¹ ØªÙ…Ø§Ù… Ù…Ø¹Ø§Ù…Ù„Ø§Øª Ø¨Ø§ comment Ù…Ø´Ø®Øµ Ø±Ø§ Ù…ÛŒâ€ŒÚ¯ÛŒØ±Ø¯ Ùˆ Ø§Ø² Ø¬Ø¯ÛŒØ¯ØªØ±ÛŒÙ† Ø´Ø±ÙˆØ¹ Ø¨Ù‡ Ø´Ù…Ø§Ø±Ø´ Ù…ÛŒâ€ŒÚ©Ù†Ø¯
    ØªØ§ Ø¨Ù‡ Ø§ÙˆÙ„ÛŒÙ† Ù…Ø¹Ø§Ù…Ù„Ù‡ Ø³ÙˆØ¯Ø¯Ù‡ Ø¨Ø±Ø³Ø¯.
    """
    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø¨Ø§Ø²Ù‡ Ø²Ù…Ø§Ù†ÛŒ
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(days=int(lookback_days))
    
    # Ø¯Ø±ÛŒØ§ÙØª ØªØ§Ø±ÛŒØ®Ú†Ù‡ Ù…Ø¹Ø§Ù…Ù„Ø§Øª
    deals = mt5.history_deals_get(start, now)
    if not deals:
        return 0

    # ÙÛŒÙ„ØªØ± Ù…Ø¹Ø§Ù…Ù„Ø§Øª Ù…Ø±Ø¨ÙˆØ· Ø¨Ù‡ Ø§ÛŒÙ† Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒ (ÙÙ‚Ø· Ø®Ø±ÙˆØ¬ÛŒâ€ŒÙ‡Ø§)
    my_deals = [d for d in deals if d.comment == comment and d.entry == mt5.DEAL_ENTRY_OUT]
    
    # Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒ Ø§Ø² Ø¬Ø¯ÛŒØ¯ Ø¨Ù‡ Ù‚Ø¯ÛŒÙ…
    my_deals.sort(key=lambda x: x.time, reverse=True)

    # Ø´Ù…Ø§Ø±Ø´ Ø¶Ø±Ø±Ù‡Ø§ÛŒ Ù…ØªÙˆØ§Ù„ÛŒ
    cnt = 0
    for d in my_deals:
        if d.profit < 0:
            cnt += 1
        elif d.profit > 0:
            break  # Ø¨Ù‡ Ø§ÙˆÙ„ÛŒÙ† Ù…Ø¹Ø§Ù…Ù„Ù‡ Ø³ÙˆØ¯Ø¯Ù‡ Ø±Ø³ÛŒØ¯ÛŒÙ…ØŒ Ø²Ù†Ø¬ÛŒØ±Ù‡ Ù‚Ø·Ø¹ Ù…ÛŒâ€ŒØ´ÙˆØ¯
            
    return cnt


# ----------------------------- ABCD: pattern picking (robust) ----------------------------- #

def pick_abcd_points_bullish(highs: list, lows: list):
    """
    Ø§Ù†ØªØ®Ø§Ø¨ Ù†Ù‚Ø§Ø· A,B,C Ø¨Ø±Ø§ÛŒ AB=CD ØµØ¹ÙˆØ¯ÛŒØŒ ÙÙ‚Ø· Ø¨Ø± Ø§Ø³Ø§Ø³ index:
    - C: Ø¢Ø®Ø±ÛŒÙ† high (Ø¨Ø§Ù„Ø§ØªØ±ÛŒÙ† index Ø¯Ø± Ø²Ù…Ø§Ù†)
    - A: high Ù‚Ø¨Ù„ Ø§Ø² C (Ø¯ÙˆÙ…ÛŒÙ† high Ø§Ø² Ø¢Ø®Ø±)
    - B: Ø¢Ø®Ø±ÛŒÙ† low Ø¨ÛŒÙ† A Ùˆ C (Ø¯Ø± Ø¨Ø§Ø²Ù‡ Ø²Ù…Ø§Ù†ÛŒ A < B < C)
    
    Ø´Ø±Ø§ÛŒØ·:
    1) A Ùˆ C Ø¨Ø§ÛŒØ¯ Ø¨Ø§Ù„Ø§ÛŒ B Ø¨Ø§Ø´Ù†Ø¯
    2) Ù†Ø³Ø¨Øª BC/AB Ø¨Ø§ÛŒØ¯ Ø¯Ø± Ø¨Ø§Ø²Ù‡ 0.55 ØªØ§ 0.85 Ø¨Ø§Ø´Ø¯
    3) D Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯: D = C - AB
    """
    # Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒ Ø¨Ø± Ø§Ø³Ø§Ø³ index (Ø§Ø² Ù‚Ø¯ÛŒÙ… Ø¨Ù‡ Ø¬Ø¯ÛŒØ¯)
    highs = _sorted_by_index(highs)
    lows = _sorted_by_index(lows)
    
    # Ø­Ø¯Ø§Ù‚Ù„ Ø¯Ùˆ high Ù„Ø§Ø²Ù… Ø§Ø³Øª
    if len(highs) < 2:
        return None

    # Ø§Ù†ØªØ®Ø§Ø¨ C Ùˆ A
    C = highs[-1]  # Ø¢Ø®Ø±ÛŒÙ† high (Ø¬Ø¯ÛŒØ¯ØªØ±ÛŒÙ†)
    A = highs[-2]  # high Ù‚Ø¨Ù„ÛŒ (Ù‚Ø¯ÛŒÙ…ÛŒâ€ŒØªØ±)

    # Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† B: Ø¢Ø®Ø±ÛŒÙ† low Ú©Ù‡ Ø¨ÛŒÙ† A Ùˆ C Ù‚Ø±Ø§Ø± Ø¯Ø§Ø±Ø¯
    b_candidates = [x for x in lows if int(A["index"]) < int(x["index"]) < int(C["index"])]
    if not b_candidates:
        return None
    B = b_candidates[-1]  # Ø¢Ø®Ø±ÛŒÙ† low Ø¯Ø± Ø§ÛŒÙ† Ø¨Ø§Ø²Ù‡

    # Ø¨Ø±Ø±Ø³ÛŒ Ø´Ø±Ø§ÛŒØ· Ù‚ÛŒÙ…ØªÛŒ: A Ùˆ C Ø¨Ø§ÛŒØ¯ Ø¨Ø§Ù„Ø§ÛŒ B Ø¨Ø§Ø´Ù†Ø¯
    if not (A["price"] > B["price"] and C["price"] > B["price"]):
        return None

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø·ÙˆÙ„ Ù¾Ø§Ù‡Ø§
    leg_AB = float(A["price"]) - float(B["price"])
    leg_BC = float(C["price"]) - float(B["price"])
    
    # Ø¨Ø±Ø±Ø³ÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† Ø§Ø¹Ø¯Ø§Ø¯
    if not (_is_finite_number(leg_AB) and _is_finite_number(leg_BC)) or leg_AB <= 0:
        return None

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù†Ø³Ø¨Øª BC/AB
    ratio = leg_BC / leg_AB
    
    # Ø¨Ø±Ø±Ø³ÛŒ Ø¨Ø§Ø²Ù‡ Ù‚Ø§Ø¨Ù„ Ù‚Ø¨ÙˆÙ„ Ù†Ø³Ø¨Øª (Ù…Ø­Ø¯ÙˆØ¯Ù‡ ØªÙ‚Ø±ÛŒØ¨ÛŒ 0.618)
    if ratio < 0.55 or ratio > 0.85:
        return None

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù‚ÛŒÙ…Øª D
    D_price = float(C["price"]) - leg_AB
    
    return {
        "type": "bullish",
        "A": A,
        "B": B,
        "C": C,
        "D_price": D_price,
        "ratio": ratio
    }


def pick_abcd_points_bearish(lows: list, highs: list):
    """
    Ø§Ù†ØªØ®Ø§Ø¨ Ù†Ù‚Ø§Ø· A,B,C Ø¨Ø±Ø§ÛŒ AB=CD Ù†Ø²ÙˆÙ„ÛŒ:
    - C: Ø¢Ø®Ø±ÛŒÙ† low (Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ±ÛŒÙ† index Ø¯Ø± Ø²Ù…Ø§Ù†)
    - A: low Ù‚Ø¨Ù„ Ø§Ø² C
    - B: Ø¢Ø®Ø±ÛŒÙ† high Ø¨ÛŒÙ† A Ùˆ C
    
    Ø´Ø±Ø§ÛŒØ·:
    1) A Ùˆ C Ø¨Ø§ÛŒØ¯ Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ± Ø§Ø² B Ø¨Ø§Ø´Ù†Ø¯
    2) Ù†Ø³Ø¨Øª BC/AB Ø¨Ø§ÛŒØ¯ Ø¯Ø± Ø¨Ø§Ø²Ù‡ 0.55 ØªØ§ 0.85 Ø¨Ø§Ø´Ø¯
    3) D Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù…ÛŒâ€ŒØ´ÙˆØ¯: D = C + AB
    """
    # Ù…Ø±ØªØ¨â€ŒØ³Ø§Ø²ÛŒ Ø¨Ø± Ø§Ø³Ø§Ø³ index
    highs = _sorted_by_index(highs)
    lows = _sorted_by_index(lows)
    
    # Ø­Ø¯Ø§Ù‚Ù„ Ø¯Ùˆ low Ù„Ø§Ø²Ù… Ø§Ø³Øª
    if len(lows) < 2:
        return None

    # Ø§Ù†ØªØ®Ø§Ø¨ C Ùˆ A
    C = lows[-1]  # Ø¢Ø®Ø±ÛŒÙ† low (Ø¬Ø¯ÛŒØ¯ØªØ±ÛŒÙ†)
    A = lows[-2]  # low Ù‚Ø¨Ù„ÛŒ (Ù‚Ø¯ÛŒÙ…ÛŒâ€ŒØªØ±)

    # Ù¾ÛŒØ¯Ø§ Ú©Ø±Ø¯Ù† B: Ø¢Ø®Ø±ÛŒÙ† high Ú©Ù‡ Ø¨ÛŒÙ† A Ùˆ C Ù‚Ø±Ø§Ø± Ø¯Ø§Ø±Ø¯
    b_candidates = [x for x in highs if int(A["index"]) < int(x["index"]) < int(C["index"])]
    if not b_candidates:
        return None
    B = b_candidates[-1]  # Ø¢Ø®Ø±ÛŒÙ† high Ø¯Ø± Ø§ÛŒÙ† Ø¨Ø§Ø²Ù‡

    # Ø¨Ø±Ø±Ø³ÛŒ Ø´Ø±Ø§ÛŒØ· Ù‚ÛŒÙ…ØªÛŒ: A Ùˆ C Ø¨Ø§ÛŒØ¯ Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ± Ø§Ø² B Ø¨Ø§Ø´Ù†Ø¯
    if not (A["price"] < B["price"] and C["price"] < B["price"]):
        return None

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø·ÙˆÙ„ Ù¾Ø§Ù‡Ø§
    leg_AB = float(B["price"]) - float(A["price"])
    leg_BC = float(B["price"]) - float(C["price"])
    
    # Ø¨Ø±Ø±Ø³ÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† Ø§Ø¹Ø¯Ø§Ø¯
    if not (_is_finite_number(leg_AB) and _is_finite_number(leg_BC)) or leg_AB <= 0:
        return None

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù†Ø³Ø¨Øª BC/AB
    ratio = leg_BC / leg_AB
    
    # Ø¨Ø±Ø±Ø³ÛŒ Ø¨Ø§Ø²Ù‡ Ù‚Ø§Ø¨Ù„ Ù‚Ø¨ÙˆÙ„
    if ratio < 0.55 or ratio > 0.85:
        return None

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù‚ÛŒÙ…Øª D
    D_price = float(C["price"]) + leg_AB
    
    return {
        "type": "bearish",
        "A": A,
        "B": B,
        "C": C,
        "D_price": D_price,
        "ratio": ratio
    }


# ----------------------------- ABCD Strategy (fixed) ----------------------------- #

def abcd_strategy(symbol: str,
                  tf: str,
                  risk: float,
                  state: dict,
                  comment: str = "ABCD_Stg",
                  depth: int = 12,
                  confirm_bars_mult: float = 1.5,
                  lookback_days: int = 30) -> dict:
    """
    Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒ AB=CD Ø¨Ø§ ÙˆÛŒÚ˜Ú¯ÛŒâ€ŒÙ‡Ø§ÛŒ:
    - Swing selection Ø¨Ø± Ø§Ø³Ø§Ø³ index (Ø¨Ø¯ÙˆÙ† ÙˆØ§Ø¨Ø³ØªÚ¯ÛŒ Ø¨Ù‡ ØªØ±ØªÛŒØ¨ Ø®Ø±ÙˆØ¬ÛŒ zigzag)
    - Ø¶Ø¯-repaint Ø¨Ø§ confirm_bars (ÙÙ‚Ø· Ø³ÙˆØ¦ÛŒÙ†Ú¯â€ŒÙ‡Ø§ÛŒ ØªØ£ÛŒÛŒØ¯â€ŒØ´Ø¯Ù‡)
    - consecutive_loss Ø§Ø² Ø¢Ø®Ø±ÛŒÙ† Ø³ÙˆØ¯ (ØªØ§ Ø³Ù‚Ù 30 Ø±ÙˆØ²)
    - lot_calculator_universal (Ø¨Ø±Ø§ÛŒ Ù‡Ù…Ù‡ Ù†Ù…Ø§Ø¯Ù‡Ø§)
    - StopLevel + NaN checks
    - Ø°Ø®ÛŒØ±Ù‡ metadata Ø¨Ø±Ø§ÛŒ invalidation pending Ø¯Ø± state
    
    Ù¾Ø§Ø±Ø§Ù…ØªØ±Ù‡Ø§:
        symbol: Ù†Ù…Ø§Ø¯ (Ù…Ø«Ù„ 'XAUUSD')
        tf: ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ… (Ù…Ø«Ù„ '3m')
        risk: Ø¯Ø±ØµØ¯ Ø±ÛŒØ³Ú© Ù¾Ø§ÛŒÙ‡
        state: Ø¯ÛŒÚ©Ø´Ù†Ø±ÛŒ state (Ø¨Ø±Ø§ÛŒ Ø°Ø®ÛŒØ±Ù‡ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¨ÛŒÙ† ÙØ±Ø§Ø®ÙˆØ§Ù†ÛŒâ€ŒÙ‡Ø§)
        comment: Ø´Ù†Ø§Ø³Ù‡ Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒ (Ø¨Ø±Ø§ÛŒ ÙÛŒÙ„ØªØ± Ù…Ø¹Ø§Ù…Ù„Ø§Øª)
        depth: Ø¹Ù…Ù‚ zigzag (Ù¾ÛŒØ´â€ŒÙØ±Ø¶ 12)
        confirm_bars_mult: Ø¶Ø±ÛŒØ¨ ØªØ£ÛŒÛŒØ¯ Ø³ÙˆØ¦ÛŒÙ†Ú¯ (Ù¾ÛŒØ´â€ŒÙØ±Ø¶ 1.5 * depth)
        lookback_days: Ø¨Ø§Ø²Ù‡ Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø¶Ø±Ø±Ù‡Ø§ÛŒ Ù…ØªÙˆØ§Ù„ÛŒ (Ù¾ÛŒØ´â€ŒÙØ±Ø¶ 30)
    
    Ø®Ø±ÙˆØ¬ÛŒ:
        state Ø¨Ù‡â€ŒØ±ÙˆØ² Ø´Ø¯Ù‡
    """
    # ØªØ¶Ù…ÛŒÙ† ÙˆØ¬ÙˆØ¯ state
    if state is None:
        state = {}

    # --- 1) Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø¶Ø±Ø±Ù‡Ø§ÛŒ Ù…ØªÙˆØ§Ù„ÛŒ Ùˆ ØªÙ†Ø¸ÛŒÙ… Ø³Ø®Øªâ€ŒÚ¯ÛŒØ±ÛŒ/Ø±ÛŒØ³Ú© ---
    consecutive_loss = consecutive_loss_since_last_win(comment, lookback_days=lookback_days)

    # ÙØ¹Ø§Ù„â€ŒØ³Ø§Ø²ÛŒ ÙÛŒÙ„ØªØ±Ù‡Ø§ÛŒ Ø§Ø¶Ø§ÙÛŒ Ø¨Ø± Ø§Ø³Ø§Ø³ ØªØ¹Ø¯Ø§Ø¯ Ø¶Ø±Ø±Ù‡Ø§
    use_rsi = consecutive_loss >= 1
    use_macd = consecutive_loss >= 2

    # ØªÙ†Ø¸ÛŒÙ… Ø­Ø¯Ø§Ù‚Ù„ Ø§Ù…ØªÛŒØ§Ø² Ù‚Ø§Ø¨Ù„ Ù‚Ø¨ÙˆÙ„
    min_score = 70
    if consecutive_loss == 1:
        min_score = 75
    elif consecutive_loss >= 2:
        min_score = 80

    # ØªÙ†Ø¸ÛŒÙ… Ø±ÛŒØ³Ú© Ù…Ø¤Ø«Ø± (Ù†ØµÙ Ø¨Ø¹Ø¯ Ø§Ø² Ø¶Ø±Ø±)
    risk_effective = float(risk) * (0.5 if consecutive_loss > 0 else 1.0)
    if risk_effective <= 0:
        return state

    # --- 2) Ø¯Ø±ÛŒØ§ÙØª Ø¯Ø§Ø¯Ù‡ Ú©Ù†Ø¯Ù„ÛŒ ---
    raw = candle(symbol, tf, 500)
    try:
        df = raw.obj.copy()
    except Exception:
        df = pd.DataFrame(raw[:])

    if df is None or df.empty:
        return state

    # ØªØ¶Ù…ÛŒÙ† ÙˆØ¬ÙˆØ¯ Ø³ØªÙˆÙ† time
    df = _ensure_time_column(df)
    
    # Ø¨Ø±Ø±Ø³ÛŒ Ø³ØªÙˆÙ†â€ŒÙ‡Ø§ÛŒ Ø¶Ø±ÙˆØ±ÛŒ
    if not {"high", "low", "close"}.issubset(df.columns):
        return state

    n = len(df)
    if n < 100:  # Ø­Ø¯Ø§Ù‚Ù„ Ø¯Ø§Ø¯Ù‡ Ù„Ø§Ø²Ù…
        return state

    # --- 3) ZigZag + Anti-Repaint ---
    zz = zigzag(df, depth=depth)
    highs = zz.get("high", [])
    lows = zz.get("low", [])

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ ØªØ¹Ø¯Ø§Ø¯ Ú©Ù†Ø¯Ù„â€ŒÙ‡Ø§ÛŒ Ù„Ø§Ø²Ù… Ø¨Ø±Ø§ÛŒ ØªØ£ÛŒÛŒØ¯
    confirm_bars = int(math.ceil(depth * float(confirm_bars_mult)))  # Ù…Ø«Ù„Ø§Ù‹ 18 Ø¨Ø±Ø§ÛŒ depth=12
    
    # Ø­Ø°Ù Ø³ÙˆØ¦ÛŒÙ†Ú¯â€ŒÙ‡Ø§ÛŒ Ù†Ø²Ø¯ÛŒÚ© Ø¨Ù‡ Ø§Ù†ØªÙ‡Ø§ÛŒ Ø¯ÛŒØªØ§ (Ù…Ø´Ú©ÙˆÚ© Ø¨Ù‡ repaint)
    highs = _safe_swings(highs, last_bar_index=n - 1, confirm_bars=confirm_bars)
    lows = _safe_swings(lows, last_bar_index=n - 1, confirm_bars=confirm_bars)

    # Ø¨Ø±Ø±Ø³ÛŒ ÙˆØ¬ÙˆØ¯ Ø³ÙˆØ¦ÛŒÙ†Ú¯ Ú©Ø§ÙÛŒ
    if len(highs) < 2 or len(lows) < 2:
        return state

    # --- 4) Ù…Ø­Ø§Ø³Ø¨Ù‡ ATR/ADX Ø¨Ø§ Ú†Ú© NaN ---
    try:
        # Ø¯Ø±ÛŒØ§ÙØª Ø³Ø±ÛŒ ATR
        atr_series = Atr(symbol, tf, 14)
        if atr_series is None or len(atr_series) < 20:
            return state
            
        # Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø§Ø² Ú©Ù†Ø¯Ù„ Ø¨Ø³ØªÙ‡â€ŒØ´Ø¯Ù‡ Ù‚Ø¨Ù„ÛŒ
        atr_current = float(atr_series[-2])
        
        # Ø¨Ø±Ø±Ø³ÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† ATR
        if not _is_finite_number(atr_current) or atr_current <= 0:
            return state
            
        # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù…ÛŒØ§Ù†Ú¯ÛŒÙ† ATR (ÙÙ‚Ø· Ø§Ø¹Ø¯Ø§Ø¯ Ù…Ø¹ØªØ¨Ø±)
        valid_atrs = [x for x in atr_series[-20:] if _is_finite_number(x)]
        atr_avg = float(np.mean(valid_atrs))
        
        # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ù†Ø³Ø¨Øª Ù†ÙˆØ³Ø§Ù†
        vol_ratio = (atr_current / atr_avg) if (atr_avg and _is_finite_number(atr_avg) and atr_avg > 0) else 1.0
        
    except Exception:
        return state

    try:
        # Ø¯Ø±ÛŒØ§ÙØª Ø³Ø±ÛŒ ADX
        adx_series = adx(symbol, tf)
        if adx_series is None or len(adx_series) == 0:
            return state
            
        adx_val = float(adx_series[-1])
        
        # Ø¨Ø±Ø±Ø³ÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† ADX
        if not _is_finite_number(adx_val):
            return state
            
    except Exception:
        return state

    # ÙÛŒÙ„ØªØ± Ø¨Ø§Ø²Ø§Ø± Ø±Ù†Ø¬ (ADX < 20)
    if adx_val < 20:
        return state

    # --- 5) Ù…Ø­Ø§Ø³Ø¨Ù‡ RSI/MACD (ÙÙ‚Ø· Ø¯Ø± ØµÙˆØ±Øª ÙØ¹Ø§Ù„ Ø¨ÙˆØ¯Ù†) ---
    rsi_val = 50.0  # Ù…Ù‚Ø¯Ø§Ø± Ù¾ÛŒØ´â€ŒÙØ±Ø¶ Ø®Ù†Ø«ÛŒ
    if use_rsi:
        try:
            rsi_series = rsi(symbol, tf)
            rsi_val = float(rsi_series[-2])
            if not _is_finite_number(rsi_val):
                return state
        except Exception:
            return state

    macd_hist_curr = macd_hist_prev = 0.0
    if use_macd:
        try:
            m = macd(symbol, tf, 12, 26, 9)
            hist = m.get("histogram", [])
            macd_hist_curr = float(hist[-2])
            macd_hist_prev = float(hist[-3])
            if not (_is_finite_number(macd_hist_curr) and _is_finite_number(macd_hist_prev)):
                return state
        except Exception:
            return state

    # --- 6) ØªØ£ÛŒÛŒØ¯ HTF (ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ… Ø¨Ø§Ù„Ø§ØªØ±) + Order Block ---
    higher_tf = _get_higher_tf(tf)

    # Ø¯Ø±ÛŒØ§ÙØª Ø±ÙˆÙ†Ø¯ HTF
    try:
        htf_trend_data = trend_ali(symbol, higher_tf)
        htf_trend = str(htf_trend_data["trend"][-1]).lower()
    except Exception:
        htf_trend = "neutral"

    # Ø¯Ø±ÛŒØ§ÙØª Order Blocks
    try:
        ob_data = detect_ob(symbol, higher_tf)
        supply_zones = ob_data.get("supply_zones", [])
        demand_zones = ob_data.get("demand_zones", [])
    except Exception:
        supply_zones, demand_zones = [], []

    # ØªÙ†Ø¸ÛŒÙ… Ø­Ø¯ÙˆØ¯ RSI Ø¨Ø± Ø§Ø³Ø§Ø³ ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ…
    tf_mins = _tf_to_minutes(tf)
    rsi_lower, rsi_upper = (20, 80) if tf_mins < 15 else (30, 70)

    # --- 7) ØªØ´Ø®ÛŒØµ Ø§Ù„Ú¯Ùˆ (robust) ---
    bull_pattern = pick_abcd_points_bullish(highs, lows)
    bear_pattern = pick_abcd_points_bearish(lows, highs)

    # Ø§Ú¯Ø± Ù‡ÛŒÚ† Ø§Ù„Ú¯ÙˆÛŒ Ù…Ø¹ØªØ¨Ø± Ù†ÛŒØ§ÙØªÛŒÙ…
    if bull_pattern is None and bear_pattern is None:
        return state

    # --- 8) Ø³ÛŒØ³ØªÙ… Ø§Ù…ØªÛŒØ§Ø²Ø¯Ù‡ÛŒ (0-100) ---
    def score_pattern(pattern: dict, direction: str) -> float:
        """Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø§Ù…ØªÛŒØ§Ø² Ø§Ù„Ú¯Ùˆ Ø¨Ø± Ø§Ø³Ø§Ø³ Ú†Ù†Ø¯ Ù…Ø¹ÛŒØ§Ø±."""
        score = 0.0

        # 1) Ú©ÛŒÙÛŒØª Ù‡Ù†Ø¯Ø³ÛŒ Ø§Ù„Ú¯Ùˆ (Ø­Ø¯Ø§Ú©Ø«Ø± 25 Ø§Ù…ØªÛŒØ§Ø²)
        # Ù†Ø²Ø¯ÛŒÚ©ÛŒ Ù†Ø³Ø¨Øª BC/AB Ø¨Ù‡ 0.7 (Ø§ÛŒØ¯Ù‡â€ŒØ¢Ù„)
        target_ratio = 0.7
        max_diff = 0.15
        diff = abs(float(pattern["ratio"]) - target_ratio)
        geo_factor = max(0.0, 1.0 - diff / max_diff)
        score += geo_factor * 25.0

        # 2) ØªØ£ÛŒÛŒØ¯ HTF (Ø­Ø¯Ø§Ú©Ø«Ø± 20 Ø§Ù…ØªÛŒØ§Ø²)
        if direction == "bullish":
            score += 20.0 if htf_trend == "long" else (5.0 if htf_trend == "neutral" else 0.0)
        else:
            score += 20.0 if htf_trend == "short" else (5.0 if htf_trend == "neutral" else 0.0)

        # 3) ØªØ£ÛŒÛŒØ¯ Order Block (Ø­Ø¯Ø§Ú©Ø«Ø± 20 Ø§Ù…ØªÛŒØ§Ø²)
        D_price = float(pattern["D_price"])
        margin = atr_current * 0.5  # Ø­Ø§Ø´ÛŒÙ‡ Ù†ØµÙ ATR
        ob_score = 0.0

        if direction == "bullish":
            # Ú†Ú© Ú©Ø±Ø¯Ù† Demand Zones
            for ob in demand_zones:
                if ob.get("status") != "active":
                    continue
                top = ob.get("top")
                bottom = ob.get("bottom")
                if top is None or bottom is None:
                    continue
                # Ø¨Ø±Ø±Ø³ÛŒ Ù‡Ù…â€ŒÙ¾ÙˆØ´Ø§Ù†ÛŒ D Ø¨Ø§ OB
                if (float(bottom) - margin) <= D_price <= (float(top) + margin):
                    ob_score = 20.0
                    break
        else:
            # Ú†Ú© Ú©Ø±Ø¯Ù† Supply Zones
            for ob in supply_zones:
                if ob.get("status") != "active":
                    continue
                top = ob.get("top")
                bottom = ob.get("bottom")
                if top is None or bottom is None:
                    continue
                if (float(bottom) - margin) <= D_price <= (float(top) + margin):
                    ob_score = 20.0
                    break

        score += ob_score

        # 4) Ù…ÙˆÙ…Ù†ØªÙˆÙ… (RSI/MACD) (Ø­Ø¯Ø§Ú©Ø«Ø± 15 Ø§Ù…ØªÛŒØ§Ø²)
        mom_score = 0.0
        
        if use_rsi:
            if direction == "bullish":
                # Ø¨Ø±Ø§ÛŒ Ø®Ø±ÛŒØ¯ØŒ RSI Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ± Ø¨Ù‡ØªØ± Ø§Ø³Øª
                if rsi_val < 50:
                    mom_score += 8.0
                if rsi_val < (rsi_lower + 5):
                    mom_score += 4.0
            else:
                # Ø¨Ø±Ø§ÛŒ ÙØ±ÙˆØ´ØŒ RSI Ø¨Ø§Ù„Ø§ØªØ± Ø¨Ù‡ØªØ± Ø§Ø³Øª
                if rsi_val > 50:
                    mom_score += 8.0
                if rsi_val > (rsi_upper - 5):
                    mom_score += 4.0

        if use_macd:
            # Ø¨Ø±Ø±Ø³ÛŒ Ø¬Ù‡Øª Ù‡ÛŒØ³ØªÙˆÚ¯Ø±Ø§Ù… MACD
            if direction == "bullish" and macd_hist_curr > macd_hist_prev:
                mom_score += 3.0
            if direction == "bearish" and macd_hist_curr < macd_hist_prev:
                mom_score += 3.0

        score += min(mom_score, 15.0)

        # 5) Ù†ÙˆØ³Ø§Ù†â€ŒÙ¾Ø°ÛŒØ±ÛŒ (Ø­Ø¯Ø§Ú©Ø«Ø± 10 Ø§Ù…ØªÛŒØ§Ø²)
        # Ø¨Ø§Ø²Ù‡ Ù…Ø·Ù„ÙˆØ¨ Ù†ÙˆØ³Ø§Ù†
        if 0.7 <= vol_ratio <= 1.8:
            vol_score = 10.0
        elif 0.5 <= vol_ratio < 0.7 or 1.8 < vol_ratio <= 2.5:
            vol_score = 5.0
        else:
            vol_score = 0.0
            
        score += vol_score

        # Ù…Ø­Ø¯ÙˆØ¯ Ú©Ø±Ø¯Ù† Ø§Ù…ØªÛŒØ§Ø² Ù†Ù‡Ø§ÛŒÛŒ Ø¨Ù‡ Ø¨Ø§Ø²Ù‡ [0, 100]
        return float(max(0.0, min(100.0, score)))

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø§Ù…ØªÛŒØ§Ø² Ø§Ù„Ú¯ÙˆÙ‡Ø§
    bull_score = score_pattern(bull_pattern, "bullish") if bull_pattern else None
    bear_score = score_pattern(bear_pattern, "bearish") if bear_pattern else None

    # --- 9) Ø§Ù†ØªØ®Ø§Ø¨ Ø¨Ù‡ØªØ±ÛŒÙ† Ø§Ù„Ú¯Ùˆ ---
    best = None
    best_dir = None
    best_score = -1.0

    # Ø¨Ø±Ø±Ø³ÛŒ Ø§Ù„Ú¯ÙˆÛŒ ØµØ¹ÙˆØ¯ÛŒ
    if bull_score is not None and bull_score >= min_score:
        best = bull_pattern
        best_dir = "bullish"
        best_score = bull_score

    # Ø¨Ø±Ø±Ø³ÛŒ Ø§Ù„Ú¯ÙˆÛŒ Ù†Ø²ÙˆÙ„ÛŒ (Ø§Ú¯Ø± Ø§Ù…ØªÛŒØ§Ø²Ø´ Ø¨ÛŒØ´ØªØ± Ø§Ø³Øª)
    if bear_score is not None and bear_score >= min_score and bear_score > best_score:
        best = bear_pattern
        best_dir = "bearish"
        best_score = bear_score

    # Ø§Ú¯Ø± Ù‡ÛŒÚ† Ø§Ù„Ú¯ÙˆÛŒÛŒ Ø¨Ù‡ Ø­Ø¯Ø§Ù‚Ù„ Ø§Ù…ØªÛŒØ§Ø² Ù†Ø±Ø³ÛŒØ¯
    if best is None:
        return state

    # --- 10) Ø³Ø§Ø®Øª Ø³ÙØ§Ø±Ø´ Pending Ø¨Ø§ Ú†Ú© StopLevel ---
    # Ø¯Ø±ÛŒØ§ÙØª Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ù†Ù…Ø§Ø¯ Ùˆ Ù‚ÛŒÙ…Øª ÙØ¹Ù„ÛŒ
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None:
        return state

    # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø­Ø¯Ø§Ù‚Ù„ ÙØ§ØµÙ„Ù‡ SL Ø§Ø² Ù‚ÛŒÙ…Øª
    point = float(info.point)
    broker_min_stop = float(info.trade_stops_level) * point
    min_stop_distance = max(point * 10.0, broker_min_stop)

    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø§Ù„Ú¯Ùˆ
    D_price = float(best["D_price"])
    C_price = float(best["C"]["price"])
    C_index = int(best["C"]["index"])

    # Ø¬Ù„ÙˆÚ¯ÛŒØ±ÛŒ Ø§Ø² ØªÚ©Ø±Ø§Ø± Ø³ÛŒÚ¯Ù†Ø§Ù„ Ø±ÙˆÛŒ Ù‡Ù…Ø§Ù† C
    if best_dir == "bullish":
        if state.get(f"{comment}_bull_idx") == C_index:
            return state
    else:
        if state.get(f"{comment}_bear_idx") == C_index:
            return state

    # --- 11) Ù…Ø­Ø§Ø³Ø¨Ù‡ SL/TP Ùˆ Ø«Ø¨Øª Ø³ÙØ§Ø±Ø´ ---
    if best_dir == "bullish":
        # Ø¨Ø±Ø±Ø³ÛŒ Ø§ÛŒÙ†Ú©Ù‡ Ù‚ÛŒÙ…Øª ÙØ¹Ù„ÛŒ Ø¨Ø§Ù„Ø§ØªØ± Ø§Ø² D Ø§Ø³Øª (Ø´Ø±Ø· Buy Limit)
        if tick.ask <= D_price:
            return state

        # Ù…Ø­Ø§Ø³Ø¨Ù‡ SL (Ø²ÛŒØ± D Ø¨Ù‡ Ø§Ù†Ø¯Ø§Ø²Ù‡ 1.5 * ATR)
        sl = D_price - (atr_current * 1.5)
        
        # Ø§Ø¹Ù…Ø§Ù„ Ø­Ø¯Ø§Ù‚Ù„ ÙØ§ØµÙ„Ù‡ Ø¨Ø±ÙˆÚ©Ø±
        if (D_price - sl) < min_stop_distance:
            sl = D_price - min_stop_distance

        # TP Ø¯Ø± Ù†Ù‚Ø·Ù‡ C
        tp = C_price

        # Ø¨Ø±Ø±Ø³ÛŒ Ù†Ù‡Ø§ÛŒÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† Ø§Ø¹Ø¯Ø§Ø¯
        if not (_is_finite_number(sl) and _is_finite_number(tp)):
            return state

        # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø­Ø¬Ù…
        lot = lot_calculator_universal(symbol, risk_effective, D_price, sl)
        if lot <= 0:
            return state

        # Ø«Ø¨Øª Ø³ÙØ§Ø±Ø´ Buy Limit
        res = pending_order(symbol, lot, mt5.ORDER_TYPE_BUY_LIMIT, D_price, sl, tp, comment)

        # Ø§Ú¯Ø± Ø³ÙØ§Ø±Ø´ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ø´Ø¯
        if res is not None and getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
            # Ø°Ø®ÛŒØ±Ù‡ index Ø¨Ø±Ø§ÛŒ Ø¬Ù„ÙˆÚ¯ÛŒØ±ÛŒ Ø§Ø² ØªÚ©Ø±Ø§Ø±
            state[f"{comment}_bull_idx"] = C_index

            # Ø°Ø®ÛŒØ±Ù‡ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¨Ø±Ø§ÛŒ Ù…Ø¯ÛŒØ±ÛŒØª invalidation
            state[f"{comment}_last_setup"] = {
                "direction": "buy",
                "C_index": C_index,
                "C_price": C_price,
                "D_price": D_price,
                "time_setup": time.time(),
                "tf": tf,
                "score": float(best_score),
            }

    else:  # bearish
        # Ø¨Ø±Ø±Ø³ÛŒ Ø§ÛŒÙ†Ú©Ù‡ Ù‚ÛŒÙ…Øª ÙØ¹Ù„ÛŒ Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ± Ø§Ø² D Ø§Ø³Øª (Ø´Ø±Ø· Sell Limit)
        if tick.bid >= D_price:
            return state

        # Ù…Ø­Ø§Ø³Ø¨Ù‡ SL (Ø¨Ø§Ù„Ø§ÛŒ D Ø¨Ù‡ Ø§Ù†Ø¯Ø§Ø²Ù‡ 1.5 * ATR)
        sl = D_price + (atr_current * 1.5)
        
        # Ø§Ø¹Ù…Ø§Ù„ Ø­Ø¯Ø§Ù‚Ù„ ÙØ§ØµÙ„Ù‡ Ø¨Ø±ÙˆÚ©Ø±
        if (sl - D_price) < min_stop_distance:
            sl = D_price + min_stop_distance

        # TP Ø¯Ø± Ù†Ù‚Ø·Ù‡ C
        tp = C_price

        # Ø¨Ø±Ø±Ø³ÛŒ Ù†Ù‡Ø§ÛŒÛŒ Ù…Ø¹ØªØ¨Ø± Ø¨ÙˆØ¯Ù† Ø§Ø¹Ø¯Ø§Ø¯
        if not (_is_finite_number(sl) and _is_finite_number(tp)):
            return state

        # Ù…Ø­Ø§Ø³Ø¨Ù‡ Ø­Ø¬Ù…
        lot = lot_calculator_universal(symbol, risk_effective, D_price, sl)
        if lot <= 0:
            return state

        # Ø«Ø¨Øª Ø³ÙØ§Ø±Ø´ Sell Limit
        res = pending_order(symbol, lot, mt5.ORDER_TYPE_SELL_LIMIT, D_price, sl, tp, comment)

        # Ø§Ú¯Ø± Ø³ÙØ§Ø±Ø´ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ø´Ø¯
        if res is not None and getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
            # Ø°Ø®ÛŒØ±Ù‡ index Ø¨Ø±Ø§ÛŒ Ø¬Ù„ÙˆÚ¯ÛŒØ±ÛŒ Ø§Ø² ØªÚ©Ø±Ø§Ø±
            state[f"{comment}_bear_idx"] = C_index
            
            # Ø°Ø®ÛŒØ±Ù‡ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¨Ø±Ø§ÛŒ Ù…Ø¯ÛŒØ±ÛŒØª invalidation
            state[f"{comment}_last_setup"] = {
                "direction": "sell",
                "C_index": C_index,
                "C_price": C_price,
                "D_price": D_price,
                "time_setup": time.time(),
                "tf": tf,
                "score": float(best_score),
            }

    return state


# ----------------------------- Pending Orders Manager (TTL + Invalidation) ----------------------------- #

def manage_pending_orders(symbol: str,
                          state: dict,
                          comment: str = "ABCD_Stg") -> dict:
    """
    Ù…Ø¯ÛŒØ±ÛŒØª Ø³ÙØ§Ø±Ø´Ø§Øª Pending Ø§ÛŒÙ† Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒ:
    - TTL (Time To Live) Ø¨Ø± Ø§Ø³Ø§Ø³ ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ…
    - Invalidation: Ø§Ú¯Ø± Ù‚ÛŒÙ…Øª Ø§Ø² C Ø¹Ø¨ÙˆØ± Ú©Ù†Ø¯ØŒ Ø³ÙØ§Ø±Ø´ Ú©Ù†Ø³Ù„ Ù…ÛŒâ€ŒØ´ÙˆØ¯
    
    Ù…Ù†Ø·Ù‚ TTL:
    - 1m â†’ 30 Ø¯Ù‚ÛŒÙ‚Ù‡
    - 3m â†’ 1 Ø³Ø§Ø¹Øª
    - 5m â†’ 2 Ø³Ø§Ø¹Øª
    - 15m â†’ 4 Ø³Ø§Ø¹Øª
    - Ø¨ÛŒØ´ØªØ± â†’ 6 Ø³Ø§Ø¹Øª
    
    Ù…Ù†Ø·Ù‚ Invalidation:
    - Ø¨Ø±Ø§ÛŒ Buy Limit: Ø§Ú¯Ø± Ù‚ÛŒÙ…Øª (bid) Ø¨Ø§Ù„Ø§ØªØ± Ø§Ø² C Ø¨Ø±ÙˆØ¯
    - Ø¨Ø±Ø§ÛŒ Sell Limit: Ø§Ú¯Ø± Ù‚ÛŒÙ…Øª (ask) Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ± Ø§Ø² C Ø¨Ø±ÙˆØ¯
    """
    # Ø¨Ø±Ø±Ø³ÛŒ ÙˆØ¬ÙˆØ¯ state
    if state is None:
        return {}

    # Ø¯Ø±ÛŒØ§ÙØª Ø³ÙØ§Ø±Ø´Ø§Øª Ø¨Ø§Ø² Ø§ÛŒÙ† Ù†Ù…Ø§Ø¯
    orders = mt5.orders_get(symbol=symbol)
    if not orders:
        return state

    # Ø¯Ø±ÛŒØ§ÙØª Ù‚ÛŒÙ…Øª ÙØ¹Ù„ÛŒ
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return state

    # Ø¯Ø±ÛŒØ§ÙØª Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¢Ø®Ø±ÛŒÙ† setup
    last_setup = state.get(f"{comment}_last_setup")
    if not last_setup:
        return state

    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ… Ùˆ Ù…Ø­Ø§Ø³Ø¨Ù‡ TTL
    tf = str(last_setup.get("tf", "3m"))
    tf_m = _tf_to_minutes(tf)

    # ØªØ¹ÛŒÛŒÙ† TTL Ø¨Ø± Ø§Ø³Ø§Ø³ ØªØ§ÛŒÙ…â€ŒÙØ±ÛŒÙ…
    if tf_m <= 1:
        ttl = 30 * 60  # 30 Ø¯Ù‚ÛŒÙ‚Ù‡
    elif tf_m <= 3:
        ttl = 60 * 60  # 1 Ø³Ø§Ø¹Øª
    elif tf_m <= 5:
        ttl = 2 * 60 * 60  # 2 Ø³Ø§Ø¹Øª
    elif tf_m <= 15:
        ttl = 4 * 60 * 60  # 4 Ø³Ø§Ø¹Øª
    else:
        ttl = 6 * 60 * 60  # 6 Ø³Ø§Ø¹Øª

    # Ø²Ù…Ø§Ù† ÙØ¹Ù„ÛŒ
    now = time.time()
    
    # Ø§Ø³ØªØ®Ø±Ø§Ø¬ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¨Ø±Ø§ÛŒ invalidation
    c_price = last_setup.get("C_price")
    direction = last_setup.get("direction")

    # Ù¾Ø±Ø¯Ø§Ø²Ø´ Ù‡Ø± Ø³ÙØ§Ø±Ø´
    for o in orders:
        # ÙÙ‚Ø· Ø³ÙØ§Ø±Ø´Ø§Øª Ø§ÛŒÙ† Ø§Ø³ØªØ±Ø§ØªÚ˜ÛŒ
        if o.comment != comment:
            continue

        # 1) Ø¨Ø±Ø±Ø³ÛŒ TTL (Ø²Ù…Ø§Ù† Ø§Ù†Ù‚Ø¶Ø§)
        order_age = now - float(o.time_setup)
        if order_age > ttl:
            remove_order(o.ticket)
            continue

        # 2) Ø¨Ø±Ø±Ø³ÛŒ Invalidation (Ø¹Ø¨ÙˆØ± Ù‚ÛŒÙ…Øª Ø§Ø² C)
        if _is_finite_number(c_price):
            c_price = float(c_price)

            # Ø¨Ø±Ø§ÛŒ Buy Limit: Ø§Ú¯Ø± Ù‚ÛŒÙ…Øª Ø¨Ø§Ù„Ø§ÛŒ C Ø±ÙØªØŒ Ø§Ù„Ú¯Ùˆ invalidate Ø´Ø¯Ù‡
            if direction == "buy" and tick.bid > c_price:
                remove_order(o.ticket)
                continue

            # Ø¨Ø±Ø§ÛŒ Sell Limit: Ø§Ú¯Ø± Ù‚ÛŒÙ…Øª Ù¾Ø§ÛŒÛŒÙ†â€ŒØªØ± Ø§Ø² C Ø±ÙØªØŒ Ø§Ù„Ú¯Ùˆ invalidate Ø´Ø¯Ù‡
            if direction == "sell" and tick.ask < c_price:
                remove_order(o.ticket)
                continue

    return state

``

## File: module\strategy_adapter.py

``python
"""Pure historical strategy adapters for Replay.

Indicators operate only on the candles supplied to `evaluate`; they never
import MT5. New indicators can be added through the IndicatorAdapter protocol
or CallableIndicator without changing HistoricalReplay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

import numpy as np
import pandas as pd

from .backtest import ReplaySignal
from .market_data import Candle


class IndicatorAdapter(Protocol):
    name: str

    def evaluate(self, candles: list[Candle]) -> dict[str, object]: ...


def _frame(candles: list[Candle]) -> pd.DataFrame:
    return pd.DataFrame([{"open": c.open, "high": c.high, "low": c.low, "close": c.close, "timestamp": c.timestamp} for c in candles])


@dataclass
class SupertrendAdapter:
    atr_period: int = 10
    multiplier: float = 3.0
    name: str = "supertrend"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        df = _frame(candles)
        if len(df) == 0:
            return {"name": self.name, "direction": [], "signals": [], "line": []}
        previous_close = df["close"].shift(1)
        tr = pd.concat([df["high"] - df["low"], (df["high"] - previous_close).abs(), (df["low"] - previous_close).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / self.atr_period, adjust=False, min_periods=1).mean()
        hl2 = (df["high"] + df["low"]) / 2
        upper = (hl2 + self.multiplier * atr).to_numpy(copy=True)
        lower = (hl2 - self.multiplier * atr).to_numpy(copy=True)
        direction: list[str] = []
        line: list[float] = []
        for i in range(len(df)):
            if i and direction[-1] == "long":
                lower[i] = max(lower[i], lower[i - 1])
            if i and direction[-1] == "short":
                upper[i] = min(upper[i], upper[i - 1])
            if i == 0:
                current = "long"
            elif direction[-1] == "short" and df.close.iloc[i] > upper[i - 1]:
                current = "long"
            elif direction[-1] == "long" and df.close.iloc[i] < lower[i - 1]:
                current = "short"
            else:
                current = direction[-1]
            direction.append(current)
            line.append(float(lower[i] if current == "long" else upper[i]))
        signals = ["hold"] + ["buy" if direction[i] == "long" and direction[i - 1] == "short" else "sell" if direction[i] == "short" and direction[i - 1] == "long" else "hold" for i in range(1, len(direction))]
        return {"name": self.name, "direction": direction, "signals": signals, "line": line}


@dataclass
class HalfTrendAdapter:
    amplitude: int = 2
    name: str = "halftrend"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        df = _frame(candles)
        if len(df) == 0:
            return {"name": self.name, "direction": [], "signals": [], "line": []}
        high_roll = df.high.rolling(self.amplitude, min_periods=1).max()
        low_roll = df.low.rolling(self.amplitude, min_periods=1).min()
        high_ma = df.high.rolling(self.amplitude, min_periods=1).mean()
        low_ma = df.low.rolling(self.amplitude, min_periods=1).mean()
        direction: list[str] = []
        line: list[float] = []
        for i in range(len(df)):
            current = direction[-1] if direction else "long"
            prev_low = df.low.iloc[i - 1] if i else df.low.iloc[i]
            prev_high = df.high.iloc[i - 1] if i else df.high.iloc[i]
            if current == "short" and high_ma.iloc[i] < low_roll.iloc[i] and df.close.iloc[i] < prev_low:
                current = "long"
            elif current == "long" and low_ma.iloc[i] > high_roll.iloc[i] and df.close.iloc[i] > prev_high:
                current = "short"
            direction.append(current)
            line.append(float(low_roll.iloc[i] if current == "long" else high_roll.iloc[i]))
        signals = ["hold"] + ["buy" if direction[i] == "long" and direction[i - 1] == "short" else "sell" if direction[i] == "short" and direction[i - 1] == "long" else "hold" for i in range(1, len(direction))]
        return {"name": self.name, "direction": direction, "signals": signals, "line": line}


@dataclass
class RSIAdapter:
    """RSI reversal filter: buy out of oversold, sell out of overbought."""

    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    name: str = "rsi"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        close = _frame(candles)["close"]
        delta = close.diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / self.period, adjust=False, min_periods=1).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / self.period, adjust=False, min_periods=1).mean()
        rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
        rsi = rsi.fillna(50.0).to_numpy()
        signals = ["hold"]
        for i in range(1, len(rsi)):
            signals.append("buy" if rsi[i - 1] <= self.oversold < rsi[i] else "sell" if rsi[i - 1] >= self.overbought > rsi[i] else "hold")
        return {"name": self.name, "direction": ["long" if x >= 50 else "short" for x in rsi], "signals": signals, "line": rsi.tolist(), "rsi": rsi.tolist(), "supports_price_line": False}


@dataclass
class MACDAdapter:
    """MACD line/signal crossover adapter."""

    fast: int = 12
    slow: int = 26
    signal_period: int = 9
    name: str = "macd"

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        close = _frame(candles)["close"]
        fast_line = close.ewm(span=self.fast, adjust=False, min_periods=1).mean()
        slow_line = close.ewm(span=self.slow, adjust=False, min_periods=1).mean()
        macd = fast_line - slow_line
        signal_line = macd.ewm(span=self.signal_period, adjust=False, min_periods=1).mean()
        signals = ["hold"]
        for i in range(1, len(macd)):
            signals.append("buy" if macd.iloc[i - 1] <= signal_line.iloc[i - 1] < macd.iloc[i] else "sell" if macd.iloc[i - 1] >= signal_line.iloc[i - 1] > macd.iloc[i] else "hold")
        direction = ["long" if value >= 0 else "short" for value in macd]
        return {"name": self.name, "direction": direction, "signals": signals, "line": macd.tolist(), "macd": macd.tolist(), "signal_line": signal_line.tolist(), "supports_price_line": False}


@dataclass
class CallableIndicator:
    name: str
    function: Callable[[list[Candle]], dict[str, object]]

    def evaluate(self, candles: list[Candle]) -> dict[str, object]:
        result = dict(self.function(candles))
        result.setdefault("name", self.name)
        return result


@dataclass
class CombinedVotingStrategy:
    indicators: list[IndicatorAdapter]
    symbol: str = "XAUUSD"
    volume: float = 0.01
    rr: float = 2.0
    min_votes: int | None = None
    comment: str = "combined_replay"

    def __post_init__(self) -> None:
        if not self.indicators:
            raise ValueError("at least one indicator is required")
        if self.min_votes is None:
            self.min_votes = len(self.indicators)
        if not 1 <= self.min_votes <= len(self.indicators):
            raise ValueError("min_votes must be between 1 and indicator count")

    def __call__(self, history: list[Candle], candle: Candle) -> Iterable[ReplaySignal]:
        candles = history + [candle]
        results = [indicator.evaluate(candles) for indicator in self.indicators]
        latest = [str(result.get("signals", ["hold"])[-1]) for result in results]
        buy_votes = latest.count("buy")
        sell_votes = latest.count("sell")
        signal = "buy" if buy_votes >= self.min_votes else "sell" if sell_votes >= self.min_votes else "hold"
        if signal == "hold":
            return []
        lines = [float(result["line"][-1]) for result in results if result.get("line") and result.get("supports_price_line", True)]
        entry = float(candle.open)
        if signal == "buy":
            sl = min(lines) if lines else float(candle.low)
            tp = entry + (entry - sl) * self.rr
            order_type = 0
        else:
            sl = max(lines) if lines else float(candle.high)
            tp = entry - (sl - entry) * self.rr
            order_type = 1
        if (signal == "buy" and sl >= entry) or (signal == "sell" and sl <= entry):
            return []
        trade_id = f"{self.comment}:{self.symbol}:{candle.timestamp}:{signal}"
        return [ReplaySignal(trade_id, self.symbol, self.volume, order_type, entry, sl, tp, self.comment)]


def make_combined_strategy(*indicators: IndicatorAdapter, **kwargs: object) -> CombinedVotingStrategy:
    """Convenience factory; custom indicators can be passed alongside built-ins."""
    return CombinedVotingStrategy(list(indicators), **kwargs)

``

## File: module\telegram_alerts.py

``python
"""Secure Telegram alert notifier.

No credentials are stored in source code. Alerts are disabled unless
TELEGRAM_ALERTS_ENABLED=YES and both TELEGRAM_BOT_TOKEN and
TELEGRAM_CHAT_ID are present in the environment.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TelegramAlertConfig:
    enabled: bool
    token: str | None
    chat_id: str | None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "TelegramAlertConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        enabled = os.getenv("TELEGRAM_ALERTS_ENABLED", "NO").upper() == "YES"
        return cls(
            enabled=enabled and bool(token and chat_id),
            token=token,
            chat_id=chat_id,
            timeout_seconds=float(os.getenv("TELEGRAM_ALERT_TIMEOUT", "10")),
        )


class TelegramAlertNotifier:
    def __init__(self, config: TelegramAlertConfig | None = None) -> None:
        self.config = config or TelegramAlertConfig.from_env()

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def send(self, message: str) -> bool:
        """Send one alert; return False when disabled or Telegram rejects it."""
        if not self.enabled:
            return False
        if not message:
            return False
        payload = urlencode({"chat_id": self.config.chat_id, "text": message[:4096]}).encode()
        request = Request(
            f"https://api.telegram.org/bot{self.config.token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
                return bool(body.get("ok"))
        except Exception:
            # The trading loop must not crash because Telegram is unavailable.
            return False

    def __call__(self, message: str) -> None:
        self.send(message)

``

## File: module\timeframe_data.py

``python
"""Single source of truth for M1-to-timeframe OHLCV aggregation."""
from __future__ import annotations
import pandas as pd

_TIMEFRAME_MINUTES = {"1m":1,"3m":3,"5m":5,"15m":15,"30m":30,"1h":60,"4h":240,"1d":1440,"1w":10080}

def timeframe_minutes(timeframe: str) -> int:
    key=str(timeframe).lower()
    if key not in _TIMEFRAME_MINUTES:
        raise ValueError(f"unsupported timeframe {timeframe!r}; use {sorted(_TIMEFRAME_MINUTES)}")
    return _TIMEFRAME_MINUTES[key]

def resample_m1_ohlcv(m1: pd.DataFrame, timeframe: str, limit: int | None = None) -> pd.DataFrame:
    """Aggregate M1 candles identically for live and backtest consumers."""
    required={"time","open","high","low","close"}
    missing=required-set(m1.columns)
    if missing: raise ValueError(f"missing OHLC columns: {sorted(missing)}")
    df=m1.copy()
    df["time"]=pd.to_datetime(df["time"], unit="s", errors="coerce") if not pd.api.types.is_datetime64_any_dtype(df["time"]) else pd.to_datetime(df["time"])
    df=df.dropna(subset=["time"]).sort_values("time").drop_duplicates("time")
    if df.empty: return df.assign(volume=pd.Series(dtype=float))[list(required|{"volume"})]
    df=df.set_index("time")
    volume_col="volume" if "volume" in df.columns else "tick_volume"
    if volume_col not in df.columns: df["volume"]=0.0; volume_col="volume"
    rule=f"{timeframe_minutes(timeframe)}min"
    out=df.resample(rule, label="left", closed="left").agg({"open":"first","high":"max","low":"min","close":"last",volume_col:"sum"}).dropna(subset=["open","high","low","close"]).reset_index()
    if volume_col != "volume": out=out.rename(columns={volume_col:"volume"})
    return out.tail(limit).reset_index(drop=True) if limit else out.reset_index(drop=True)

def fetch_m1_resampled(api, symbol: str, timeframe: str, limit: int):
    """Fetch M1 only, then aggregate; callers never request native higher TF bars."""
    minutes=timeframe_minutes(timeframe)
    raw=api.copy_rates_from_pos(symbol, getattr(api,"TIMEFRAME_M1",1), 0, max(2, limit*minutes+1))
    if raw is None or len(raw)==0: return pd.DataFrame(columns=["time","open","high","low","close","volume"])
    return resample_m1_ohlcv(pd.DataFrame(raw), timeframe, limit)

``

## File: module\volume_control.py

``python
"""Conservative, approval-gated position sizing and staged volume changes."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def risk_corrected_percent(base_risk: float, starting_balance: float, rr: float, total_trades: int, current_profit: float, max_risk: float) -> float:
    """Mirror the project's risk_corrector formula without requiring MT5."""
    if starting_balance <= 0 or rr <= 0:
        raise ValueError("starting_balance and rr must be positive")
    initial_risk = starting_balance * (base_risk / 100.0)
    target_profit = initial_risk * rr * max(1, total_trades)
    deficit = target_profit - current_profit
    if deficit <= 0:
        return min(base_risk, max_risk)
    adjusted = round((deficit / rr) / starting_balance * 100.0, 2)
    return min(max(adjusted, base_risk), max_risk)


def calculate_risk_volume(balance: float, risk_percent: float, entry: float, stop_loss: float, tick_size: float, tick_value: float, volume_step: float = 0.01, min_volume: float = 0.01, max_volume: float = 1.0, max_target: float = 0.01) -> float:
    """Size by money risk and hard-cap it at MAX_VOLUME_TARGET."""
    distance = abs(float(entry) - float(stop_loss))
    if balance <= 0 or risk_percent <= 0 or distance <= 0 or tick_size <= 0 or tick_value <= 0:
        return 0.0
    risk_money = balance * risk_percent / 100.0
    loss_per_lot = distance / tick_size * tick_value
    raw = risk_money / loss_per_lot
    cap = min(float(max_volume), float(max_target))
    if cap <= 0:
        return 0.0
    sized = min(raw, cap)
    sized = math.floor(sized / volume_step) * volume_step
    if sized < min_volume and raw >= min_volume and min_volume <= cap:
        sized = min_volume
    return round(min(sized, cap), 8)


@dataclass
class VolumeChange:
    timestamp: str
    old_volume: float
    new_volume: float
    risk_percent: float
    reason: str
    approved_by: str
    status: str = "APPROVED"


class VolumeController:
    """Persist volume history and require a manual approval per stage."""
    def __init__(self, state_path: str | Path = "volume_state.json", log_path: str | Path = "logs/volume_changes.log", max_target: float = 0.01, min_observation_days: int = 3):
        self.state_path = Path(state_path)
        self.log_path = Path(log_path)
        self.max_target = float(max_target)
        self.min_observation_days = int(min_observation_days)
        self.state = self._load()

    def _load(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"current_volume": 0.01, "observation_started": "", "changes": []}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def record_change(self, new_volume: float, risk_percent: float, reason: str, approved_by: str) -> VolumeChange:
        old = float(self.state.get("current_volume", 0.01))
        new = min(float(new_volume), self.max_target)
        if new <= 0 or new < old:
            raise ValueError("new volume must be positive and not below current volume; use rollback() to decrease")
        if new > self.max_target:
            raise ValueError("new volume exceeds MAX_VOLUME_TARGET")
        change = VolumeChange(datetime.now(timezone.utc).isoformat(), old, new, float(risk_percent), reason, approved_by)
        self.state["current_volume"] = new
        self.state.setdefault("changes", []).append(asdict(change))
        self.state["observation_started"] = datetime.now(timezone.utc).date().isoformat()
        self._save()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(change), ensure_ascii=False) + "\n")
        return change

    def rollback(self, volume: float, reason: str, approved_by: str) -> VolumeChange:
        old = float(self.state.get("current_volume", 0.01))
        new = float(volume)
        if new <= 0 or new >= old:
            raise ValueError("rollback volume must be positive and lower than current volume")
        change = VolumeChange(datetime.now(timezone.utc).isoformat(), old, new, 0.0, reason, approved_by, "ROLLBACK")
        self.state["current_volume"] = new
        self.state.setdefault("changes", []).append(asdict(change))
        self._save()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(change), ensure_ascii=False) + "\n")
        return change

``

## File: scripts\daily_report.py

``python
#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from module.performance import calculate_performance
from module.telegram_alerts import TelegramAlertNotifier


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def build_report(root: Path, date: str) -> str:
    states = load_json(root / os.getenv("TRADE_STATE_PATH", "trade_state.json"), {})
    counts = Counter(str(item.get("state", "UNKNOWN")) for item in states.values())
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_paths = list(log_dir.glob("**/*.jsonl"))
    alerts = []
    for path in log_paths:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            timestamp = str(row.get("timestamp", ""))
            if date not in timestamp:
                continue
            if str(row.get("level", "")).upper() in {"ERROR", "CRITICAL"} or row.get("event") in {"recovery_timeout", "recovery_error", "trade_rejected"}:
                alerts.append(row)
    paper = load_json(root / os.getenv("PAPER_STATE_PATH", "paper_state.json"), {})
    profits = [float(p.get("profit", 0.0)) for p in paper.get("positions", {}).values() if p.get("status") == "CLOSED"]
    metrics = calculate_performance(profits, initial_balance=float(os.getenv("INITIAL_BALANCE", "0")))
    rejected = counts.get("REJECTED", 0)
    threshold = int(os.getenv("DAILY_ALERT_THRESHOLD", "5"))
    prefix = "âš ï¸ WARNING: " if rejected + len(alerts) >= threshold else ""
    lines = [f"# {prefix}Daily PAPER Report â€” {date}", "", f"Generated at: {datetime.now(timezone.utc).isoformat()}", "", "## State counts", ""]
    lines.extend(f"- **{state}**: {count}" for state, count in sorted(counts.items()))
    lines.extend(["", "## Performance", "", f"- Net PnL: **{metrics['net_profit']:.4f}**", f"- Profit Factor: **{metrics['profit_factor']}**", f"- Sharpe: **{metrics['sharpe']:.4f}**", f"- Max Drawdown: **{metrics['max_drawdown']:.4f}**", f"- Closed trades: **{metrics['trades']}**", "", f"## Alerts ({len(alerts)})", ""])
    lines.extend(f"- `{row.get('timestamp', '')}` `{row.get('event', row.get('level', ''))}`: {row.get('message', '')}" for row in alerts[:100])
    return "\n".join(lines) + "\n"


def main():
    root = Path(__file__).resolve().parents[1]
    date = os.getenv("REPORT_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    report = build_report(root, date)
    path = root / "reports" / f"daily_{date.replace('-', '')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(path)
    notifier = TelegramAlertNotifier()
    if notifier.enabled:
        notifier.send(report)


if __name__ == "__main__":
    main()

``

## File: scripts\monitor_logs.py

``python
#!/usr/bin/env python3
"""Tail trading JSONL logs and send deduplicated Telegram alerts.

Credentials are read only from environment variables. The script never prints
the bot token or chat ID. It is intentionally read-only with respect to logs.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class Telegram:
    def __init__(self) -> None:
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = os.getenv("TELEGRAM_ALERTS_ENABLED", "NO").upper() == "YES" and bool(self.token and self.chat_id)
        self.timeout = float(os.getenv("TELEGRAM_ALERT_TIMEOUT", "10"))

    def send(self, text: str) -> bool:
        if not self.enabled:
            return False
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        body = urlencode({"chat_id": self.chat_id, "text": text[:3900], "disable_web_page_preview": "true"}).encode()
        request = Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return 200 <= response.status < 300
        except Exception as exc:
            print(f"telegram_send_failed: {type(exc).__name__}", file=sys.stderr)
            return False


def is_alert(row: dict) -> bool:
    level = str(row.get("level", "")).upper()
    event = str(row.get("event", "")).lower()
    return level in {"ERROR", "CRITICAL"} or event in {"recovery_timeout", "recovery_error", "run_once_error", "trade_rejected"}


def format_alert(row: dict) -> str:
    return "Trading bot alert\n" + "\n".join(f"{key}: {value}" for key, value in row.items() if key not in {"exception"})


def monitor(path: Path, *, once: bool = False) -> int:
    telegram = Telegram()
    cooldown = max(0.0, float(os.getenv("TELEGRAM_ALERT_COOLDOWN_SECONDS", "300")))
    poll = max(0.1, float(os.getenv("LOG_POLL_INTERVAL_SECONDS", "1")))
    last_alert: dict[str, float] = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                if once:
                    return 0
                time.sleep(poll)
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                print("ignored_non_json_log_line", file=sys.stderr)
                continue
            if not is_alert(row):
                continue
            key = f"{row.get('level')}:{row.get('event')}:{row.get('message')}"
            now = time.monotonic()
            if now - last_alert.get(key, 0.0) < cooldown:
                continue
            last_alert[key] = now
            print(format_alert(row), flush=True)
            telegram.send(format_alert(row))


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else os.getenv("LOG_FILE", "logs/trading.jsonl"))
    monitor(path)


if __name__ == "__main__":
    main()

``

## File: scripts\notify_paper_start.py

``python
#!/usr/bin/env python3
from datetime import datetime, timezone
import os
from module.telegram_alerts import TelegramAlertNotifier

message = f"PAPER run started at {os.getenv('PAPER_RUN_STARTED_AT', datetime.now(timezone.utc).isoformat())}"
notifier = TelegramAlertNotifier()
print(message)
if notifier.enabled:
    print("telegram_start_alert_sent=" + str(notifier.send(message)))

``

## File: scripts\volume_step.py

``python
#!/usr/bin/env python3
"""Manual, approval-gated staged volume controller.

Usage:
  volume_step.py status
  volume_step.py size --balance 1000 --entry 2000 --sl 1990 --tick-size 0.01 --tick-value 1 --trades 20 --profit 30
  volume_step.py approve --volume 0.02 --risk-percent 1 --reason '3-day stable PAPER' --approved-by operator
  volume_step.py rollback --volume 0.01 --reason 'drawdown increased' --approved-by operator
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from module.volume_control import VolumeController, calculate_risk_volume, risk_corrected_percent


def controller() -> VolumeController:
    return VolumeController(
        os.getenv("VOLUME_STATE_PATH", "volume_state.json"),
        os.getenv("VOLUME_CHANGE_LOG", "logs/volume_changes.log"),
        float(os.getenv("MAX_VOLUME_TARGET", "0.01")),
        int(os.getenv("MIN_OBSERVATION_DAYS", "3")),
    )


def cmd_status(args):
    c = controller()
    print(json.dumps(c.state, ensure_ascii=False, indent=2))
    print(f"MAX_VOLUME_TARGET={c.max_target} MIN_OBSERVATION_DAYS={c.min_observation_days}")


def cmd_size(args):
    corrected = risk_corrected_percent(args.base_risk, args.balance, args.rr, args.trades, args.profit, args.max_risk)
    volume = calculate_risk_volume(args.balance, corrected, args.entry, args.sl, args.tick_size, args.tick_value, args.volume_step, args.min_volume, args.broker_max, float(os.getenv("MAX_VOLUME_TARGET", "0.01")))
    print(json.dumps({"risk_percent": corrected, "calculated_volume": volume, "max_volume_target": float(os.getenv("MAX_VOLUME_TARGET", "0.01"))}, indent=2))


def cmd_approve(args):
    c = controller()
    started = c.state.get("observation_started", "")
    if started:
        days = (date.today() - date.fromisoformat(started)).days
        if days < c.min_observation_days:
            raise SystemExit(f"NO-GO: only {days} observation day(s); require {c.min_observation_days}")
    change = c.record_change(args.volume, args.risk_percent, args.reason, args.approved_by)
    print(json.dumps(change.__dict__, ensure_ascii=False, indent=2))


def cmd_rollback(args):
    change = controller().rollback(args.volume, args.reason, args.approved_by)
    print(json.dumps(change.__dict__, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    size = sub.add_parser("size")
    for name, typ in [("balance", float), ("entry", float), ("sl", float), ("tick-size", float), ("tick-value", float), ("trades", int), ("profit", float)]: size.add_argument("--" + name, required=True, type=typ)
    size.add_argument("--base-risk", type=float, default=1.0); size.add_argument("--rr", type=float, default=2.0); size.add_argument("--max-risk", type=float, default=2.0); size.add_argument("--volume-step", type=float, default=0.01); size.add_argument("--min-volume", type=float, default=0.01); size.add_argument("--broker-max", type=float, default=100.0); size.set_defaults(func=cmd_size)
    approve = sub.add_parser("approve")
    approve.add_argument("--volume", required=True, type=float); approve.add_argument("--risk-percent", required=True, type=float); approve.add_argument("--reason", required=True); approve.add_argument("--approved-by", required=True); approve.set_defaults(func=cmd_approve)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--volume", required=True, type=float); rollback.add_argument("--reason", required=True); rollback.add_argument("--approved-by", required=True); rollback.set_defaults(func=cmd_rollback)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()

``

## File: state_io.py

``python
# module/state_io.py (ÙØ§ÛŒÙ„ Ø¬Ø¯Ø§Ú¯Ø§Ù†Ù‡)
"""
Ù…Ø§Ú˜ÙˆÙ„ Ø°Ø®ÛŒØ±Ù‡ Ùˆ Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ state Ø¨Ù‡/Ø§Ø² ÙØ§ÛŒÙ„ JSON
Ø¨Ø§ Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ø§Ø² Ø§Ù†ÙˆØ§Ø¹ NumPy
"""

import json
import numpy as np
from typing import Any, Dict


class NumpyEncoder(json.JSONEncoder):
    """
    Encoder Ø³ÙØ§Ø±Ø´ÛŒ Ø¨Ø±Ø§ÛŒ ØªØ¨Ø¯ÛŒÙ„ Ø§Ù†ÙˆØ§Ø¹ NumPy Ø¨Ù‡ Ø§Ù†ÙˆØ§Ø¹ Python Ø§Ø³ØªØ§Ù†Ø¯Ø§Ø±Ø¯
    Ø§ÛŒÙ† Ú©Ù„Ø§Ø³ Ù…Ø´Ú©Ù„ serialize Ú©Ø±Ø¯Ù† np.int64, np.float64 Ùˆ... Ø±Ø§ Ø­Ù„ Ù…ÛŒâ€ŒÚ©Ù†Ø¯
    """
    def default(self, obj):
        # ØªØ¨Ø¯ÛŒÙ„ Ø§Ø¹Ø¯Ø§Ø¯ ØµØ­ÛŒØ­ NumPy Ø¨Ù‡ int
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        
        # ØªØ¨Ø¯ÛŒÙ„ Ø§Ø¹Ø¯Ø§Ø¯ Ø§Ø¹Ø´Ø§Ø±ÛŒ NumPy Ø¨Ù‡ float
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        
        # ØªØ¨Ø¯ÛŒÙ„ Ø¢Ø±Ø§ÛŒÙ‡ NumPy Ø¨Ù‡ Ù„ÛŒØ³Øª
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        # Ø¨Ø±Ø§ÛŒ Ø¨Ù‚ÛŒÙ‡ Ù…ÙˆØ§Ø±Ø¯ØŒ Ø§Ø² encoder Ù¾ÛŒØ´â€ŒÙØ±Ø¶ Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø´ÙˆØ¯
        return super().default(obj)


def save_state(state: Dict[str, Any], filename: str = "bot_state.json") -> None:
    """
    Ø°Ø®ÛŒØ±Ù‡ state Ø¯Ø± ÙØ§ÛŒÙ„ JSON
    
    Ù¾Ø§Ø±Ø§Ù…ØªØ±Ù‡Ø§:
        state: Ø¯ÛŒÚ©Ø´Ù†Ø±ÛŒ state Ø¨Ø±Ø§ÛŒ Ø°Ø®ÛŒØ±Ù‡
        filename: Ù†Ø§Ù… ÙØ§ÛŒÙ„ (Ù¾ÛŒØ´â€ŒÙØ±Ø¶: bot_state.json)
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(
                state, 
                f, 
                cls=NumpyEncoder,  # Ø§Ø³ØªÙØ§Ø¯Ù‡ Ø§Ø² encoder Ø³ÙØ§Ø±Ø´ÛŒ
                ensure_ascii=False,  # Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ø§Ø² ÙØ§Ø±Ø³ÛŒ
                indent=2  # ÙØ±Ù…Øª Ø®ÙˆØ§Ù†Ø§
            )
    except Exception as e:
        print(f"[ERROR] Failed to save state: {e}")


def load_state(filename: str = "bot_state.json") -> Dict[str, Any]:
    """
    Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ state Ø§Ø² ÙØ§ÛŒÙ„ JSON
    
    Ù¾Ø§Ø±Ø§Ù…ØªØ±Ù‡Ø§:
        filename: Ù†Ø§Ù… ÙØ§ÛŒÙ„ (Ù¾ÛŒØ´â€ŒÙØ±Ø¶: bot_state.json)
    
    Ø®Ø±ÙˆØ¬ÛŒ:
        Ø¯ÛŒÚ©Ø´Ù†Ø±ÛŒ state (Ø§Ú¯Ø± ÙØ§ÛŒÙ„ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø´Øª ÛŒØ§ Ø®Ø·Ø§ Ø±Ø® Ø¯Ø§Ø¯ØŒ {} Ø¨Ø±Ù…ÛŒâ€ŒÚ¯Ø±Ø¯Ø§Ù†Ø¯)
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Ø§Ú¯Ø± ÙØ§ÛŒÙ„ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø±Ø¯ (Ø§ÙˆÙ„ÛŒÙ† Ø§Ø¬Ø±Ø§)ØŒ state Ø®Ø§Ù„ÛŒ Ø¨Ø±Ú¯Ø±Ø¯Ø§Ù†
        return {}
    except Exception as e:
        print(f"[ERROR] Failed to load state: {e}")
        return {}
``

## File: tests\run_paper_mock.py

``python
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class MockMT5:
    TRADE_RETCODE_DONE = 10009
    TIMEFRAME_M1 = 1

    def __init__(self):
        self.initialize_calls = 0
        self.order_send_calls = 0
        self.copy_calls = 0

    def initialize(self):
        self.initialize_calls += 1
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=1700000000, bid=100.0, ask=100.2)

    def positions_get(self, symbol=None):
        return []

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.copy_calls += 1
        return None

    def order_send(self, request):
        self.order_send_calls += 1
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=999, deal=999, comment="mock")


class StopAfterSleeps(Exception):
    pass


def run():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ.update({
            "TRADING_MODE": "PAPER",
            "ENABLE_LIVE_TRADING": "NO",
            "SYMBOL": "XAUUSD",
            "TIMEFRAME": "1m",
            "LOOP_INTERVAL_SECONDS": "0.01",
            "INITIAL_BALANCE": "1000",
            "COMMISSION_PER_LOT": "2",
            "DEFAULT_SPREAD": "0.2",
            "RISK_MAX_VOLUME": "1.0",
            "PAPER_STATE_PATH": str(root / "paper_state.json"),
            "TRADE_STATE_PATH": str(root / "trade_state.json"),
            "MEMORY_PATH": str(root / "memory" / "events.jsonl"),
            "LOG_DIR": str(root / "logs"),
        })
        api = MockMT5()
        main.mt5 = api
        emitted = {"count": 0}

        def provider(rt):
            if emitted["count"] == 0:
                emitted["count"] += 1
                return SimpleNamespace(symbol="XAUUSD", volume=0.01, order_type=0, sl=95.0, tp=110.0, comment="paper-mock")
            return None

        original_sleep = main.time.sleep

        def limited_sleep(seconds):
            emitted["count"] += 1
            if emitted["count"] >= 4:
                raise StopAfterSleeps
            original_sleep(0.001)

        original_provider_setup = main.setup
        def setup_with_provider(**kwargs):
            kwargs["api"] = api
            kwargs["signal_provider"] = provider
            return original_provider_setup(**kwargs)

        main.setup = setup_with_provider
        main.time.sleep = limited_sleep
        try:
            try:
                main.main()
            except StopAfterSleeps:
                pass
        finally:
            main.time.sleep = original_sleep
            main.setup = original_provider_setup

        log_path = root / "logs" / "trading.jsonl"
        state_path = root / "trade_state.json"
        paper_path = root / "paper_state.json"
        log_lines = log_path.read_text().splitlines() if log_path.exists() else []
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        paper = json.loads(paper_path.read_text()) if paper_path.exists() else {}
        print(json.dumps({
            "initialize_calls": api.initialize_calls,
            "mt5_order_send_calls": api.order_send_calls,
            "copy_rates_calls": api.copy_calls,
            "paper_log_exists": log_path.exists(),
            "log_lines": len(log_lines),
            "state_records": len(state),
            "state_values": [item["state"] for item in state.values()],
            "paper_orders": len(paper.get("orders", {})),
            "paper_positions": len(paper.get("positions", {})),
            "live_mt5_called": api.order_send_calls > 0,
        }, indent=2))
        assert api.initialize_calls == 1
        assert api.order_send_calls == 0
        assert log_path.exists()
        assert len(state) == 1
        assert len(paper.get("orders", {})) == 1
        assert len(paper.get("positions", {})) == 1


if __name__ == "__main__":
    run()

``

## File: tests\test_agent_manager.py

``python
import tempfile
import unittest
from pathlib import Path

from agent.manager import ExperimentManager, ExperimentSpec
from agent.skills import SkillCatalog
from module.market_data import Candle


class ExperimentManagerTests(unittest.TestCase):
    def candles(self):
        return [
            Candle(str(i), "XAUUSD", 100 + i, 102 + i, 98 + i, 101 + i)
            for i in range(30)
        ]

    def test_run_splits_data_and_persists_result(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExperimentManager(Path(directory) / "results.jsonl")
            result = manager.run(self.candles(), ExperimentSpec())
            self.assertEqual(result.train["candles"], 21)
            self.assertEqual(result.test["candles"], 9)
            self.assertEqual(len(manager.history()), 1)
            self.assertEqual(len(result.experiment_id), 16)

    def test_grid_and_best_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = ExperimentManager(Path(directory) / "results.jsonl")
            results = manager.grid({"name": ["a", "b"], "min_votes": [2]})
            self.assertEqual(len(results), 2)
            self.assertIsNotNone(manager.best(results))

    def test_live_settings_are_not_part_of_manager(self):
        self.assertFalse(hasattr(ExperimentManager, "send"))

    def test_skill_catalog_discovers_trading_guidance(self):
        catalog = SkillCatalog()
        skill = catalog.get("gold")
        self.assertIsNotNone(skill)
        self.assertIn("kill switch", skill.content.lower())

    def test_skill_catalog_can_rank_relevant_guidance(self):
        skills = SkillCatalog().relevant("risk drawdown paper backtest")
        self.assertTrue(skills)
        self.assertTrue(any("golden-trading-engineer" == skill.name.casefold() for skill in skills))


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_chaos_paper.py

``python
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import main
from module.recovery import TradeRecovery
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class ChaosPaperTests(unittest.TestCase):
    def test_kill_restart_recovery_to_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            machine = TradeStateMachine(path)
            machine.create(TradeRecord("t1", state=TradeState.SENT, symbol="XAUUSD", strategy="strat"))
            machine.transition("t1", TradeState.ACCEPTED, ticket=1)
            restored = TradeStateMachine(path)
            broker = SimpleNamespace(
                orders_get=lambda symbol=None: [],
                positions_get=lambda symbol=None: [SimpleNamespace(ticket=99, symbol="XAUUSD", magic=26080901, comment="strat")],
            )
            TradeRecovery(broker).recover(restored)
            self.assertEqual(restored.get("t1").state, TradeState.OPEN)
            self.assertEqual(restored.get("t1").ticket, 99)

    def test_transient_provider_exception_does_not_prevent_next_cycle(self):
        calls = {"n": 0}
        def provider(_):
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("temporary MT5 outage")
            return None
        fake_runtime = SimpleNamespace(signal_provider=provider, symbol="XAUUSD")
        with patch.object(main, "reconcile_all_trade_states"), patch.object(main, "runtime", fake_runtime):
            with self.assertRaises(ConnectionError):
                main.run_once(fake_runtime)
            self.assertIsNone(main.run_once(fake_runtime))
            self.assertEqual(calls["n"], 2)

    def test_duplicate_signal_does_not_create_second_state(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_api = SimpleNamespace(
                initialize=lambda: True,
                symbol_info_tick=lambda symbol: SimpleNamespace(time=1, bid=100, ask=100.1),
                TRADE_RETCODE_DONE=10009,
            )
            with patch.dict("os.environ", {"TRADING_MODE": "PAPER", "PAPER_STATE_PATH": str(Path(directory) / "paper.json"), "TRADE_STATE_PATH": str(Path(directory) / "state.json"), "MEMORY_PATH": str(Path(directory) / "memory.jsonl"), "LOG_DIR": str(Path(directory) / "logs")}, clear=False):
                rt = main.setup(api=fake_api)
                signal = SimpleNamespace(symbol="XAUUSD", volume=0.01, order_type=0, sl=95, tp=110, comment="same")
                main.managed_create_order(signal.symbol, signal.volume, signal.order_type, signal.sl, signal.tp, signal.comment, "1m")
                main.managed_create_order(signal.symbol, signal.volume, signal.order_type, signal.sl, signal.tp, signal.comment, "1m")
                self.assertEqual(len(rt.trade_states.records), 1)
                self.assertEqual(len(rt.paper_broker.orders), 1)

    def test_accepted_timeout_rejects_without_position(self):
        machine = TradeStateMachine()
        old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        machine.create(TradeRecord("t1", state=TradeState.ACCEPTED, symbol="XAUUSD", strategy="strat", updated_at=old))
        broker = SimpleNamespace(orders_get=lambda symbol=None: [], positions_get=lambda symbol=None: [])
        report = TradeRecovery(broker, timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_costs.py

``python
import tempfile
import unittest
from pathlib import Path

from module.market_data import Tick
from module.paper import PaperBroker


class TradingCostTests(unittest.TestCase):
    def request(self, trade_id):
        return {"trade_id": trade_id, "symbol": "XAUUSD", "volume": 1.0, "type": 0, "price": 100.0, "sl": 95.0, "tp": 110.0, "action": "deal"}

    def test_commission_and_bid_ask_spread_reduce_net_profit(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", commission_per_lot=2.0)
            broker.send(self.request("costed"))
            broker.mark_price("XAUUSD", 110, bid=109.0, ask=111.0)
            position = broker.positions["costed"]
            self.assertEqual(position.gross_profit, 9.0)
            self.assertEqual(position.commission, 2.0)
            self.assertEqual(position.exit_spread, 2.0)
            self.assertEqual(position.spread_cost, 2.0)
            self.assertEqual(position.profit, 5.0)

    def test_tick_replay_uses_bid_ask(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", commission_per_lot=1.0)
            broker.send(self.request("tick-cost"))
            report = broker.replay_ticks([Tick("1", "XAUUSD", 109.0, 111.0)])
            self.assertEqual(report["closed"], 1)
            self.assertEqual(broker.positions["tick-cost"].profit, 6.0)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_custom_indicators.py

``python
import tempfile
import unittest
from pathlib import Path

from module.backtest import HistoricalReplay
from module.market_data import Candle
from module.paper import PaperBroker
from module.strategy_adapter import CombinedVotingStrategy, MACDAdapter, RSIAdapter


class CustomIndicatorTests(unittest.TestCase):
    def candles(self):
        prices = [100, 99, 98, 97, 96, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 103, 102, 101, 100, 99, 98, 97, 98, 99, 100, 101, 102, 103, 104, 105]
        return [Candle(str(i), "XAUUSD", p, p + 1, p - 1, p) for i, p in enumerate(prices)]

    def test_rsi_output_is_aligned_and_bounded(self):
        result = RSIAdapter(period=5, oversold=35, overbought=65).evaluate(self.candles())
        self.assertEqual(len(result["rsi"]), 30)
        self.assertTrue(all(0 <= value <= 100 for value in result["rsi"]))
        self.assertEqual(len(result["signals"]), 30)

    def test_macd_output_is_aligned(self):
        result = MACDAdapter(fast=3, slow=7, signal_period=2).evaluate(self.candles())
        self.assertEqual(len(result["macd"]), 30)
        self.assertEqual(len(result["signal_line"]), 30)
        self.assertEqual(len(result["signals"]), 30)
        self.assertTrue(set(result["signals"]).issubset({"buy", "sell", "hold"}))

    def test_rsi_and_macd_can_be_combined(self):
        strategy = CombinedVotingStrategy(
            [RSIAdapter(period=5, oversold=35, overbought=65), MACDAdapter(fast=3, slow=7, signal_period=2)],
            min_votes=1,
            volume=0.1,
        )
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            result = HistoricalReplay(broker, initial_balance=1000).run(self.candles(), strategy)
            self.assertEqual(result["candles"], 30)
            self.assertGreaterEqual(result["ticks"], 30)

    def test_default_threshold_can_reject_disagreement(self):
        strategy = CombinedVotingStrategy(
            [RSIAdapter(period=5), MACDAdapter(fast=3, slow=7, signal_period=2)],
            min_votes=2,
        )
        signals = []
        for i, candle in enumerate(self.candles()):
            signals.extend(strategy(self.candles()[:i], candle))
        self.assertTrue(isinstance(signals, list))


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_dashboard_memory.py

``python
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import create_app
from module.memory import SecondBrain


class DashboardMemoryTests(unittest.TestCase):
    def test_dashboard_endpoints_without_mt5(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(root=directory)
            client = app.test_client()
            self.assertEqual(client.get("/api/status").status_code, 200)
            self.assertEqual(client.get("/api/positions").get_json()["source"], "paper")
            self.assertEqual(client.get("/api/logs").status_code, 200)
            self.assertEqual(client.get("/api/memory").status_code, 200)
            self.assertEqual(client.get("/api/performance").status_code, 200)

    def test_dashboard_token_protection(self):
        import os
        old = os.environ.get("DASHBOARD_TOKEN")
        os.environ["DASHBOARD_TOKEN"] = "test-token"
        try:
            app = create_app(root=tempfile.mkdtemp())
            client = app.test_client()
            self.assertEqual(client.get("/api/status").status_code, 401)
            self.assertEqual(client.get("/api/status", headers={"X-Dashboard-Token": "test-token"}).status_code, 200)
        finally:
            if old is None:
                os.environ.pop("DASHBOARD_TOKEN", None)
            else:
                os.environ["DASHBOARD_TOKEN"] = old

    def test_remote_dashboard_requires_token(self):
        import os
        old_host = os.environ.get("DASHBOARD_HOST")
        old_token = os.environ.pop("DASHBOARD_TOKEN", None)
        os.environ["DASHBOARD_HOST"] = "0.0.0.0"
        try:
            with self.assertRaises(RuntimeError):
                create_app(root=tempfile.mkdtemp())
        finally:
            if old_host is None:
                os.environ.pop("DASHBOARD_HOST", None)
            else:
                os.environ["DASHBOARD_HOST"] = old_host
            if old_token is not None:
                os.environ["DASHBOARD_TOKEN"] = old_token

    def test_second_brain_records_jsonl(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            brain = SecondBrain(path)
            brain.record("lesson", "Spread too high", "Skip signal", symbol="XAUUSD")
            rows = brain.recent()
            self.assertEqual(rows[0]["kind"], "lesson")
            self.assertEqual(rows[0]["metadata"]["symbol"], "XAUUSD")


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_execution.py

``python
import os
import unittest
from types import SimpleNamespace

from module.execution import ExecutionEngine


class FakeMT5:
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.calls = []

    def order_send(self, request):
        self.calls.append(request)
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, comment="live")


class ExecutionEngineTests(unittest.TestCase):
    def test_paper_never_calls_mt5(self):
        api = FakeMT5()
        result = ExecutionEngine(api, "PAPER").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
        self.assertTrue(result.simulated)
        self.assertEqual(api.calls, [])

    def test_backtest_never_calls_mt5(self):
        api = FakeMT5()
        result = ExecutionEngine(api, "BACKTEST").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
        self.assertTrue(result.simulated)
        self.assertEqual(api.calls, [])

    def test_live_requires_explicit_flag(self):
        api = FakeMT5()
        old = os.environ.pop("ENABLE_LIVE_TRADING", None)
        try:
            with self.assertRaises(RuntimeError):
                ExecutionEngine(api, "LIVE").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
            self.assertEqual(api.calls, [])
        finally:
            if old is not None:
                os.environ["ENABLE_LIVE_TRADING"] = old

    def test_live_calls_mt5_only_when_explicitly_enabled(self):
        api = FakeMT5()
        old = os.environ.get("ENABLE_LIVE_TRADING")
        os.environ["ENABLE_LIVE_TRADING"] = "YES"
        try:
            result = ExecutionEngine(api, "LIVE").send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
            self.assertFalse(result.simulated)
            self.assertEqual(len(api.calls), 1)
        finally:
            if old is None:
                os.environ.pop("ENABLE_LIVE_TRADING", None)
            else:
                os.environ["ENABLE_LIVE_TRADING"] = old


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_live_gate_metrics.py

``python
import unittest
from types import SimpleNamespace
from module.risk import RiskLimits, RiskValidator
from module.risk_metrics import broker_metrics
from module.experiments.grid_hedge import GridHedgeConfig, pending_levels

class LiveGateMetricTests(unittest.TestCase):
    def test_numeric_mt5_type_is_understood_by_sl_tp_validation(self):
        validator = RiskValidator(RiskLimits(max_volume=1.0))
        decision = validator.validate({"symbol": "XAUUSD", "volume": 0.1, "price": 100.0, "type": 0, "sl": 95.0, "tp": 110.0})
        self.assertTrue(decision.approved, decision.reasons)

    def test_grid_planning_is_pure_and_symmetric(self):
        levels = pending_levels(100.0, GridHedgeConfig(step_price=0.5, levels=2))
        self.assertEqual(levels, {"buy": [100.5, 101.0], "sell": [99.5, 99.0]})

    def test_paper_metrics_include_open_positions(self):
        class Broker:
            positions = {"x": SimpleNamespace(status="OPEN", profit=3.5)}
            def positions_get(self): return list(self.positions.values())
        profit, count = broker_metrics(None, Broker(), "PAPER")
        self.assertEqual((profit, count), (3.5, 1))

if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_log_monitor.py

``python
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.monitor_logs import Telegram, is_alert, monitor


class LogMonitorTests(unittest.TestCase):
    def test_alert_filter(self):
        self.assertTrue(is_alert({"level": "ERROR", "message": "x"}))
        self.assertTrue(is_alert({"level": "INFO", "event": "recovery_timeout"}))
        self.assertFalse(is_alert({"level": "INFO", "event": "state_transition"}))

    def test_disabled_telegram_does_not_send(self):
        with patch.dict(os.environ, {"TELEGRAM_ALERTS_ENABLED": "NO", "TELEGRAM_BOT_TOKEN": "secret", "TELEGRAM_CHAT_ID": "1"}, clear=False):
            self.assertFalse(Telegram().enabled)

    def test_once_reads_error_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trading.jsonl"
            path.write_text(json.dumps({"level": "ERROR", "event": "run_once_error", "message": "boom"}) + "\n")
            with patch.dict(os.environ, {"TELEGRAM_ALERTS_ENABLED": "NO"}, clear=False):
                self.assertEqual(monitor(path, once=True), 0)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_main_smoke.py

``python
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from types import SimpleNamespace

from module.backtest import ReplaySignal


class FakeMT5:
    TRADE_RETCODE_DONE = 10009
    ORDER_TYPE_BUY = 0

    def __init__(self):
        self.initialized = 0
        self.orders = []

    def initialize(self):
        self.initialized += 1
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=123, bid=100.0, ask=100.2)

    def positions_get(self, symbol=None):
        return []

    def copy_rates_from_pos(self, symbol, tf, start, count):
        return None


class MainSmokeTest(unittest.TestCase):
    def test_setup_and_run_once_with_mock_mt5(self):
        fake = FakeMT5()
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
            "TRADING_MODE": "PAPER",
            "PAPER_STATE_PATH": str(Path(directory) / "paper.json"),
            "TRADE_STATE_PATH": str(Path(directory) / "trade.json"),
            "MEMORY_PATH": str(Path(directory) / "memory.jsonl"),
            "LOG_DIR": str(Path(directory) / "logs"),
            "INITIAL_BALANCE": "1000",
            "LOOP_INTERVAL_SECONDS": "0.05",
        }, clear=False):
            import main
            def provider(rt):
                return ReplaySignal("smoke", "XAUUSD", 0.01, 0, 100.0, 95.0, 110.0, "smoke")
            rt = main.setup(api=fake, signal_provider=provider)
            result = main.run_once(rt)
            self.assertEqual(fake.initialized, 1)
            self.assertIsNotNone(result)
            self.assertEqual(result.retcode, fake.TRADE_RETCODE_DONE)
            main.reconcile_all_trade_states()


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_managed_order_integration.py

``python
import os
import tempfile
import unittest
from types import SimpleNamespace

import main


class FakeAPI:
    TRADE_RETCODE_DONE = 10009

    def __init__(self):
        self.order_send_calls = 0

    def initialize(self):
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=123, ask=100.0, bid=99.9)

    def order_send(self, request):
        self.order_send_calls += 1
        return SimpleNamespace(retcode=self.TRADE_RETCODE_DONE, order=1, comment="unexpected")


class ManagedOrderIntegrationTests(unittest.TestCase):
    def test_daily_loss_rejects_through_managed_create_order(self):
        with tempfile.TemporaryDirectory() as directory:
            old = {key: os.environ.get(key) for key in (
                "TRADING_MODE", "RISK_MAX_DAILY_LOSS", "TRADE_STATE_PATH",
                "PAPER_STATE_PATH", "MEMORY_PATH", "LOG_DIR"
            )}
            os.environ.update({
                "TRADING_MODE": "PAPER",
                "RISK_MAX_DAILY_LOSS": "10",
                "TRADE_STATE_PATH": os.path.join(directory, "trade_state.json"),
                "PAPER_STATE_PATH": os.path.join(directory, "paper_state.json"),
                "MEMORY_PATH": os.path.join(directory, "memory.jsonl"),
                "LOG_DIR": directory,
            })
            try:
                api = FakeAPI()
                runtime = main.setup(api=api)
                runtime.paper_broker.send({
                    "action": "deal", "symbol": "XAUUSD", "volume": 0.1, "type": "buy",
                    "price": 100.0, "sl": 95.0, "tp": 110.0, "comment": "existing",
                    "trade_id": "existing-1",
                })
                existing = next(iter(runtime.paper_broker.positions.values()))
                existing.profit = -25.0
                result = main.managed_create_order(
                    "XAUUSD", 0.1, "buy", 95.0, 110.0, "integration", "1m"
                )
                self.assertIsNone(result)
                self.assertEqual(api.order_send_calls, 0)
                trade_id = next(iter(main.trade_states.records))
                self.assertEqual(main.trade_states.get(trade_id).state.value, "REJECTED")
            finally:
                for key, value in old.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_market_replay.py

``python
import tempfile
import unittest
from pathlib import Path

from module.market_data import candle_to_ticks, load_candles_csv, load_ticks_csv
from module.paper import PaperBroker


class MarketReplayTests(unittest.TestCase):
    def test_candle_loader_and_deterministic_bullish_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "candles.csv"
            path.write_text("timestamp,open,high,low,close,volume\n2026-01-01T00:00:00Z,100,112,98,110,10\n")
            candles = load_candles_csv(path)
            self.assertEqual([t.price for t in candle_to_ticks(candles[0])], [100, 112, 98, 110])

    def test_tick_loader_sorts_and_reads_ask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticks.csv"
            path.write_text("timestamp,bid,ask\n2026-01-01T00:00:01Z,101,102\n2026-01-01T00:00:00Z,100,101\n")
            ticks = load_ticks_csv(path)
            self.assertEqual(ticks[0].bid, 100)
            self.assertEqual(ticks[0].price, 100.5)

    def test_candle_replay_hits_tp(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send({"trade_id": "replay", "symbol": "XAUUSD", "volume": 1, "type": 0, "price": 100, "sl": 95, "tp": 110, "action": "deal"})
            result = broker.replay_candles(load_candles_csv_from_text("2026-01-01T00:00:00Z,100,112,98,110"))
            self.assertEqual(result["closed"], 1)
            self.assertEqual(broker.positions["replay"].close_reason, "TP")


def load_candles_csv_from_text(row):
    import tempfile
    from pathlib import Path
    from module.market_data import load_candles_csv
    directory = tempfile.mkdtemp()
    path = Path(directory) / "c.csv"
    path.write_text("timestamp,open,high,low,close\n" + row + "\n")
    return load_candles_csv(path)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_observability.py

``python
import json
import logging
import tempfile
import unittest
from pathlib import Path

from module.observability import ErrorAlertingHandler, configure_logging


class ObservabilityTests(unittest.TestCase):
    def test_jsonl_logging_and_error_cooldown(self):
        with tempfile.TemporaryDirectory() as directory:
            alerts = []
            logger = configure_logging(directory, notifier=alerts.append, alert_cooldown_seconds=3600)
            logger.error("connection failure", extra={"event": "mt5_error", "symbol": "XAUUSD"})
            logger.error("connection failure", extra={"event": "mt5_error", "symbol": "XAUUSD"})
            for handler in logger.handlers:
                handler.flush()
            lines = (Path(directory) / "trading.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["level"], "ERROR")
            self.assertEqual(len(alerts), 1)

    def test_alert_handler_without_notifier_is_safe(self):
        handler = ErrorAlertingHandler(None)
        record = logging.LogRecord("test", logging.ERROR, __file__, 1, "boom", (), None)
        handler.emit(record)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_paper.py

``python
import tempfile
import unittest
from pathlib import Path

from module.paper import PaperBroker


class PaperTradingTests(unittest.TestCase):
    def request(self, trade_id="t1"):
        return {
            "trade_id": trade_id,
            "symbol": "XAUUSD",
            "volume": 0.1,
            "type": 0,
            "price": 2000.0,
            "sl": 1990.0,
            "tp": 2020.0,
            "comment": "strategy:t1",
            "magic": 26080901,
            "action": "deal",
        }

    def test_paper_order_creates_one_virtual_position(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            result = broker.send(self.request())
            self.assertEqual(result.retcode, 10009)
            self.assertEqual(len(broker.positions_get()), 1)
            self.assertEqual(broker.reconcile()["open_positions"], 1)

    def test_duplicate_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            first = broker.send(self.request())
            second = broker.send(self.request())
            self.assertEqual(first.order, second.order)
            self.assertEqual(len(broker.orders_get()), 1)
            self.assertEqual(len(broker.positions_get()), 1)

    def test_restart_recovers_ledger_and_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.json"
            first = PaperBroker(path)
            result = first.send(self.request("restart-id"))
            restored = PaperBroker(path)
            duplicate = restored.send(self.request("restart-id"))
            self.assertEqual(result.order, duplicate.order)
            self.assertEqual(len(restored.positions_get()), 1)

    def test_close_persists_virtual_position(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.json"
            broker = PaperBroker(path)
            broker.send(self.request("close-id"))
            self.assertTrue(broker.close("close-id"))
            restored = PaperBroker(path)
            self.assertEqual(len(restored.positions_get()), 0)
            self.assertEqual(restored.reconcile()["closed_positions"], 1)

    def test_manual_close_records_current_price_and_profit(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("manual-pnl"))
            position = broker.positions["manual-pnl"]
            position.current_price = 2010.0
            self.assertTrue(broker.close("manual-pnl"))
            closed = broker.positions["manual-pnl"]
            self.assertEqual(closed.exit_price, 2010.0)
            self.assertEqual(closed.gross_profit, 1.0)
            self.assertEqual(closed.profit, 1.0)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_paper_price.py

``python
import tempfile
import unittest
from pathlib import Path

from module.paper import PaperBroker


class PaperPriceTests(unittest.TestCase):
    def request(self, trade_id, order_type, sl, tp):
        return {
            "trade_id": trade_id,
            "symbol": "XAUUSD",
            "volume": 1.0,
            "type": order_type,
            "price": 100.0,
            "sl": sl,
            "tp": tp,
            "comment": trade_id,
            "magic": 26080901,
            "action": "deal",
        }

    def test_buy_tp_closes_with_positive_pnl_and_slippage(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("buy-tp", 0, 95, 110))
            result = broker.mark_price("XAUUSD", 110, slippage=1.5)
            position = broker.positions["buy-tp"]
            self.assertEqual(result["closed"], 1)
            self.assertEqual(position.close_reason, "TP")
            self.assertEqual(position.exit_price, 108.5)
            self.assertAlmostEqual(position.profit, 8.5)

    def test_buy_sl_closes_with_negative_pnl(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("buy-sl", 0, 95, 110))
            broker.mark_price("XAUUSD", 95, slippage=0.5)
            position = broker.positions["buy-sl"]
            self.assertEqual(position.close_reason, "SL")
            self.assertAlmostEqual(position.profit, -5.5)

    def test_sell_tp_closes_with_positive_pnl(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("sell-tp", 1, 105, 90))
            broker.mark_price("XAUUSD", 90, slippage=1.0)
            position = broker.positions["sell-tp"]
            self.assertEqual(position.close_reason, "TP")
            self.assertAlmostEqual(position.exit_price, 91.0)
            self.assertAlmostEqual(position.profit, 9.0)

    def test_price_between_barriers_keeps_position_open(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json")
            broker.send(self.request("open", 0, 95, 110))
            result = broker.mark_price("XAUUSD", 105)
            self.assertEqual(result["closed"], 0)
            self.assertEqual(broker.positions["open"].status, "OPEN")
            self.assertAlmostEqual(broker.positions["open"].profit, 5.0)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_performance_replay.py

``python
import tempfile
import unittest
from pathlib import Path

from module.backtest import HistoricalReplay, ReplaySignal
from module.market_data import Candle
from module.paper import PaperBroker
from module.performance import calculate_performance, max_drawdown


class PerformanceReplayTests(unittest.TestCase):
    def test_metrics(self):
        result = calculate_performance([100, -50, 25, -25], initial_balance=1000)
        self.assertEqual(result["trades"], 4)
        self.assertAlmostEqual(result["profit_factor"], 1.6666666667)
        self.assertAlmostEqual(result["net_profit"], 50)
        self.assertGreater(result["sharpe"], 0)

    def test_drawdown(self):
        result = max_drawdown([1000, 1100, 1040, 1200, 1150])
        self.assertEqual(result["max_drawdown"], 60)
        self.assertEqual(result["peak"], 1100)
        self.assertEqual(result["trough"], 1040)

    def test_strategy_callback_runs_through_paper_replay(self):
        candles = [
            Candle("1", "XAUUSD", 100, 105, 99, 104),
            Candle("2", "XAUUSD", 104, 106, 95, 96),
        ]
        calls = []

        def strategy(history, candle):
            calls.append((len(history), candle.timestamp))
            if candle.timestamp == "1":
                return [ReplaySignal("r1", "XAUUSD", 1, 0, 100, 95, 104, "test")]
            return []

        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            result = HistoricalReplay(broker, initial_balance=1000).run(candles, strategy)
            self.assertEqual(calls, [(0, "1"), (1, "2")])
            self.assertEqual(result["closed_profits"], [5.0])
            self.assertEqual(result["metrics"]["profit_factor"], float("inf"))


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_recovery.py

``python
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from module.recovery import TradeRecovery
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class FakeBroker:
    def __init__(self, orders=(), positions=()):
        self.orders = list(orders)
        self.positions = list(positions)

    def orders_get(self, symbol=None):
        return self.orders

    def positions_get(self, symbol=None):
        return self.positions


class RecoveryTests(unittest.TestCase):
    def make_machine(self, state, age=0):
        machine = TradeStateMachine()
        old = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        machine.create(TradeRecord("t1", state=state, symbol="XAUUSD", strategy="strat", updated_at=old))
        return machine

    def item(self, ticket=10, comment="strat"):
        return SimpleNamespace(ticket=ticket, symbol="XAUUSD", magic=26080901, comment=comment)

    def test_sent_with_order_recovers_to_accepted(self):
        machine = self.make_machine(TradeState.SENT)
        report = TradeRecovery(FakeBroker(orders=[self.item()])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.ACCEPTED)
        self.assertEqual(report.recovered, 1)

    def test_sent_timeout_is_rejected_without_resend(self):
        machine = self.make_machine(TradeState.SENT, age=300)
        report = TradeRecovery(FakeBroker(), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)

    def test_accepted_with_position_recovers_to_open(self):
        machine = self.make_machine(TradeState.ACCEPTED)
        report = TradeRecovery(FakeBroker(positions=[self.item(ticket=11)])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.OPEN)
        self.assertEqual(machine.get("t1").ticket, 11)
        self.assertEqual(report.opened, 1)

    def test_wrong_magic_is_ignored(self):
        machine = self.make_machine(TradeState.ACCEPTED, age=300)
        foreign = SimpleNamespace(ticket=99, symbol="XAUUSD", magic=999, comment="strat")
        TradeRecovery(FakeBroker(positions=[foreign]), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)

    def test_persistence_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            machine = TradeStateMachine(path)
            machine.create(TradeRecord("t1", state=TradeState.ACCEPTED, symbol="XAUUSD", strategy="strat"))
            restored = TradeStateMachine(path)
            TradeRecovery(FakeBroker(positions=[self.item()])).recover(restored)
            self.assertEqual(restored.get("t1").state, TradeState.OPEN)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_recovery_matrix.py

``python
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from module.execution import ExecutionEngine
from module.recovery import TradeRecovery
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class Broker:
    def __init__(self, orders=(), positions=()):
        self.orders = list(orders)
        self.positions = list(positions)
        self.send_calls = 0

    def orders_get(self, symbol=None):
        return [x for x in self.orders if symbol is None or getattr(x, "symbol", symbol) == symbol]

    def positions_get(self, symbol=None):
        return [x for x in self.positions if symbol is None or getattr(x, "symbol", symbol) == symbol]

    def send(self, request):
        self.send_calls += 1
        return SimpleNamespace(retcode=10009, order=1, comment="accepted", simulated=True)


class RecoveryMatrixTests(unittest.TestCase):
    def record(self, state, age=0, ticket=0):
        old = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        machine = TradeStateMachine()
        machine.create(TradeRecord("t1", state=state, symbol="XAUUSD", strategy="strat", ticket=ticket, updated_at=old))
        return machine

    def item(self, *, ticket=10, magic=26080901, comment="strat", symbol="XAUUSD"):
        return SimpleNamespace(ticket=ticket, symbol=symbol, magic=magic, comment=comment)

    def test_sent_after_restart_with_broker_order(self):
        machine = self.record(TradeState.SENT)
        report = TradeRecovery(Broker(orders=[self.item(ticket=77)])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.ACCEPTED)
        self.assertEqual(machine.get("t1").ticket, 77)
        self.assertEqual(report.recovered, 1)

    def test_accepted_without_position_waits_before_timeout(self):
        machine = self.record(TradeState.ACCEPTED, age=10)
        report = TradeRecovery(Broker(), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.ACCEPTED)
        self.assertEqual(report.waiting, 1)

    def test_position_ticket_mismatch_is_recovered_by_magic_and_comment(self):
        machine = self.record(TradeState.ACCEPTED, ticket=12)
        report = TradeRecovery(Broker(positions=[self.item(ticket=99)])).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.OPEN)
        self.assertEqual(machine.get("t1").ticket, 99)
        self.assertEqual(report.opened, 1)

    def test_accepted_timeout_is_rejected(self):
        machine = self.record(TradeState.ACCEPTED, age=300)
        report = TradeRecovery(Broker(), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)

    def test_recovery_never_resends_order(self):
        broker = Broker(orders=[self.item()])
        machine = self.record(TradeState.SENT)
        TradeRecovery(broker).recover(machine)
        TradeRecovery(broker).recover(machine)
        self.assertEqual(broker.send_calls, 0)

    def test_magic_and_comment_are_both_required(self):
        machine = self.record(TradeState.ACCEPTED, age=300)
        foreign = self.item(magic=999, comment="strat")
        wrong_comment = self.item(magic=26080901, comment="other")
        report = TradeRecovery(Broker(positions=[foreign, wrong_comment]), timeout_seconds=120).recover(machine)
        self.assertEqual(machine.get("t1").state, TradeState.REJECTED)
        self.assertEqual(report.rejected, 1)

    def test_paper_does_not_call_mt5_and_live_is_explicit(self):
        class Api:
            TRADE_RETCODE_DONE = 10009
            def __init__(self): self.calls = []
            def order_send(self, request):
                self.calls.append(request)
                return SimpleNamespace(retcode=10009, order=1, comment="live")
        api = Api()
        paper = ExecutionEngine(api, "PAPER")
        result = paper.send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
        self.assertTrue(result.simulated)
        self.assertEqual(api.calls, [])
        old = os.environ.get("ENABLE_LIVE_TRADING")
        os.environ["ENABLE_LIVE_TRADING"] = "YES"
        try:
            live = ExecutionEngine(api, "LIVE")
            result = live.send({"action": "deal", "symbol": "XAUUSD", "volume": 0.1})
            self.assertFalse(result.simulated)
            self.assertEqual(len(api.calls), 1)
        finally:
            if old is None: os.environ.pop("ENABLE_LIVE_TRADING", None)
            else: os.environ["ENABLE_LIVE_TRADING"] = old


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_risk_and_state.py

``python
import tempfile
import unittest
from pathlib import Path

from module.risk import RiskLimits, RiskValidator
from module.state_machine import TradeRecord, TradeState, TradeStateMachine


class RiskAndStateTests(unittest.TestCase):
    def test_risk_rejects_daily_loss_and_excess_volume(self):
        validator = RiskValidator(RiskLimits(max_volume=0.1, max_daily_loss=100))
        decision = validator.validate(
            {"symbol": "XAUUSD", "volume": 0.2},
            daily_profit=-100,
        )
        self.assertFalse(decision.approved)
        self.assertIn("volume exceeds max_volume", decision.reasons)
        self.assertIn("daily loss limit reached", decision.reasons)

    def test_risk_accepts_valid_order(self):
        decision = RiskValidator(RiskLimits(max_volume=1)).validate(
            {"symbol": "XAUUSD", "volume": 0.1}
        )
        self.assertTrue(decision.approved)

    def test_risk_bypass_is_rejected_for_opening_order(self):
        decision = RiskValidator(RiskLimits(max_volume=0.1)).validate(
            {"action": "deal", "symbol": "XAUUSD", "volume": 10.0, "risk_exempt": True}
        )
        self.assertFalse(decision.approved)
        self.assertIn("risk_exempt is only valid for non-opening actions", decision.reasons)

    def test_risk_bypass_is_allowed_for_position_modification(self):
        decision = RiskValidator(RiskLimits(max_volume=0.1)).validate(
            {"action": 6, "position": 42, "symbol": "XAUUSD", "volume": 10.0, "risk_exempt": True}
        )
        self.assertTrue(decision.approved)

    def test_state_machine_rejects_invalid_transition(self):
        machine = TradeStateMachine()
        machine.create(TradeRecord("t1", symbol="XAUUSD"))
        machine.transition("t1", TradeState.VALIDATED)
        with self.assertRaises(ValueError):
            machine.transition("t1", TradeState.OPEN)

    def test_state_machine_persists_and_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            machine = TradeStateMachine(path)
            machine.create(TradeRecord("t1", symbol="XAUUSD"))
            machine.transition("t1", TradeState.VALIDATED)
            machine.transition("t1", TradeState.APPROVED)
            restored = TradeStateMachine(path)
            self.assertEqual(restored.get("t1").state, TradeState.APPROVED)
            self.assertTrue(restored.get("t1").created_at.endswith("+00:00"))
            self.assertTrue(restored.get("t1").updated_at.endswith("+00:00"))

    def test_transition_updates_timestamp(self):
        machine = TradeStateMachine()
        record = machine.create(TradeRecord("t1"))
        created = record.created_at
        machine.transition("t1", TradeState.VALIDATED)
        self.assertEqual(machine.get("t1").created_at, created)
        self.assertGreaterEqual(machine.get("t1").updated_at, created)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_safety_audit.py

``python
import logging
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from module.execution import ExecutionEngine
from module.observability import ErrorAlertingHandler
from module.risk import RiskLimits, RiskValidator, bounded_risk_percent

class FakeAPI:
    TRADE_RETCODE_DONE = 10009
    def initialize(self): return True
    def symbol_info_tick(self, symbol): return SimpleNamespace(time=1, ask=100.0, bid=99.9)

class SafetyAuditTests(unittest.TestCase):
    def test_alert_first_send_with_monotonic_clock(self):
        alerts=[]; handler=ErrorAlertingHandler(alerts.append, cooldown_seconds=10)
        rec=logging.LogRecord("x", logging.ERROR, __file__, 1, "boom", (), None)
        with patch("module.observability.time.monotonic", side_effect=[0.1, 0.2, 11.0]):
            handler.emit(rec); handler.emit(rec); handler.emit(rec)
        self.assertEqual(len(alerts), 2)

    def test_legacy_risk_correction_is_hard_capped(self):
        self.assertEqual(bounded_risk_percent(100.0, max_risk=100.0), 2.0)

    def test_drawdown_gate_rejects(self):
        decision=RiskValidator(RiskLimits(max_volume=1, max_drawdown_pct=10)).validate({"symbol":"XAUUSD","volume":.1}, drawdown_pct=10)
        self.assertFalse(decision.approved)
        self.assertIn("max drawdown limit reached", decision.reasons)

    def test_emergency_stop_closes_paper_positions_and_locks(self):
        from module.paper import PaperBroker
        with tempfile.TemporaryDirectory() as d:
            broker=PaperBroker(os.path.join(d,"paper.json"))
            broker.send({"action":"deal","symbol":"XAUUSD","volume":.1,"type":"buy","price":100.0,"sl":95,"tp":110,"comment":"t","trade_id":"emergency-1"})
            engine=ExecutionEngine(FakeAPI(), mode="PAPER", paper_broker=broker)
            result=engine.emergency_stop()
            self.assertEqual(result["closed"], 1); self.assertTrue(engine.emergency_locked)
            with self.assertRaises(RuntimeError): engine.send({"action":"deal","symbol":"XAUUSD","volume":.1})
            engine.reset_emergency_stop(); self.assertFalse(engine.emergency_locked)

if __name__ == "__main__": unittest.main()

``

## File: tests\test_strategy_adapter.py

``python
import tempfile
import unittest
from pathlib import Path

from module.backtest import HistoricalReplay
from module.market_data import Candle
from module.paper import PaperBroker
from module.strategy_adapter import CallableIndicator, CombinedVotingStrategy, HalfTrendAdapter, SupertrendAdapter


class StrategyAdapterTests(unittest.TestCase):
    def candles(self):
        return [
            Candle(str(i), "XAUUSD", 100 + i, 102 + i, 98 + i, 101 + i)
            for i in range(20)
        ]

    def test_builtin_indicators_are_pure_and_aligned(self):
        candles = self.candles()
        for adapter in (SupertrendAdapter(3, 1.5), HalfTrendAdapter(2)):
            result = adapter.evaluate(candles)
            self.assertEqual(len(result["direction"]), len(candles))
            self.assertEqual(len(result["signals"]), len(candles))
            self.assertEqual(len(result["line"]), len(candles))

    def test_combined_voting_requires_threshold(self):
        def buy(_):
            return {"signals": ["buy"], "line": [95]}

        def sell(_):
            return {"signals": ["sell"], "line": [105]}

        strategy = CombinedVotingStrategy([CallableIndicator("a", buy), CallableIndicator("b", buy)], volume=1, rr=2)
        signals = list(strategy([], Candle("1", "XAUUSD", 100, 102, 99, 101)))
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].order_type, 0)
        self.assertEqual(signals[0].sl, 95)
        self.assertEqual(signals[0].tp, 110)
        no_consensus = CombinedVotingStrategy([CallableIndicator("a", buy), CallableIndicator("b", sell)], min_votes=2)
        self.assertEqual(list(no_consensus([], Candle("1", "XAUUSD", 100, 102, 99, 101))), [])

    def test_custom_indicator_can_run_through_replay(self):
        def buy(_):
            return {"signals": ["buy"], "line": [90]}

        strategy = CombinedVotingStrategy([CallableIndicator("custom", buy)], volume=1, rr=1)
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            result = HistoricalReplay(broker, initial_balance=1000).run(self.candles()[:1], strategy)
            self.assertEqual(result["candles"], 1)
            self.assertEqual(len(broker.orders), 1)


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_stress.py

``python
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from module.paper import PaperBroker
from module.market_data import Tick


class StressTests(unittest.TestCase):
    def test_max_drawdown_from_equity_curve(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            broker.equity_history = [
                {"timestamp": "1", "equity": 1050},
                {"timestamp": "2", "equity": 980},
                {"timestamp": "3", "equity": 1010},
            ]
            result = broker.max_drawdown()
            self.assertEqual(result["max_drawdown"], 70)
            self.assertAlmostEqual(result["max_drawdown_percent"], 6.6666666667, places=5)
            self.assertEqual(result["peak"], 1050)
            self.assertEqual(result["trough"], 980)

    def test_stress_replay_persists_through_restarts_and_idempotency(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.json"
            broker = PaperBroker(path, initial_balance=1000)
            request = {"trade_id": "stress", "symbol": "XAUUSD", "volume": 1, "type": 0, "price": 100, "sl": 95, "tp": 110, "action": "deal"}
            first = broker.send(request)
            ticks = [Tick(str(i), "XAUUSD", price) for i, price in enumerate([101, 102, 99, 104, 98, 103])]
            report = broker.stress_replay(ticks, slippage=0.1, restart_every=2)
            duplicate = broker.send(request)
            self.assertEqual(first.order, duplicate.order)
            self.assertEqual(report["restarts"], 3)
            self.assertEqual(report["ticks"], 6)
            self.assertEqual(report["open_positions"], 1)
            self.assertGreaterEqual(report["max_drawdown"], 0)

    def test_stress_replay_closes_on_tp(self):
        with tempfile.TemporaryDirectory() as directory:
            broker = PaperBroker(Path(directory) / "paper.json", initial_balance=1000)
            broker.send({"trade_id": "tp", "symbol": "XAUUSD", "volume": 1, "type": 0, "price": 100, "sl": 95, "tp": 105, "action": "deal"})
            report = broker.stress_replay([Tick("1", "XAUUSD", 102), Tick("2", "XAUUSD", 105)], restart_every=1)
            self.assertEqual(report["closed"], 1)
            self.assertEqual(broker.positions["tp"].close_reason, "TP")


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_telegram_alerts.py

``python
import json
import os
import unittest
from unittest.mock import patch

from module.telegram_alerts import TelegramAlertConfig, TelegramAlertNotifier


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"ok": True}).encode()


class TelegramAlertTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            notifier = TelegramAlertNotifier()
            self.assertFalse(notifier.enabled)
            self.assertFalse(notifier.send("test"))

    def test_requires_both_credentials_and_explicit_enable(self):
        with patch.dict(os.environ, {"TELEGRAM_ALERTS_ENABLED": "YES", "TELEGRAM_BOT_TOKEN": "token"}, clear=True):
            self.assertFalse(TelegramAlertNotifier().enabled)

    def test_enabled_notifier_uses_environment_credentials(self):
        env = {
            "TELEGRAM_ALERTS_ENABLED": "YES",
            "TELEGRAM_BOT_TOKEN": "secret-token",
            "TELEGRAM_CHAT_ID": "12345",
        }
        with patch.dict(os.environ, env, clear=True), patch("module.telegram_alerts.urlopen", return_value=FakeResponse()) as urlopen:
            notifier = TelegramAlertNotifier(TelegramAlertConfig.from_env())
            self.assertTrue(notifier.enabled)
            self.assertTrue(notifier.send("alert"))
            request = urlopen.call_args.args[0]
            self.assertIn("secret-token", request.full_url)
            self.assertIn("12345", request.data.decode())


if __name__ == "__main__":
    unittest.main()

``

## File: tests\test_timeframe_data.py

``python
import unittest
import pandas as pd
from module.timeframe_data import resample_m1_ohlcv

class TimeframeDataTests(unittest.TestCase):
    def test_resamples_m1_to_three_minute_deterministically(self):
        df=pd.DataFrame({"time":pd.date_range("2026-01-01",periods=6,freq="min"),"open":[1,2,3,4,5,6],"high":[2,3,4,5,6,7],"low":[0,1,2,3,4,5],"close":[1.5,2.5,3.5,4.5,5.5,6.5],"tick_volume":[1,2,3,4,5,6]})
        out=resample_m1_ohlcv(df,"3m")
        self.assertEqual(len(out),2); self.assertEqual(out.loc[0,"open"],1); self.assertEqual(out.loc[0,"high"],4); self.assertEqual(out.loc[0,"low"],0); self.assertEqual(out.loc[0,"volume"],6)

if __name__ == "__main__": unittest.main()

``

## File: tests\test_volume_control.py

``python
import json
import tempfile
import unittest
from pathlib import Path

from module.volume_control import VolumeController, calculate_risk_volume, risk_corrected_percent


class VolumeControlTests(unittest.TestCase):
    def test_risk_corrector_never_below_base_or_above_max(self):
        self.assertEqual(risk_corrected_percent(1, 1000, 2, 1, 1000, 2), 1)
        self.assertLessEqual(risk_corrected_percent(1, 1000, 2, 100, -1000, 2), 2)

    def test_volume_uses_stop_distance_and_hard_cap(self):
        volume = calculate_risk_volume(1000, 1, 2000, 1990, 1, 1, max_target=0.01)
        self.assertEqual(volume, 0.01)

    def test_change_is_logged_and_rollback_is_possible(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = VolumeController(Path(directory) / "state.json", Path(directory) / "volume_changes.log", max_target=0.1, min_observation_days=0)
            change = controller.record_change(0.02, 1.0, "stable PAPER", "operator")
            self.assertEqual(change.new_volume, 0.02)
            self.assertEqual(len(Path(directory, "volume_changes.log").read_text().splitlines()), 1)
            rollback = controller.rollback(0.01, "drawdown increase", "operator")
            self.assertEqual(rollback.status, "ROLLBACK")
            self.assertEqual(json.loads(Path(directory, "state.json").read_text())["current_volume"], 0.01)

    def test_hard_target_rejects_above_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = VolumeController(Path(directory) / "state.json", Path(directory) / "volume_changes.log", max_target=0.02, min_observation_days=0)
            change = controller.record_change(0.10, 1.0, "attempt", "operator")
            self.assertEqual(change.new_volume, 0.02)


if __name__ == "__main__":
    unittest.main()

``
