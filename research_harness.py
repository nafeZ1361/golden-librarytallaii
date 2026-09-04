# research_harness.py
# Shared, reusable research harness (CP4/CP4c/CP4d logic refactored into functions).
# All functions take a `signal_fn` (strategy module) and/or window data - no MT5
# fetch inside strategies (coherent-pipeline property enforced by design).
# Nothing here modifies project source. No orders.

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

TF_INFO = {"3m": {"mt5": None, "bars_per_window": 14400},  # mt5 const injected at load
           "15m": {"mt5": None, "bars_per_window": 2880},
           "1h": {"mt5": None, "bars_per_window": 720}}
TF_STR = {"3m": "3m", "15m": "15m", "1h": "1h"}


# ---------------------------------------------------------------- data loader
def load_windows(mt5, tf, n_windows=6, m3_boundaries=None):
    """Return list of plain-candle windows (same 6 calendar windows as CP4d):
       time(naive broker) / open / high / low / close / volume(+ tick_volume raw
       for strategies that need tick volume: kept as 'tick_volume')."""
    if tf == "3m":
        total = 14400 * n_windows
        raw = mt5.copy_rates_from_pos("XAUUSD.", mt5.TIMEFRAME_M3, 1, total)
        if raw is None or len(raw) < total:
            raise RuntimeError("insufficient 3m history")
        raw = raw[np.argsort(raw["time"])]
        bounds = [int(raw["time"][i * 14400]) for i in range(n_windows)] + [int(raw["time"][-1])]
        wins = []
        for w in range(n_windows):
            sl = raw[w * 14400:(w + 1) * 14400]
            t = pd.to_datetime(sl["time"], unit="s")
            d = pd.DataFrame(sl)
            d["time"] = t.values
            if "tick_volume" in d.columns and "volume" not in d.columns:
                d["volume"] = d["tick_volume"]
            wins.append(d.reset_index(drop=True))
        return wins, bounds
    # higher TFs: same calendar bounds as the M3 reference
    tf_const = {"15m": mt5.TIMEFRAME_M15, "1h": mt5.TIMEFRAME_H1}[tf]
    if m3_boundaries is None:
        raise RuntimeError("m3_boundaries required for non-3m tf")
    rates = mt5.copy_rates_range("XAUUSD.", tf_const,
                                 pd.to_datetime(m3_boundaries[0], unit="s").to_pydatetime(),
                                 pd.to_datetime(m3_boundaries[-1], unit="s").to_pydatetime())
    if rates is None or len(rates) == 0:
        raise RuntimeError("no %s data" % tf)
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    if "tick_volume" in df.columns and "volume" not in df.columns:
        df["volume"] = df["tick_volume"]
    df = df.sort_values("time").reset_index(drop=True)
    wins = []
    for w in range(n_windows):
        lo, hi = m3_boundaries[w], m3_boundaries[w + 1]
        tsec = df["time"].astype(np.int64) // 10**9
        wins.append(df[(tsec >= lo) & (tsec <= hi)].reset_index(drop=True))
    return wins, m3_boundaries


def window_bounds_from_m3(mt5, n_windows=6):
    raw = mt5.copy_rates_from_pos("XAUUSD.", mt5.TIMEFRAME_M3, 1, 14400 * n_windows)
    raw = raw[np.argsort(raw["time"])]
    return [int(raw["time"][i * 14400]) for i in range(n_windows)] + [int(raw["time"][-1])]


# ------------------------------------------------------------- hit rate metric
def hit_rate(states, closes, horizon):
    """Generalized CP4c transition metric: every bar i where the state ENTERS
       'buy'/'sell' and differs from the previous bar's state counts as one
       directional prediction. Consecutive same-direction bars = one run/event.
       Pure trend-state series (no 'hold') reduce exactly to CP4c flip counting."""
    events = hits = excluded = 0
    for i in range(1, len(states)):
        s_prev, s_cur = states[i - 1], states[i]
        if s_cur in ("buy", "sell") and s_cur != s_prev:
            if i + horizon >= len(closes):
                excluded += 1
                continue
            events += 1
            fwd = closes[i + horizon]
            entry = closes[i]
            if (s_cur == "buy" and fwd > entry) or (s_cur == "sell" and fwd < entry):
                hits += 1
    return events, hits, excluded


