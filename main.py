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
