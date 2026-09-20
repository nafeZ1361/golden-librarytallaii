# cp6_oos_freeze.py — CP6 INDEPENDENT OOS DATA FREEZE
# REGISTERED OOS DEFINITION (fixed BEFORE any evaluation, per CP6 gate):
#   The CP5 frozen dataset (be4fa581...) spans 2025-12-10 21:39 .. 2026-09-04
#   17:30 broker time and was the ONLY data used in design/selection/review
#   (CP5.0..CP5.8). A temporally-forward independent sample barely exists (the
#   freeze happened Friday evening; market closed for the weekend), therefore:
#   PRIMARY OOS  = the 6 x 14,400 M3 bars IMMEDIATELY PRECEDING the frozen
#                  dataset start boundary (last bar = 2025-12-10 21:36). This
#                  period was never fetched or used in any audited phase.
#   SUPPLEMENT   = the forward fragment strictly after 2026-09-04 17:30
#                  (fetched and reported, but statistically underpowered —
#                  recorded as such, never merged into the primary OOS).
#   No tuning on any of it: A1/A2 run with frozen parameters only, one-shot.
# Acquisition: MT5 read-only, ONE bulk range fetch + one fragment fetch,
# then frozen to project_audit/stability_windows_cache/cp6_window_{i}_df.csv.
# Integrity battery per window + boundary continuity against the frozen set.

import os, sys, json, hashlib, subprocess, shutil
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
CACHE = os.path.join(HERE, "stability_windows_cache")
SYMBOL = "XAUUSD."
N_WINDOWS, BARS, TF_MIN = 6, 14400, 3
FROZEN_FIRST = "2025-12-10 21:39:00"
FROZEN_LAST = "2026-09-04 17:30:00"
# TZ FIX (v2): the MetaTrader5 API interprets naive datetime bounds in the LOCAL
# timezone (Tehran, UTC+3:30) and converts to UTC, while broker bar timestamps
# are UTC-naive. Two exact observations: requested 17:33 -> first bar 14:03;
# requested to 21:36 -> last bar 18:06 (both exactly -3:30). Diagnostic fetch
# with +3:30 bounds proved broker history around the boundary is CONTINUOUS
# (only the normal 63-min daily break). Therefore all date bounds below are
# passed as broker_naive + 3:30. v1 artifacts (fetched with the buggy bounds)
# are preserved as *_superseded (rule 7).
TZ = timedelta(hours=3, minutes=30)


def T(broker_naive):
    return broker_naive + TZ

lines = []


def P(s):
    print(s)
    lines.append(s)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def ohlc_valid(df):
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    return bool(np.all(h >= np.maximum.reduce([o, c, l])) and
                np.all(l <= np.minimum.reduce([o, c, h])) and np.all(o > 0) and
                np.all(h > 0) and np.all(l > 0) and np.all(c > 0))


P("# CP6 — INDEPENDENT OOS DATA FREEZE (v2 — timezone-corrected bounds)")
P("Generated: %s | REGISTERED OOS DEFINITION (before any evaluation):" % datetime.now().isoformat(timespec="seconds"))
P("- PRIMARY OOS = 6 x 14,400 M3 bars immediately PRECEDING the frozen CP5"
  " boundary (last OOS bar = 2025-12-10 21:36; frozen first = 2025-12-10 21:39).")
P("  This period was never fetched/used in any audited phase (all prior phases"
  " used 'latest-N' windows starting 2025-12-09/10).")
P("- SUPPLEMENT = forward fragment strictly after 2026-09-04 17:30 (underpowered,"
  " reported separately, never merged).")
P("- One-shot evaluation with frozen parameters; no tuning; no optimization.")
P("")
P("## v1 -> v2 defect record (error-handler loop)")
P("- v1 bounds were passed broker-naive; the API interprets them Tehran-naive and"
  " converts to UTC (-3:30), so v1 data ended at broker 18:06 and the fragment"
  " overlapped the frozen period. CLASS: audit-script error (timezone).")
P("- Diagnostic with +3:30 bounds proved broker history around the boundary is"
  " continuous (only the normal 63-min daily break) -> the hole was an artifact.")
P("- v1 artifacts preserved as *_superseded; v2 = complete re-acquisition with"
  " corrected bounds (authorized: the v1 freeze failed its own registered"
  " definition; no scientific result existed on v1).")
P("- Related historical note: CP4d's M15/H1 fetch used the same naive-bound API"
  " call (same -3:30 shift, span 3.5h earlier than intended). Impact: none on"
  " its verdict (all CIs wide and included 50%); recorded for provenance.")