def wald95(rate_pct, n):
    if n <= 0 or rate_pct is None:
        return None
    p = rate_pct / 100.0
    se = (p * (1 - p) / n) ** 0.5
    return [max(0.0, p - 1.96 * se) * 100, min(100.0, p + 1.96 * se) * 100]


def hit_rate_diagnostic(windows, signal_fn, horizons=(5, 20)):
    """windows: list of dataframes (plain candles). signal_fn(wdf) -> states list."""
    rows = []
    for wi, wdf in enumerate(windows):
        closes = wdf["close"].to_numpy()
        states = signal_fn(wdf)
        if states is None or len(states) != len(wdf):
            raise RuntimeError("signal_fn output length mismatch (w%d: %s vs %d)"
                               % (wi + 1, len(states) if states else None, len(wdf)))
        for h in horizons:
            ev, hits, excl = hit_rate(states, closes, h)
            rate = (hits / ev * 100) if ev else None
            rows.append({"window": wi + 1, "horizon": h, "events": ev,
                         "hits": hits, "rate_pct": rate, "excluded_end": excl,
                         "wald95": wald95(rate, ev)})
    return rows


def aggregate_hr(rows, horizon):
    rs = [r for r in rows if r["horizon"] == horizon]
    ev = sum(r["events"] for r in rs)
    hits = sum(r["hits"] for r in rs)
    rate = (hits / ev * 100) if ev else None
    return {"horizon": horizon, "events": ev, "hits": hits,
            "rate_pct": rate, "wald95": wald95(rate, ev), "windows": len(rs)}


# --------------------------------------------------- engine equivalence (CP4b)
def harness_backtest(df, trig, conf, pip, pv_per_lot, mode="fixed", atr=None,
                     fixed_sl_pips=100.0, fixed_tp_pips=200.0,
                     initial_balance=5000.0, risk_pct=2.0):
    """Mirror of project run_backtest(); returns dict incl. roi/winrate/trades/PF."""
    n = len(df)
    balance = initial_balance
    peak = initial_balance
    maxdd_pct = 0.0
    wins = losses = 0
    gross_win = gross_loss = 0.0
    current = None
    skipped = 0
    for i in range(n):
        bar = df.iloc[i]
        t_i, c_i = trig[i], conf[i]
        if current is None:
            if t_i in ("buy", "sell") and c_i == t_i:
                entry = float(bar["close"])
                if mode == "atr":
                    a = float(atr[i])
                    if np.isnan(a) or a <= 0:
                        skipped += 1
                        continue
                    sl_dist = 2.0 * a
                    tp_dist = 3.0 * a
                else:
                    sl_dist = fixed_sl_pips * pip
                    tp_dist = fixed_tp_pips * pip
                if t_i == "buy":
                    slp, tpp, ptype = entry - sl_dist, entry + tp_dist, "buy"
                else:
                    slp, tpp, ptype = entry + sl_dist, entry - tp_dist, "sell"
                raw_lot = (initial_balance * (risk_pct / 100.0)) / ((sl_dist / pip) * pv_per_lot)
                lot = max(0.01, round(raw_lot, 2))
                current = {"type": ptype, "entry": entry, "sl": slp, "tp": tpp,
                           "pv": round(pv_per_lot * lot, 3)}
        else:
            exit_price = pips = None
            if current["type"] == "buy":
                if bar["high"] >= current["tp"]:
                    exit_price, pips = current["tp"], (current["tp"] - current["entry"]) / pip
                elif bar["low"] <= current["sl"]:
                    exit_price, pips = current["sl"], (current["sl"] - current["entry"]) / pip
            else:
                if bar["low"] <= current["tp"]:
                    exit_price, pips = current["tp"], (current["entry"] - current["tp"]) / pip
                elif bar["high"] >= current["sl"]:
                    exit_price, pips = current["sl"], (current["entry"] - current["sl"]) / pip
            if exit_price is not None:
                profit = pips * current["pv"]
                balance += profit
                if profit > 0:
                    wins += 1
                    gross_win += profit
                elif profit < 0:
                    losses += 1
                    gross_loss += abs(profit)
                current = None
        if balance > peak:
            peak = balance
        maxdd_pct = max(maxdd_pct, (peak - balance) / peak * 100 if peak > 0 else 0)
    total = wins + losses
    return {"roi": (balance - initial_balance) / initial_balance * 100,
            "winrate": (wins / total * 100) if total else 0.0,
            "total_trades": total,
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf"),
            "max_drawdown": maxdd_pct, "final_balance": balance,
            "total_profit": balance - initial_balance, "skipped_entries": skipped}


