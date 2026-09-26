"""Safe MT5 M1 historical-data exporter for Stage 7.1."""
from __future__ import annotations
import gzip, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
import MetaTrader5 as mt5
import pandas as pd
TIMEFRAME=mt5.TIMEFRAME_M1
CHUNK=int(os.getenv("MT5_BARS_PER_CHUNK","100000"))
SYMBOL=os.getenv("MT5_SYMBOL","XAUUSD")
OUT_DIR=Path(os.getenv("MT5_OUTPUT_DIR","data_export")); OUT_DIR.mkdir(parents=True,exist_ok=True)
def fail(message): raise SystemExit(f"BLOCKED: {message}")
def main():
    ok=mt5.initialize(path=os.getenv("MT5_TERMINAL_PATH")) if os.getenv("MT5_TERMINAL_PATH") else mt5.initialize()
    if not ok: fail(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        info=mt5.terminal_info()
        if info is None: fail(f"terminal_info unavailable: {mt5.last_error()}")
        symbol_info=mt5.symbol_info(SYMBOL)
        if symbol_info is None:
            candidates=[s.name for s in (mt5.symbols_get() or []) if "XAUUSD" in s.name.upper() or s.name.upper()=="GOLD"]
            fail(f"symbol {SYMBOL!r} not found. Candidates: {candidates}")
        if not symbol_info.visible and not mt5.symbol_select(SYMBOL,True): fail(f"could not select symbol {SYMBOL}: {mt5.last_error()}")
        frames=[]; start_pos=0
        while True:
            rates=mt5.copy_rates_from_pos(SYMBOL,TIMEFRAME,start_pos,CHUNK)
            if rates is None: fail(f"copy_rates_from_pos failed at start_pos={start_pos}: {mt5.last_error()}")
            if len(rates)==0: break
            frames.append(pd.DataFrame(rates))
            if len(rates)<CHUNK: break
            start_pos += len(rates)
        if not frames: fail("MT5 returned zero M1 bars")
        df=pd.concat(frames,ignore_index=True).drop_duplicates(subset=["time"],keep="last").sort_values("time").reset_index(drop=True)
        df["timestamp"]=pd.to_datetime(df["time"],unit="s",utc=True); df=df.drop(columns=["time"]).rename(columns={"tick_volume":"volume"})
        df=df[[c for c in ["timestamp","open","high","low","close","volume","spread","real_volume"] if c in df.columns]]
        data_path=OUT_DIR/f"{SYMBOL}_M1.csv.gz"; metadata_path=OUT_DIR/f"{SYMBOL}_M1.metadata.json"
        with gzip.open(data_path,"wt",encoding="utf-8",newline="") as fh: df.to_csv(fh,index=False)
        sha=hashlib.sha256(data_path.read_bytes()).hexdigest()
        metadata={"symbol":SYMBOL,"timeframe":"M1","timezone":"UTC","rows":int(len(df)),"start":df["timestamp"].iloc[0].isoformat(),"end":df["timestamp"].iloc[-1].isoformat(),"source":"MetaTrader 5 terminal historical bars","exported_at":datetime.now(timezone.utc).isoformat(),"sha256":sha,"terminal_build":getattr(info,"build",None),"no_orders_sent":True}
        metadata_path.write_text(json.dumps(metadata,indent=2),encoding="utf-8"); print(json.dumps(metadata,indent=2))
    finally: mt5.shutdown()
if __name__=="__main__": main()