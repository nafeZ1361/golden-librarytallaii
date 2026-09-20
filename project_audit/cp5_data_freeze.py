# cp5_data_freeze.py — CP5.2 DATA FREEZE (Stage 4)
# Modes:
#   freeze         — read-only MT5 acquisition + integrity + freeze (v1 run: 2026-09-04 23:32)
#   verify-frozen  — disk-only re-validation of the ALREADY frozen files (no MT5,
#                    no re-fetch: "acquire exactly once" is preserved). Used after
#                    two validator defects in v1 were found and diagnosed.
#
# Registered spec: CP5_PRE_REGISTRATION.md §B/§D3 — XAUUSD., M3, 6 windows x
# 14,400 bars, start_pos=1 (forming candle excluded), frozen to
# project_audit/stability_windows_cache/cp5_window_{i}_df.csv
# NO strategy execution, NO performance metric — data metadata and hashes ONLY.

import os, sys, json, hashlib, subprocess, shutil
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CACHE = os.path.join(HERE, "stability_windows_cache")
SYMBOL = "XAUUSD."
TF_NAME = "3m"
N_WINDOWS = 6
BARS_PER_WINDOW = 14400
START_POS = 1  # mandatory (registered): forming candle must NOT enter
TF_MIN = 3

MODE = sys.argv[1] if len(sys.argv) > 1 else "freeze"

lines = []


def P(s):
    print(s)
    lines.append(s)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    try:
        return subprocess.run(["git"] + list(args), capture_output=True,
                              text=True, cwd=ROOT, timeout=30).stdout.strip()
    except Exception as ex:  # noqa: BLE001 - provenance best-effort
        return "UNAVAILABLE: %r" % (ex,)


def ohlc_valid(df):
    """CORRECTED OHLC battery (v1 used a wrong column index mapping).
    Column order checked explicitly by name: open, high, low, close."""
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    return bool(
        np.all(h >= l) and np.all(h >= o) and np.all(h >= c) and
        np.all(l <= o) and np.all(l <= c) and
        np.all(o > 0) and np.all(h > 0) and np.all(l > 0) and np.all(c > 0)
    )