def verify_engine_equivalence(hb, bi, mt5, window_df, sl_raw, symbol="XAUUSD.",
                              sl_pips=100.0, tp_pips=200.0):
    """CP4b-style proof: harness_backtest (fixed mode) == project run_backtest()."""
    import numpy as np
    pip = (10 ** -mt5.symbol_info(symbol).digits) * 10
    info = mt5.symbol_info(symbol)
    pip_size = (10 ** -info.digits) * 10
    pv_per_lot = (pip_size / info.trade_tick_size) * info.trade_tick_value
    sig = bi.backtest_supertrend(symbol, "3m", len(window_df), atr_period=10,
                                 multiplier=3.0, candle_type="ha", df=sl_raw)["signal"]
    conf = bi.backtest_trend_ali(symbol, "3m", len(window_df), length=60,
                                 length_mult=6.0, mode="Hma", candle_type="ha",
                                 df=sl_raw)["trend"]
    if len(sig) > len(window_df): sig = sig[-len(window_df):]
    if len(conf) > len(window_df): conf = conf[-len(window_df):]
    if len(sig) < len(window_df): sig += ["hold"] * (len(window_df) - len(sig))
    if len(conf) < len(window_df): conf += ["hold"] * (len(window_df) - len(conf))
    ref = hb.run_backtest(window_df.copy(), list(sig), list(conf), symbol=symbol,
                          tf="3m", backtest_days=30, use_risk_free=False,
                          risk_free_distance_pips=50.0, use_sl=True, sl_pips=sl_pips,
                          use_tp=True, tp_pips=tp_pips, close_opposite_position=False,
                          initial_balance=5000.0, position_size_mode="risk_percent",
                          fixed_lot_size=0.01, risk_percent=2, risk_based_on="initial")
    mine = harness_backtest(window_df, sig, conf, pip, pv_per_lot, mode="fixed",
                            fixed_sl_pips=sl_pips, fixed_tp_pips=tp_pips)
    eq = (ref["roi"] == mine["roi"] and ref["winrate"] == mine["winrate"] and
          ref["total_trades"] == mine["total_trades"] and
          ref["profit_factor"] == mine["profit_factor"])
    return eq, ref, mine


# ------------------------------------------------------------------ walk-forward
def walk_forward(windows, signal_fn, params_grid, select_metric="roi",
                 min_trades=10, engine=None):
    """Generic walk-forward shell (CP4/CP4b logic). windows[i] is IS of fold i,
       windows[i+1] is its OOS. params_grid: list of param dicts passed to
       signal_fn(wdf, params). engine(wdf, states, params) -> metrics dict.
       Only IS drives selection. Returns per-fold records + aggregate."""
    folds = []
    n = len(windows) - 1
    for f in range(n):
        is_w, oos_w = windows[f], windows[f + 1]
        is_table = []
        for params in params_grid:
            st = signal_fn(is_w, params)
            r = engine(is_w, st, params) if engine else None
            is_table.append({"params": params, "is": r})
        eligible = [t for t in is_table if t["is"] and t["is"].get("total_trades", 0) >= min_trades]
        if not eligible:
            folds.append({"fold": f + 1, "status": "THIN_IS", "is_table": is_table})
            continue
        best = max(eligible, key=lambda t: (t["is"][select_metric], t["is"].get("total_trades", 0)))
        oos_st = signal_fn(oos_w, best["params"])
        oos = engine(oos_w, oos_st, best["params"]) if engine else None
        folds.append({"fold": f + 1, "status": "OK", "selected_params": best["params"],
                      "is": best["is"], "oos": oos, "is_table": is_table})
    return folds