P("")

import MetaTrader5 as mt5

if not mt5.initialize():
    P("## ABORTED: MT5 initialize failed: %s" % (mt5.last_error(),))
    with open(os.path.join(HERE, "CP6_OOS_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(3)
try:
    info = mt5.symbol_info(SYMBOL)
    P("- MT5 %s | symbol digits=%s point=%s" % (mt5.version(), info.digits, info.point))
    retrieved = datetime.now().isoformat(timespec="seconds")
    P("- retrieved_at_local: %s | timezone: naive broker-server (never converted)" % retrieved)

    # ---- preserve v1 artifacts (rule 7) ------------------------------------
    for i in range(1, N_WINDOWS + 1):
        old = os.path.join(CACHE, "cp6_window_%d_df.csv" % i)
        if os.path.exists(old):
            shutil.move(old, os.path.join(CACHE, "cp6_window_%d_df_v1_superseded.csv" % i))
    for old, new in (("cp6_forward_fragment.csv", "cp6_forward_fragment_v1_superseded.csv"),
                     ("CP6_OOS_DATA_FREEZE_manifest.json", "CP6_OOS_DATA_FREEZE_manifest_v1_superseded.json"),
                     ("CP6_OOS_DATA_FREEZE.md", "CP6_OOS_DATA_FREEZE_v1_superseded.md")):
        op, np_ = os.path.join(CACHE, old), os.path.join(CACHE, new)
        op2 = os.path.join(HERE, old)
        if os.path.exists(op):
            shutil.move(op, np_)
        elif os.path.exists(op2):
            shutil.move(op2, os.path.join(CACHE, new))

    # ---- primary OOS bulk fetch (ONE range fetch, ascending; TZ-corrected) --
    raw = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M3,
                               T(datetime(2023, 12, 10)), T(datetime(2025, 12, 10, 21, 38)))
    if raw is None or len(raw) < BARS * N_WINDOWS:
        P("## ABORTED: insufficient OOS history: %s rows (need >= %d)"
          % (0 if raw is None else len(raw), BARS * N_WINDOWS))
        with open(os.path.join(HERE, "CP6_OOS_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        mt5.shutdown()
        sys.exit(3)
    raw = raw[np.argsort(raw["time"])][-BARS * N_WINDOWS:]
    P("- primary OOS fetch: requested range 2023-12-10..2025-12-10 21:36; got %d rows;"
      " took LAST %d" % (len(raw), BARS * N_WINDOWS))

    wins = []
    for w in range(N_WINDOWS):
        sl = raw[w * BARS:(w + 1) * BARS]
        d = pd.DataFrame(sl)
        d["time"] = pd.to_datetime(d["time"], unit="s")
        if "tick_volume" in d.columns and "volume" not in d.columns:
            d["volume"] = d["tick_volume"]
        wins.append(d.reset_index(drop=True))

    # ---- forward fragment (TZ-corrected: broker 17:33 -> Tehran 21:03) ------
    frag = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M3,
                                T(datetime(2026, 9, 4, 17, 33)), T(datetime(2026, 9, 6, 23, 59)))
    frag_df = None
    if frag is not None and len(frag) > 0:
        frag_df = pd.DataFrame(frag[np.argsort(frag["time"])]).reset_index(drop=True)
        frag_df["time"] = pd.to_datetime(frag_df["time"], unit="s")
        if "tick_volume" in frag_df.columns and "volume" not in frag_df.columns:
            frag_df["volume"] = frag_df["tick_volume"]
    P("- forward fragment: %d bars after %s" % (0 if frag_df is None else len(frag_df), FROZEN_LAST))

    # ---- integrity battery + freeze ----------------------------------------
    verdict, anomalies = "FROZEN", []
    metas = []
    prev_last = None
    frozen_first = pd.Timestamp(FROZEN_FIRST)
    for i, wdf in enumerate(wins, start=1):
        t = pd.to_datetime(wdf["time"])
        n = len(wdf)
        diffs = t.diff().dropna()
        inc = bool((diffs > pd.Timedelta(0)).all())
        dups = int(n - t.nunique())
        gap_rows = diffs[diffs != pd.Timedelta(minutes=TF_MIN)]
        gaps = {}
        for d_ in gap_rows:
            m = int(d_.total_seconds() // 60)
            key = "daily_break" if m <= 240 else ("weekend" if m >= 1000 else "OTHER")
            gaps[key] = gaps.get(key, 0) + 1
            if key == "OTHER":
                anomalies.append("window %d unclassified gap %d min" % (i, m))
        grid_ok = bool((t.astype("int64") // 10**9 % 180 == 0).all())
        ohlc_ok = ohlc_valid(wdf)
        nan_n = int(sum(np.sum(~np.isfinite(wdf[k].to_numpy(dtype=float)))
                        for k in ("open", "high", "low", "close")))
        contiguous = None
        if prev_last is not None:
            contiguous = bool((t.iloc[0] - prev_last) == pd.Timedelta(minutes=TF_MIN))
            if not contiguous:
                anomalies.append("window %d not contiguous" % i)
        prev_last = t.iloc[-1]
        fname = "cp6_window_%d_df.csv" % i
        fpath = os.path.join(CACHE, fname)
        wdf.to_csv(fpath, index=False)
        sha = sha256_file(fpath)
        metas.append({"file": fname, "window_id": i, "symbol": SYMBOL, "timeframe": "M3",
                      "bars": n, "first": str(t.iloc[0]), "last": str(t.iloc[-1]),
                      "increasing": inc, "duplicates": dups, "gaps": gaps,
                      "ohlc_valid": ohlc_ok, "nan_inf": nan_n, "grid_ok": grid_ok,
                      "contiguous": contiguous, "sha256": sha})
        P("- OOS window %d: bars=%d span=%s..%s inc=%s dups=%d gaps=%s ohlc=%s nan=%d"
          " grid=%s cont=%s sha=%s" % (i, n, str(t.iloc[0])[:16], str(t.iloc[-1])[:16],
                                       inc, dups, json.dumps(gaps), ohlc_ok, nan_n,
                                       grid_ok, contiguous, sha[:12]))
    # boundary continuity with the frozen dataset
    t6 = pd.to_datetime(wins[-1]["time"])
    t1 = pd.to_datetime(wins[0]["time"])
    bridge = bool((frozen_first - t6.iloc[-1]) == pd.Timedelta(minutes=TF_MIN))
    P("- boundary continuity: OOS last (%s) +3min == frozen first (%s): %s"
      % (t6.iloc[-1], frozen_first, bridge))
    if not bridge:
        anomalies.append("OOS does not abut the frozen boundary")
    if not all(m["bars"] == BARS and m["increasing"] and m["duplicates"] == 0 and
               m["ohlc_valid"] and m["nan_inf"] == 0 and m["grid_ok"] and
               m["contiguous"] in (None, True) for m in metas):
        verdict = "ANOMALY"
    # forward fragment integrity (light) + freeze
    frag_meta = None
    if frag_df is not None and len(frag_df) > 0:
        ft = pd.to_datetime(frag_df["time"])
        f_after = bool((ft > pd.Timestamp(FROZEN_LAST)).all())
        frag_path = os.path.join(CACHE, "cp6_forward_fragment.csv")
        frag_df.to_csv(frag_path, index=False)
        frag_meta = {"file": "cp6_forward_fragment.csv", "bars": len(frag_df),
                     "first": str(ft.iloc[0]), "last": str(ft.iloc[-1]),
                     "all_after_frozen_last": f_after,
                     "sha256": sha256_file(frag_path)}
        P("- fragment: %d bars %s..%s all_after_frozen=%s sha=%s"
          % (len(frag_df), str(ft.iloc[0])[:16], str(ft.iloc[-1])[:16], f_after,
             frag_meta["sha256"][:12]))
        if not f_after:
            anomalies.append("fragment contains bars at/before frozen last")
    combined = hashlib.sha256()
    for m in metas:
        combined.update(m["sha256"].encode())
    manifest = {"experiment": "CP6 OOS FREEZE", "created_local": retrieved,
                "registered_oos_definition": "6x14400 bars preceding frozen boundary"
                " + forward fragment supplement",
                "frozen_boundary": {"cp5_first": FROZEN_FIRST, "cp5_last": FROZEN_LAST},
                "mt5_symbol_info": {"digits": info.digits, "point": info.point},
                "windows": metas, "forward_fragment": frag_meta,
                "dataset_sha256_combined": combined.hexdigest(),
                "anomalies": anomalies, "verdict": verdict}
    with open(os.path.join(HERE, "CP6_OOS_DATA_FREEZE_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, default=str)
    P("")
    P("## OOS dataset identity: %s" % combined.hexdigest())
    P("## Verdict: %s | anomalies: %s" % (verdict, "; ".join(anomalies) if anomalies else "none"))
finally:
    mt5.shutdown()
    P("- MT5 closed (read-only).")

with open(os.path.join(HERE, "CP6_OOS_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
sys.exit(0 if verdict == "FROZEN" else 4)