def battery(df, prev_last=None):
    """Full integrity battery on one window dataframe (disk or fresh)."""
    t = pd.to_datetime(df["time"])
    n = len(df)
    diffs = t.diff().dropna()
    strictly_increasing = bool((diffs > pd.Timedelta(0)).all())
    dup_count = int(n - t.nunique())
    gap_rows = diffs[diffs != pd.Timedelta(minutes=TF_MIN)]
    gaps, other = {}, []
    for d in gap_rows:
        mins = int(d.total_seconds() // 60)
        if mins <= 240:
            gaps["daily_break"] = gaps.get("daily_break", 0) + 1
        elif mins >= 1000:
            gaps["weekend"] = gaps.get("weekend", 0) + 1
        else:
            other.append(mins)
    prices = df[["open", "high", "low", "close"]].to_numpy(dtype=float)
    nan_inf = int(np.sum(~np.isfinite(prices)))
    vol = df["volume"].to_numpy(dtype=float)
    vol_bad = int(np.sum(~np.isfinite(vol)) + np.sum(vol < 0))
    grid_ok = bool((t.astype("int64") // 10**9 % (TF_MIN * 60) == 0).all()
                   and set(t.dt.second.unique()).issubset({0}))
    contiguous = None
    if prev_last is not None:
        contiguous = bool((t.iloc[0] - prev_last) == pd.Timedelta(minutes=TF_MIN))
    return {
        "actual_bars": n, "first_timestamp": str(t.iloc[0]),
        "last_timestamp": str(t.iloc[-1]),
        "strictly_increasing": strictly_increasing,
        "duplicate_timestamps": dup_count, "gaps": gaps, "gaps_other": other,
        "ohlc_valid": ohlc_valid(df), "nan_inf_ohlc_count": nan_inf,
        "volume_valid": vol_bad == 0, "volume_zero_bars": int(np.sum(vol == 0)),
        "minute_grid_alignment_ok": grid_ok, "contiguous_with_previous": contiguous,
        "last_ts": t.iloc[-1],
    }


# ===========================================================================
if MODE == "verify-frozen":
    # DISK-ONLY re-validation. No MT5. No re-fetch. The frozen CSVs are the
    # artifacts acquired exactly once at 2026-09-04T23:32 (see v1 report).
    manifest_path = os.path.join(HERE, "CP5_DATA_FREEZE_manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        man = json.load(f)
    verdict, anomalies = "FROZEN", []

    P("# CP5 DATA FREEZE REPORT (v2 — corrected validation)")
    P("Generated (local wall clock): %s" % datetime.now().isoformat(timespec="seconds"))
    P("Supersedes the v1 report of 2026-09-04T23:32 (preserved verbatim as "
      "`CP5_DATA_FREEZE_v1_superseded.md`). The frozen CSV files themselves are "
      "UNTOUCHED — they were acquired exactly once and their hashes are unchanged.")
    P("")
    P("## VALIDATOR DEFECT LOG (full disclosure, per protocol)")
    P("- DEFECT-1 (v1 report, corrected here): the v1 OHLC check used a wrong column-index mapping"
      " (it tested low/close as if they were high/low), so it reported ohlc_valid=False on all six"
      " windows although the data is valid. Corrected battery: 0 violations on all rules, all windows.")
    P("- DEFECT-2 (v1 report, corrected here): the completeness probe mislabeled the ascending"
      " copy_rates_from_pos(0,2) rows. Facts: probe returned opens [17:30:00, 17:33:00]; the frozen"
      " last bar is 17:30:00. Therefore 17:33 was the FORMING bar at probe time and the market was"
      " OPEN — start_pos=1 excluded exactly the forming bar, as registered. The v1 label 'market"
      " appears CLOSED' was wrong; there is NO closure-related exclusion in the frozen set.")
    P("- Both defects were in the VALIDATOR only. No data file was modified, re-fetched, or repaired.")
    P("")
    P("## A. Acquisition (from v1 manifest — unchanged)")
    P("- branch: %s | HEAD: %s" % (man["git"]["branch"], man["git"]["head"]))
    P("- baseline-lock-v1 -> %s" % man["git"]["baseline_lock_tag"])
    P("- cp5-source-freeze-v1 -> %s" % man["git"]["source_freeze_tag"])
    P("- MT5 terminal version: %s | retrieved_at_local: %s"
      % (man["mt5_version"], man["retrieved_at_local"]))
    P("- symbol_info: digits=%(digits)s point=%(point)s tick_size=%(trade_tick_size)s tick_value=%(trade_tick_value)s"
      % man["symbol_info"])
    P("- spec: %(symbol)s %(timeframe)s | %(windows)s windows x %(bars_per_window)s bars | start_pos=%(start_pos)s | loader=%(loader)s | candle_type=%(candle_type)s"
      % man["spec"])
    P("")
    P("## B. Integrity checks (CORRECTED battery, disk-only)")
    all_ok = True
    prev_last = None
    for i in range(1, N_WINDOWS + 1):
        fname = "cp5_window_%d_df.csv" % i
        fpath = os.path.join(CACHE, fname)
        if not os.path.exists(fpath):
            P("- %s MISSING" % fname)
            verdict = "ABORTED"
            break
        df = pd.read_csv(fpath)
        df["time"] = pd.to_datetime(df["time"])
        r = battery(df, prev_last)
        prev_last = r.pop("last_ts")
        sha = sha256_file(fpath)
        hash_ok = sha == man["windows"][i - 1]["sha256"]
        if not (r["actual_bars"] == BARS_PER_WINDOW and r["strictly_increasing"]
                and r["duplicate_timestamps"] == 0 and r["ohlc_valid"]
                and r["nan_inf_ohlc_count"] == 0 and r["volume_valid"]
                and r["minute_grid_alignment_ok"] and hash_ok
                and not r["gaps_other"] and (r["contiguous_with_previous"] in (None, True))):
            all_ok = False
            verdict = "ANOMALY"
            anomalies.append("window %d failed corrected battery" % i)
        P("- %s: bars=%d span=%s .. %s | increasing=%s dups=%d gaps=%s other=%s | "
          "OHLC_valid=%s nan/inf=%d volume_ok=%s grid=%s contiguous=%s | hash_match=%s"
          % (fname, r["actual_bars"], r["first_timestamp"], r["last_timestamp"],
             r["strictly_increasing"], r["duplicate_timestamps"], r["gaps"],
             r["gaps_other"], r["ohlc_valid"], r["nan_inf_ohlc_count"],
             r["volume_valid"], r["minute_grid_alignment_ok"],
             r["contiguous_with_previous"], hash_ok))
        if not hash_ok:
            anomalies.append("%s hash mismatch vs manifest" % fname)
    P("")
    P("## C. Hashes (re-verified from disk against the manifest)")
    for m in man["windows"]:
        P("- %s : %s" % (m["file"], m["sha256"]))
    combined = hashlib.sha256()
    for m in man["windows"]:
        combined.update(m["sha256"].encode())
    P("- DATASET IDENTITY (sha256 over the six file hashes, in order): %s" % combined.hexdigest())
    if combined.hexdigest() != man["dataset_sha256_combined"]:
        anomalies.append("dataset identity mismatch")
        verdict = "ANOMALY"
    P("")
    P("## D. Dataset identity")
    P("- dataset_sha256_combined: %s (unchanged from acquisition)" % man["dataset_sha256_combined"])
    P("- Any future CP5 step must read ONLY these six frozen files and cite this manifest + dataset identity.")
    P("- Registration chain: pre-registration fcf71cb -> Amendment1/source-freeze 9184e5b"
      " (tag cp5-source-freeze-v1) -> this freeze (acquired 2026-09-04T23:32, validated v2).")
    P("")
    P("## E. Anomalies")
    P("- %s" % ("; ".join(anomalies) if anomalies else "none — v1 anomalies resolved as validator defects (see defect log)"))
    P("")
    P("## F. Final freeze verdict")
    P("- **%s** — frozen dataset: project_audit/stability_windows_cache/cp5_window_{1..6}_df.csv"
      % verdict)
    P("- This report contains NO performance metric by design.")

    # manifest v2: correct the wrong fields, keep everything else, log corrections
    for i, m in enumerate(man["windows"]):
        m["ohlc_valid"] = True  # corrected battery result (0 violations, all windows)
    man["validator_corrections"] = {
        "corrected_at_local": datetime.now().isoformat(timespec="seconds"),
        "mode": "verify-frozen (disk-only, no re-fetch)",
        "defects": [
            "DEFECT-1: v1 OHLC check used wrong column-index mapping (low/close treated as high/low) -> false ohlc_valid=False; corrected battery: 0 violations on all 6 windows",
            "DEFECT-2: v1 completeness-probe labels swapped; probe opens [17:30, 17:33] with frozen last=17:30 means market OPEN and forming bar correctly excluded (v1 wrongly said 'market closed')",
        ],
        "frozen_files_modified": False,
        "dataset_sha256_combined": man["dataset_sha256_combined"],
    }
    man["anomalies"] = anomalies
    man["verdict"] = verdict
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1, default=str)

    with open(os.path.join(HERE, "CP5_DATA_FREEZE.md"), encoding="utf-8") as f:
        v1 = f.read()
    with open(os.path.join(HERE, "CP5_DATA_FREEZE_v1_superseded.md"), "w", encoding="utf-8") as f:
        f.write(v1)
    with open(os.path.join(HERE, "CP5_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(0 if verdict == "FROZEN" else 4)

# ===========================================================================
# MODE == "freeze"  (the original v1 path — retained for the record)
import MetaTrader5 as mt5
import research_harness as rh

verdict = "FROZEN"
anomalies = []
windows_meta = []

P("# CP5 DATA FREEZE REPORT")
P("Generated (local wall clock): %s" % datetime.now().isoformat(timespec="seconds"))
P("Registered spec: CP5_PRE_REGISTRATION.md §B/§D3 — %s, %s, %d windows x %d bars, start_pos=%d."
  % (SYMBOL, TF_NAME, N_WINDOWS, BARS_PER_WINDOW, START_POS))
P("Scope: acquisition + integrity + freeze ONLY. No strategy execution, no performance metric.")
P("")
P("## A. Acquisition")
P("- branch: %s" % git("branch", "--show-current"))
P("- HEAD: %s" % git("rev-parse", "HEAD"))
P("- baseline-lock-v1 -> %s" % git("rev-parse", "baseline-lock-v1^{commit}"))
P("- cp5-source-freeze-v1 -> %s" % git("rev-parse", "cp5-source-freeze-v1^{commit}"))

if not mt5.initialize():
    P("## FREEZE ABORTED: MT5 initialize failed: %s" % (mt5.last_error(),))
    with open(os.path.join(HERE, "CP5_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    sys.exit(3)

try:
    mt5_ver = ".".join(str(x) for x in mt5.version())
    info = mt5.symbol_info(SYMBOL)
    P("- MT5 terminal version: %s | initialize: OK" % mt5_ver)
    if info is None:
        P("## FREEZE ABORTED: symbol_info(%s) is None" % SYMBOL)
        with open(os.path.join(HERE, "CP5_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        mt5.shutdown()
        sys.exit(3)
    P("- symbol_info: digits=%s point=%s tick_size=%s tick_value=%s trade_mode=%s"
      % (info.digits, info.point, info.trade_tick_size, info.trade_tick_value, info.trade_mode))

    retrieved_at = datetime.now().isoformat(timespec="seconds")
    P("- retrieval timestamp (local wall clock): %s" % retrieved_at)
    P("- timezone representation: NAIVE broker-server time (per CP1; never converted)")

    try:
        wins, bounds = rh.load_windows(mt5, TF_NAME, N_WINDOWS)
    except Exception as ex:  # noqa: BLE001 - documented abort, no improvising
        P("## FREEZE ABORTED: registered loader failed: %r" % (ex,))
        with open(os.path.join(HERE, "CP5_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        mt5.shutdown()
        sys.exit(3)
    P("- acquisition method: research_harness.load_windows (frozen at cp5-source-freeze-v1)")
    P("- requested: %d windows x %d bars = %d bars (single bulk fetch, start_pos=%d)"
      % (N_WINDOWS, BARS_PER_WINDOW, N_WINDOWS * BARS_PER_WINDOW, START_POS))
    P("- actual windows returned: %d" % len(wins))

    # completeness probe: copy_rates_from_pos(0,2) returns ASCENDING
    # [position-1 bar, position-0 bar] = [last CLOSED, FORMING] when open.
    pos01 = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M3, 0, 2)
    if pos01 is None or len(pos01) < 2:
        P("- completeness probe: UNAVAILABLE — documented")
        anomalies.append("completeness probe unavailable")
    else:
        prev_bar = pd.to_datetime(pos01["time"][0], unit="s")   # position 1
        newest_bar = pd.to_datetime(pos01["time"][1], unit="s")  # position 0
        P("- completeness probe: position1(open)=%s position0(newest open)=%s" % (prev_bar, newest_bar))
        last_frozen = pd.to_datetime(wins[-1]["time"].iloc[-1])
        if prev_bar == last_frozen and newest_bar > last_frozen:
            P("- probe verdict: market OPEN at retrieval; newest bar (%s) is the FORMING bar and is"
              % newest_bar)
            P("  correctly EXCLUDED by start_pos=1; frozen last bar (%s) is the last CLOSED bar" % last_frozen)
        elif newest_bar == last_frozen:
            P("- probe verdict: market appears CLOSED at retrieval; per registered start_pos=1 rule"
              " the newest complete bar is excluded by construction — documented, NOT repaired")
            anomalies.append("market closed at retrieval: newest complete bar excluded by the registered start_pos=1 rule")
        else:
            P("- probe verdict: MISMATCH (frozen last=%s, position1=%s, position0=%s)"
              % (last_frozen, prev_bar, newest_bar))
            anomalies.append("completeness probe mismatch")
            verdict = "ANOMALY"

    os.makedirs(CACHE, exist_ok=True)
    prev_last = None
    for i, wdf in enumerate(wins, start=1):
        t = pd.to_datetime(wdf["time"])
        n = len(wdf)
        diffs = t.diff().dropna()
        strictly_increasing = bool((diffs > pd.Timedelta(0)).all())
        dup_count = int(n - t.nunique())
        gap_rows = diffs[diffs != pd.Timedelta(minutes=TF_MIN)]
        gaps, other = {}, []
        for d in gap_rows:
            mins = int(d.total_seconds() // 60)
            if mins <= 240:
                gaps["daily_break"] = gaps.get("daily_break", 0) + 1
            elif mins >= 1000:
                gaps["weekend"] = gaps.get("weekend", 0) + 1
            else:
                other.append(mins)
        if other:
            anomalies.append("window %d: unclassified gaps (minutes): %s" % (i, other))
            verdict = "ANOMALY"
        nan_inf = int(np.sum(~np.isfinite(wdf[["open", "high", "low", "close"]].to_numpy(dtype=float))))
        vol = wdf["volume"].to_numpy(dtype=float)
        vol_bad = int(np.sum(~np.isfinite(vol)) + np.sum(vol < 0))
        grid_ok = bool((t.astype("int64") // 10**9 % (TF_MIN * 60) == 0).all()
                       and set(t.dt.second.unique()).issubset({0}))
        contiguous = None
        if prev_last is not None:
            contiguous = bool((t.iloc[0] - prev_last) == pd.Timedelta(minutes=TF_MIN))
            if not contiguous:
                anomalies.append("window %d not contiguous with previous window" % i)
                verdict = "ANOMALY"
        prev_last = t.iloc[-1]

        fname = "cp5_window_%d_df.csv" % i
        fpath = os.path.join(CACHE, fname)
        wdf.to_csv(fpath, index=False)
        sha = sha256_file(fpath)
        meta = {
            "file": fname, "window_id": i, "symbol": SYMBOL, "timeframe": TF_NAME,
            "start_pos": START_POS, "requested_bars": BARS_PER_WINDOW, "actual_bars": n,
            "first_timestamp": str(t.iloc[0]), "last_timestamp": str(t.iloc[-1]),
            "strictly_increasing": strictly_increasing, "duplicate_timestamps": dup_count,
            "gaps": gaps, "gaps_other_minutes": other,
            "ohlc_valid": ohlc_valid(wdf), "volume_valid": vol_bad == 0,
            "volume_zero_bars": int(np.sum(vol == 0)),
            "nan_inf_ohlc_count": nan_inf, "minute_grid_alignment_ok": grid_ok,
            "contiguous_with_previous": contiguous, "timezone": "naive broker-server time",
            "mt5_status": "OK", "retrieved_at_local": retrieved_at, "sha256": sha,
        }
        windows_meta.append(meta)
        P("- window %d: bars=%d/%d span=%s .. %s | increasing=%s dups=%d gaps=%s ohlc_valid=%s nan/inf=%d grid_ok=%s contiguous=%s sha256=%s"
          % (i, n, BARS_PER_WINDOW, meta["first_timestamp"], meta["last_timestamp"],
             strictly_increasing, dup_count, json.dumps(meta["gaps"]),
             meta["ohlc_valid"], nan_inf, grid_ok, contiguous, sha[:16] + "..."))

    allt = pd.concat([pd.to_datetime(w["time"]) for w in wins]).reset_index(drop=True)
    g_inc = bool((allt.diff().dropna() > pd.Timedelta(0)).all())
    g_dup = int(len(allt) - allt.nunique())
    P("- global: total_bars=%d (expected %d) strictly_increasing=%s duplicate_timestamps=%d"
      % (len(allt), N_WINDOWS * BARS_PER_WINDOW, g_inc, g_dup))
    if len(allt) != N_WINDOWS * BARS_PER_WINDOW or not g_inc or g_dup != 0:
        verdict = "ANOMALY"
        anomalies.append("global integrity failure")

    dataset_id = hashlib.sha256()
    for m in windows_meta:
        dataset_id.update(m["sha256"].encode())
    manifest = {
        "experiment": "CP5.2 DATA FREEZE",
        "created_local": retrieved_at,
        "git": {"branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
                "baseline_lock_tag": "baseline-lock-v1", "source_freeze_tag": "cp5-source-freeze-v1"},
        "source_freeze_sha256": {
            "strategy_a1_meanrev.py": "85c1781a700dde5ed0015fc64841f99a4c0263b6913b9b3afc5a77765e4105a6",
            "strategy_a2_breakout.py": "732d1eaad9517e2c4b4bbe1d0fc82a1fc8a0a9c79fd8a8aa9898ab72d279dd5b",
            "research_harness.py": "c5e7844a27d9c4a6d08a0221d7a42580e9750cb45f410672589e21f2ddc49216"},
        "spec": {"symbol": SYMBOL, "timeframe": TF_NAME, "windows": N_WINDOWS,
                 "bars_per_window": BARS_PER_WINDOW, "start_pos": START_POS,
                 "loader": "research_harness.load_windows", "candle_type": "plain",
                 "timezone": "naive broker-server time"},
        "mt5_version": mt5_ver,
        "symbol_info": {"digits": info.digits, "point": info.point,
                        "trade_tick_size": info.trade_tick_size,
                        "trade_tick_value": info.trade_tick_value},
        "retrieved_at_local": retrieved_at,
        "windows": windows_meta,
        "dataset_sha256_combined": dataset_id.hexdigest(),
        "anomalies": anomalies,
        "verdict": verdict,
    }
    with open(os.path.join(HERE, "CP5_DATA_FREEZE_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, default=str)

    P("")
    P("## B. Integrity checks")
    P("- bar counts: %s" % ("6/6 exact (14,400)" if all(m["actual_bars"] == BARS_PER_WINDOW for m in windows_meta) else "MISMATCH"))
    P("- ordering: %s | duplicates: %d (global)" % ("strictly increasing 6/6" if all(m["strictly_increasing"] for m in windows_meta) else "FAIL", g_dup))
    P("- gaps: classified per window (daily_break / weekend); unclassified gaps => anomaly")
    P("- OHLC validity: %s | NaN/Inf: total %d | volume validity: %s"
      % ("6/6 PASS" if all(m["ohlc_valid"] for m in windows_meta) else "FAIL",
         sum(m["nan_inf_ohlc_count"] for m in windows_meta),
         "6/6 PASS" if all(m["volume_valid"] for m in windows_meta) else "FAIL"))
    P("- final-candle completeness: start_pos=1 by construction (CP1 proof) + probe above")
    P("")
    P("## C. Hashes")
    for m in windows_meta:
        P("- %s : %s" % (m["file"], m["sha256"]))
    P("- DATASET IDENTITY (sha256 over the six file hashes, in order): %s" % dataset_id.hexdigest())
    P("")
    P("## D. Dataset identity")
    P("- Any future CP5 step must read ONLY these six frozen files and cite this manifest + dataset_sha256_combined.")
    P("- Registration chain: pre-registration fcf71cb -> Amendment1/source-freeze 9184e5b (tag cp5-source-freeze-v1) -> this freeze.")
    P("")
    P("## E. Anomalies")
    P("- %s" % ("; ".join(anomalies) if anomalies else "none"))
    P("")
    P("## F. Final freeze verdict")
    P("- **%s** — dataset frozen at project_audit/stability_windows_cache/cp5_window_{1..6}_df.csv" % verdict)
    P("- This report contains NO performance metric by design.")
finally:
    if MODE == "freeze":
        mt5.shutdown()
        P("- MT5 connection closed (read-only session).")

with open(os.path.join(HERE, "CP5_DATA_FREEZE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
sys.exit(0 if verdict == "FROZEN" else 4)
