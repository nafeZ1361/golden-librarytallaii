# cycle_r1_oos_freeze.py — CYCLE-R1 SHARED OOS FREEZE (DS-R1-RESERVE)
# Registered definition (CYCLE_R1_CONTRACT.md): 6 x 14,400 M3 bars ending
# 2024-06-26 11:18 broker (bar immediately before the DS-ARCH-OOS start
# 2025-03-20... no: before 2024-06-26 11:21 = DS-ARCH start). Period
# 2021-06-26..2024-06-26 11:18 — NEVER fetched/analyzed by any phase.
# TZ-corrected bounds (+3:30) per CP6 v2 rule. One bulk fetch; battery; manifest.

import os, sys, json, hashlib
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
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


P("# CYCLE-R1 — SHARED OOS DATA FREEZE (DS-R1-RESERVE)")
P("Generated: %s | registered: 6 x 14,400 M3 bars ending 2024-06-26 11:18" % datetime.now().isoformat(timespec="seconds"))
P("  broker (abutting DS-ARCH-OOS start 11:21); TZ-corrected bounds; one-shot")
P("  consumption by CYCLE-R1 (H-V3-1 fade + H-V3-2 session-conditioned).")

import MetaTrader5 as mt5

verdict, anomalies = "FROZEN", []
if not mt5.initialize():
    P("## ABORTED: MT5 init failed: %s" % (mt5.last_error(),))
    with open(os.path.join(HERE, "CYCLE_R1_OOS_FREEZE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(3)
try:
    info = mt5.symbol_info(SYMBOL)
    retrieved = datetime.now().isoformat(timespec="seconds")
    P("- MT5 %s | digits=%s | retrieved_at_local=%s" % (mt5.version(), info.digits, retrieved))
    raw = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M3,
                               T(datetime(2021, 6, 26)), T(datetime(2024, 6, 26, 11, 18)))
    if raw is None or len(raw) < BARS * N_WINDOWS:
        P("## ABORTED: insufficient history: %s rows" % (0 if raw is None else len(raw)))
        with open(os.path.join(HERE, "CYCLE_R1_OOS_FREEZE.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        mt5.shutdown()
        sys.exit(3)
    P("- range fetch returned %d rows; took LAST %d" % (len(raw), BARS * N_WINDOWS))
    raw = raw[np.argsort(raw["time"])][-BARS * N_WINDOWS:]
    metas, prev_last = [], None
    for w in range(N_WINDOWS):
        d = pd.DataFrame(raw[w * BARS:(w + 1) * BARS])
        d["time"] = pd.to_datetime(d["time"], unit="s")
        if "tick_volume" in d.columns and "volume" not in d.columns:
            d["volume"] = d["tick_volume"]
        t = pd.to_datetime(d["time"])
        diffs = t.diff().dropna()
        inc = bool((diffs > pd.Timedelta(0)).all())
        dups = int(len(t) - t.nunique())
        g = diffs[diffs != pd.Timedelta(minutes=TF_MIN)]
        gaps = {}
        for d_ in g:
            mm = int(d_.total_seconds() // 60)
            key = "daily_break" if mm <= 240 else ("weekend" if mm >= 1000 else "OTHER")
            gaps[key] = gaps.get(key, 0) + 1
            if key == "OTHER":
                anomalies.append("w%d unclassified gap %dmin" % (w + 1, mm))
        o, h_, l, c = (d[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        ohlc = bool(np.all(h_ >= np.maximum.reduce([o, c, l])) and
                    np.all(l <= np.minimum.reduce([o, c, h_])) and np.all(o > 0) and
                    np.all(h_ > 0) and np.all(l > 0) and np.all(c > 0))
        grid = bool((t.astype("int64") // 10**9 % 180 == 0).all())
        cont = None
        if prev_last is not None:
            cont = bool((t.iloc[0] - prev_last) == pd.Timedelta(minutes=TF_MIN))
            if not cont:
                anomalies.append("w%d not contiguous" % (w + 1))
        prev_last = t.iloc[-1]
        fname = "r1_window_%d_df.csv" % (w + 1)
        d.to_csv(os.path.join(CACHE, fname), index=False)
        sha = sha256_file(os.path.join(CACHE, fname))
        metas.append({"file": fname, "bars": len(d), "first": str(t.iloc[0]),
                      "last": str(t.iloc[-1]), "increasing": inc, "dups": dups,
                      "gaps": gaps, "ohlc_valid": ohlc, "grid_ok": grid,
                      "contiguous": cont, "sha256": sha})
        P("- window %d: bars=%d span=%s..%s inc=%s dups=%d gaps=%s ohlc=%s grid=%s"
          " cont=%s sha=%s" % (w + 1, len(d), str(t.iloc[0])[:16], str(t.iloc[-1])[:16],
                               inc, dups, json.dumps(gaps), ohlc, grid, cont, sha[:12]))
    t6 = pd.to_datetime(metas[-1]["last"])
    bridge = bool((pd.Timestamp("2024-06-26 11:21:00") - t6) == pd.Timedelta(minutes=TF_MIN))
    P("- abutment: R1 last (%s) +3min == DS-ARCH start (2024-06-26 11:21): %s"
      % (t6, bridge))
    if not bridge:
        anomalies.append("R1 does not abut DS-ARCH start")
    if not all(mm["bars"] == BARS and mm["increasing"] and mm["dups"] == 0 and
               mm["ohlc_valid"] and mm["grid_ok"] and mm["contiguous"] in (None, True)
               for mm in metas):
        verdict = "ANOMALY"
    combined = hashlib.sha256()
    for mm in metas:
        combined.update(mm["sha256"].encode())
    manifest = {"experiment": "CYCLE-R1 OOS FREEZE", "created_local": retrieved,
                "windows": metas, "dataset_sha256_combined": combined.hexdigest(),
                "anomalies": anomalies, "verdict": verdict}
    with open(os.path.join(HERE, "CYCLE_R1_OOS_FREEZE_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, default=str)
    P("")
    P("## R1 dataset identity: %s" % combined.hexdigest())
    P("## Verdict: %s | anomalies: %s" % (verdict, "; ".join(anomalies) if anomalies else "none"))
finally:
    mt5.shutdown()
    P("- MT5 closed (read-only).")

with open(os.path.join(HERE, "CYCLE_R1_OOS_FREEZE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
sys.exit(0 if verdict == "FROZEN" else 4)
