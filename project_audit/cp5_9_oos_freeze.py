# cp5_9_oos_freeze.py — A2-v2 INDEPENDENT OOS FREEZE (archive period)
# Registered OOS-v2 definition (CP5_9_A2V2_PRE_REGISTRATION.md, fixed before
# any v2 evaluation): 6 x 14,400 M3 bars ending 2025-03-20 03:51 broker time
# (the bar immediately before the CP6 OOS start 03:54). This archive period
# was never fetched or analyzed by any phase; it is the only data left that is
# uncontaminated for a hypothesis designed after v1's CP6 OOS.
# TZ fix applied (CP6 v2 lesson): API bounds passed as broker_naive + 3:30.
# One bulk range fetch; integrity battery; manifest; abutment check.

import os, sys, json, hashlib, shutil
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")
SYMBOL, N_WINDOWS, BARS, TF_MIN = "XAUUSD.", 6, 14400, 3
TZ = timedelta(hours=3, minutes=30)


def T(b):
    return b + TZ


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


lines = []


def P(s):
    print(s)
    lines.append(s)


P("# CP5.9 — A2-v2 INDEPENDENT OOS DATA FREEZE (archive period)")
P("Generated: %s | registered definition: last bar = 2025-03-20 03:51 broker" % datetime.now().isoformat(timespec="seconds"))
P("  (abutting the CP6 OOS start); TZ-corrected bounds (+3:30) per CP6 v2 fix.")
P("")

import MetaTrader5 as mt5

if not mt5.initialize():
    P("## ABORTED: MT5 init failed: %s" % (mt5.last_error(),))
    with open(os.path.join(HERE, "CP5_9_OOS_FREEZE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(3)
try:
    info = mt5.symbol_info(SYMBOL)
    retrieved = datetime.now().isoformat(timespec="seconds")
    P("- MT5 %s | digits=%s | retrieved_at_local=%s" % (mt5.version(), info.digits, retrieved))
    raw = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M3,
                               T(datetime(2021, 6, 20)), T(datetime(2025, 3, 20, 3, 51)))
    if raw is None or len(raw) < BARS * N_WINDOWS:
        P("## ABORTED: insufficient history: %s rows" % (0 if raw is None else len(raw)))
        with open(os.path.join(HERE, "CP5_9_OOS_FREEZE.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        mt5.shutdown()
        sys.exit(3)
    P("- range fetch returned %d rows; took LAST %d" % (len(raw), BARS * N_WINDOWS))
    raw = raw[np.argsort(raw["time"])][-BARS * N_WINDOWS:]
    wins = []
    for w in range(N_WINDOWS):
        d = pd.DataFrame(raw[w * BARS:(w + 1) * BARS])
        d["time"] = pd.to_datetime(d["time"], unit="s")
        if "tick_volume" in d.columns and "volume" not in d.columns:
            d["volume"] = d["tick_volume"]
        wins.append(d.reset_index(drop=True))

    verdict, anomalies, metas, prev_last = "FROZEN", [], [], None
    for i, wdf in enumerate(wins, start=1):
        t = pd.to_datetime(wdf["time"])
        diffs = t.diff().dropna()
        inc = bool((diffs > pd.Timedelta(0)).all())
        dups = int(len(t) - t.nunique())
        g = diffs[diffs != pd.Timedelta(minutes=TF_MIN)]
        gaps = {}
        for d_ in g:
            m = int(d_.total_seconds() // 60)
            key = "daily_break" if m <= 240 else ("weekend" if m >= 1000 else "OTHER")
            gaps[key] = gaps.get(key, 0) + 1
            if key == "OTHER":
                anomalies.append("w%d unclassified gap %dmin" % (i, m))
        o, h_, l, c = (wdf[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        ohlc = bool(np.all(h_ >= np.maximum.reduce([o, c, l])) and
                    np.all(l <= np.minimum.reduce([o, c, h_])) and np.all(o > 0) and
                    np.all(h_ > 0) and np.all(l > 0) and np.all(c > 0))
        grid = bool((t.astype("int64") // 10**9 % 180 == 0).all())
        cont = None
        if prev_last is not None:
            cont = bool((t.iloc[0] - prev_last) == pd.Timedelta(minutes=TF_MIN))
            if not cont:
                anomalies.append("w%d not contiguous" % i)
        prev_last = t.iloc[-1]
        fname = "cp6v2_window_%d_df.csv" % i
        wdf.to_csv(os.path.join(CACHE, fname), index=False)
        sha = sha256_file(os.path.join(CACHE, fname))
        metas.append({"file": fname, "bars": len(wdf), "first": str(t.iloc[0]),
                      "last": str(t.iloc[-1]), "increasing": inc, "dups": dups,
                      "gaps": gaps, "ohlc_valid": ohlc, "grid_ok": grid,
                      "contiguous": cont, "sha256": sha})
        P("- OOSv2 window %d: bars=%d span=%s..%s inc=%s dups=%d gaps=%s ohlc=%s"
          " grid=%s cont=%s sha=%s" % (i, len(wdf), str(t.iloc[0])[:16],
                                       str(t.iloc[-1])[:16], inc, dups,
                                       json.dumps(gaps), ohlc, grid, cont, sha[:12]))
    t6 = pd.to_datetime(wins[-1]["time"])
    bridge = bool((pd.Timestamp("2025-03-20 03:54:00") - t6.iloc[-1]) == pd.Timedelta(minutes=TF_MIN))
    P("- abutment: OOSv2 last (%s) +3min == CP6 OOS first (2025-03-20 03:54): %s"
      % (t6.iloc[-1], bridge))
    if not bridge:
        anomalies.append("v2 OOS does not abut CP6 OOS start")
    if not all(m["bars"] == BARS and m["increasing"] and m["dups"] == 0 and
               m["ohlc_valid"] and m["grid_ok"] and m["contiguous"] in (None, True)
               for m in metas):
        verdict = "ANOMALY"
    combined = hashlib.sha256()
    for m in metas:
        combined.update(m["sha256"].encode())
    manifest = {"experiment": "CP5.9 OOS-v2 FREEZE", "created_local": retrieved,
                "definition": "6x14400 M3 bars ending 2025-03-20 03:51 broker",
                "windows": metas, "dataset_sha256_combined": combined.hexdigest(),
                "anomalies": anomalies, "verdict": verdict}
    with open(os.path.join(HERE, "CP5_9_OOS_FREEZE_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, default=str)
    P("")
    P("## OOS-v2 dataset identity: %s" % combined.hexdigest())
    P("## Verdict: %s | anomalies: %s" % (verdict, "; ".join(anomalies) if anomalies else "none"))
finally:
    mt5.shutdown()
    P("- MT5 closed (read-only).")

with open(os.path.join(HERE, "CP5_9_OOS_FREEZE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
sys.exit(0 if verdict == "FROZEN" else 4)
