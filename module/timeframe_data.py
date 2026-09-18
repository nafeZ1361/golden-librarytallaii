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
