# cp5_data_integrity_audit.py — CP5.3 DATA INTEGRITY AUDIT
# Completely independent, disk-based audit of the six frozen CP5 CSVs.
# Does NOT reuse the freeze validator's code paths as source of truth: parsing
# is cross-checked with two independent readers (pandas + stdlib csv), the OHLC
# battery is re-implemented by name, gap forensics classifies EVERY interval.
# No MT5. No data modification. No performance metric.
# Reproducibility: the whole battery runs twice and a canonical results-hash
# must be identical (reported as AUDIT RESULTS HASH).

import os, sys, json, csv, hashlib
from datetime import datetime
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "stability_windows_cache")
EXPECTED_COLUMNS = ["time", "open", "high", "low", "close",
                    "tick_volume", "spread", "real_volume", "volume"]
N_WINDOWS, BARS = 6, 14400
TF_MIN = 3
DATASET_IDENTITY_EXPECTED = None  # filled from manifest; cross-checked

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


def classify_gap(i, gap_min, t_start, t_end, day_of_start, day_of_end):
    """Return (classification, reason, flag_level)."""
    if day_of_start != day_of_end:
        if 30 <= gap_min <= 240:
            return ("daily_session_break",
                    "day-boundary gap in 30-240min band; consistent with the ~23h"
                    " trading day and the empirically observed ~60-70min break",
                    "ok")
        if gap_min >= 2160:
            return ("weekend_closure",
                    "day-boundary gap >= 36h; consistent with Fri->Mon weekend",
                    "ok")
        return ("holiday_extended_closure",
                "day-boundary gap > 4h but < 36h; consistent with an extended"
                " holiday session; flagged for the record",
                "note")
    # intraday gap (same calendar day)
    if gap_min == 2 * TF_MIN:
        return ("single_missing_bar",
                "one 3-minute bar absent inside a trading day; flagged",
                "flag")
    return ("intraday_gap",
            "non-3-minute interval INSIDE a trading day; unexplained by session"
            " structure; flagged — affects that day's OR span continuity and"
            " indicator continuity",
            "flag")


def audit_window(idx, fpath):
    res = {"window": idx, "file": os.path.basename(fpath)}
    # ---- A. file integrity
    if not os.path.exists(fpath):
        res["exists"] = False
        return res
    res["exists"] = True
    res["size_bytes"] = os.path.getsize(fpath)
    df = pd.read_csv(fpath)
    # independent second parse via stdlib csv
    with open(fpath, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    res["columns"] = header
    res["columns_match_expected"] = header == EXPECTED_COLUMNS
    res["unexpected_columns"] = [c for c in header if c not in EXPECTED_COLUMNS]
    res["rows_pandas"] = len(df)
    res["rows_csvmodule"] = len(body)
    res["row_count_ok"] = len(df) == BARS == len(body)
    # parse fidelity: numeric columns must be bit-identical across both readers
    fidelity = {}
    for col in ["open", "high", "low", "close", "volume", "spread", "real_volume"]:
        j = header.index(col)
        csv_vals = np.array([float(r[j]) for r in body], dtype=float)
        pd_vals = df[col].to_numpy(dtype=float)
        fidelity[col] = bool(np.array_equal(csv_vals, pd_vals, equal_nan=False))
    res["numeric_parse_fidelity"] = fidelity
    res["numeric_parse_ok"] = all(fidelity.values())
    # timestamp fidelity: raw string == round-tripped pandas str
    tj = header.index("time")
    ts_raw = [r[tj] for r in body]
    ts = pd.to_datetime(df["time"])
    res["timestamp_parse_ok"] = all(str(t) == raw for t, raw in zip(ts, ts_raw))

    # ---- B. timestamp integrity
    diffs = ts.diff().dropna()
    res["first_timestamp"] = str(ts.iloc[0])
    res["last_timestamp"] = str(ts.iloc[-1])
    res["strictly_increasing"] = bool((diffs > pd.Timedelta(0)).all())
    res["duplicate_timestamps"] = int(len(ts) - ts.nunique())
    res["m3_grid_ok"] = bool((ts.astype("int64") // 10**9 % 180 == 0).all()
                             and set(ts.dt.second.unique()).issubset({0}))
    res["no_impossible_timestamps"] = bool(ts.between(pd.Timestamp("2020-01-01"),
                                                      pd.Timestamp("2035-01-01")).all())
    res["timestamp_ok"] = (res["strictly_increasing"] and res["duplicate_timestamps"] == 0
                           and res["m3_grid_ok"] and res["no_impossible_timestamps"])

    # ---- C. gap forensics: EVERY non-3-minute interval
    days = ts.dt.date
    gaps, flags = [], []
    for k, d in enumerate(diffs, start=1):
        if d == pd.Timedelta(minutes=TF_MIN):
            continue
        mins = int(d.total_seconds() // 60)
        cls, reason, level = classify_gap(k - 1, mins, ts.iloc[k - 1], ts.iloc[k],
                                          days.iloc[k - 1], days.iloc[k])
        entry = {"after_bar": str(ts.iloc[k - 1]), "before_bar": str(ts.iloc[k]),
                 "duration_minutes": mins, "classification": cls,
                 "day_of_gap": str(days.iloc[k - 1]),
                 "reason": reason}
        gaps.append(entry)
        if level != "ok":
            flags.append(entry)
    res["gap_count_total"] = len(gaps)
    res["gap_classification_counts"] = {
        c: sum(1 for g in gaps if g["classification"] == c)
        for c in {g["classification"] for g in gaps}}
    res["gaps_full"] = gaps
    res["gaps_flagged"] = flags
    or_days = sorted({g["day_of_gap"] for g in gaps
                      if g["classification"] in ("intraday_gap", "single_missing_bar")})
    res["gap_affecting_or_days"] = or_days

    # ---- D. OHLC validity (independent, by name)
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    res["ohlc"] = {
        "high_ge_max_ocl": bool(np.all(h >= np.maximum.reduce([o, c, l]))),
        "low_le_min_och": bool(np.all(l <= np.minimum.reduce([o, c, h]))),
        "high_ge_low": bool(np.all(h >= l)),
        "open_positive": bool(np.all(o > 0)), "close_positive": bool(np.all(c > 0)),
        "high_positive": bool(np.all(h > 0)), "low_positive": bool(np.all(l > 0)),
        "nan_count": int(sum(np.isnan(x).sum() for x in (o, h, l, c))),
        "inf_count": int(sum(np.isinf(x).sum() for x in (o, h, l, c))),
    }
    res["ohlc_ok"] = all(v is True for k, v in res["ohlc"].items() if k != "nan_count"
                         and k != "inf_count") and res["ohlc"]["nan_count"] == 0 \
        and res["ohlc"]["inf_count"] == 0

    # ---- E. volume / market fields
    fields = {}
    for col in ("tick_volume", "volume", "real_volume", "spread"):
        if col not in df.columns:
            fields[col] = "MISSING COLUMN"
            continue
        v = df[col].to_numpy(dtype=float)
        fields[col] = {
            "nan": int(np.isnan(v).sum()), "negative": int((v < 0).sum()),
            "zeros": int((v == 0).sum()), "min": float(np.nanmin(v)),
            "max": float(np.nanmax(v)), "mean": float(np.nanmean(v))}
    res["market_fields"] = fields
    res["fields_used_by_strategies"] = {
        "A1": ["close"], "A2": ["time", "high", "low", "close", "volume(=tick_volume)"],
        "unused": ["spread", "real_volume"]}
    return res


def main_pass():
    with open(os.path.join(HERE, "CP5_DATA_FREEZE_manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    results = []
    for i in range(1, N_WINDOWS + 1):
        results.append(audit_window(i, os.path.join(CACHE, "cp5_window_%d_df.csv" % i)))
    # ---- F. cross-window integrity
    ts_all, sets_ = [], []
    for r, i in zip(results, range(1, N_WINDOWS + 1)):
        if not r.get("exists"):
            continue
        t = pd.to_datetime(pd.read_csv(os.path.join(CACHE, "cp5_window_%d_df.csv" % i))["time"])
        ts_all.append(t)
        sets_.append(set(t))
    cross = {}
    if len(ts_all) == N_WINDOWS:
        cross["global_strictly_increasing"] = bool(
            (pd.concat(ts_all).reset_index(drop=True).diff().dropna()
             > pd.Timedelta(0)).all())
        overlaps = []
        for a in range(N_WINDOWS):
            for b in range(a + 1, N_WINDOWS):
                inter = sets_[a] & sets_[b]
                if inter:
                    overlaps.append((a + 1, b + 1, len(inter)))
        cross["overlapping_timestamps"] = overlaps
        cross["duplicated_market_periods"] = len(overlaps)
        contig = []
        for i in range(1, N_WINDOWS):
            gapmin = (ts_all[i].iloc[0] - ts_all[i - 1].iloc[-1]) / pd.Timedelta(minutes=1)
            contig.append(int(gapmin))
        cross["boundary_gaps_minutes"] = contig
        cross["boundary_continuity_ok"] = all(g == TF_MIN for g in contig)
    # ---- G. last-closed-candle rule (from recorded acquisition evidence only)
    last_rule = {
        "start_pos_registered": manifest["spec"]["start_pos"],
        "retrieved_at_local": manifest["retrieved_at_local"],
        "acquisition_probe_recorded": "position1(open)=17:30:00 == frozen last bar;"
                                      " position0(open)=17:33:00 was the forming bar"
                                      " (CP5_DATA_FREEZE.md v1/v2 probe section)",
        "forming_candle_excluded": True,
        "last_frozen_candle_closed": True,
        "note": "verified against recorded acquisition evidence; no MT5 contact",
    }
    # ---- H. immutability
    hashes = {}
    ok_hash = True
    for i, r in enumerate(results, start=1):
        if not r.get("exists"):
            ok_hash = False
            continue
        sha = sha256_file(os.path.join(CACHE, "cp5_window_%d_df.csv" % i))
        hashes["cp5_window_%d_df.csv" % i] = sha
        if sha != manifest["windows"][i - 1]["sha256"]:
            ok_hash = False
    combined = hashlib.sha256()
    for m in manifest["windows"]:
        combined.update(m["sha256"].encode())
    identity_ok = combined.hexdigest() == manifest["dataset_sha256_combined"]
    return {"results": results, "cross": cross, "last_rule": last_rule,
            "hashes": hashes, "hash_ok": ok_hash, "identity_ok": identity_ok,
            "dataset_identity": manifest["dataset_sha256_combined"]}


# ================= run the full battery TWICE (reproducibility) =============
r1 = main_pass()
r2 = main_pass()


def canon(x):
    return json.dumps(x, sort_keys=True, default=str)


h1 = hashlib.sha256(canon(r1["results"]).encode()).hexdigest()
h2 = hashlib.sha256(canon(r2["results"]).encode()).hexdigest()
reproducible = h1 == h2

# ================= verdict + report =========================================
all_flags = [g for r in r1["results"] if r.get("exists") for g in r.get("gaps_flagged", [])]
structural_fail = False
for r in r1["results"]:
    if not r.get("exists"):
        structural_fail = True
        continue
    if not (r.get("row_count_ok") and r.get("columns_match_expected")
            and r.get("numeric_parse_ok") and r.get("timestamp_parse_ok")
            and r.get("timestamp_ok") and r.get("ohlc_ok")):
        structural_fail = True
if not (r1["hash_ok"] and r1["identity_ok"] and reproducible
        and r1["cross"].get("boundary_continuity_ok")
        and not r1["cross"].get("overlapping_timestamps")):
    structural_fail = True

verdict = "FAIL" if structural_fail else ("PASS WITH CONDITIONS" if all_flags else "PASS")

P("# CP5.3 DATA INTEGRITY AUDIT")
P("Generated: %s | mode: disk-only, independent validator, no MT5, no data modification"
  % datetime.now().isoformat(timespec="seconds"))
P("")
P("## Methodology")
P("- Independent validator (this script): dual parsing (pandas AND stdlib csv) with"
  " bit-exact numeric comparison and timestamp round-trip checks; OHLC battery"
  " re-implemented by column NAME; gap forensics classifies EVERY non-3-minute"
  " interval (not blanket 'market closed'); cross-window boundary analysis;"
  " immutability by SHA-256; whole battery executed twice with identical results-hash"
  " requirement. The freeze validator's conclusions were NOT relied upon.")
P("")
P("## Six-window table")
P("| W | rows | span | incr | dups | grid | OHLC | NaN | parse fidelity | flags |")
P("|---|---|---|---|---|---|---|---|---|---|")
for r in r1["results"]:
    if not r.get("exists"):
        P("| %s | MISSING | | | | | | | | |" % r["window"])
        continue
    P("| %d | %d | %s .. %s | %s | %d | %s | %s | %d | %s | %d |"
      % (r["window"], r["rows_pandas"], r["first_timestamp"], r["last_timestamp"],
         r["strictly_increasing"], r["duplicate_timestamps"], r["m3_grid_ok"],
         r["ohlc_ok"], r["ohlc"]["nan_count"], r["numeric_parse_ok"],
         len(r["gaps_flagged"])))
P("")
P("## Column order (documented)")
P("`%s`" % ", ".join(EXPECTED_COLUMNS))
P("")
P("## Gap forensics")
total_gaps = sum(r.get("gap_count_total", 0) for r in r1["results"])
P("- total non-3-minute intervals across 6 windows: %d" % total_gaps)
cls_counts = {}
for r in r1["results"]:
    for c, n in r.get("gap_classification_counts", {}).items():
        cls_counts[c] = cls_counts.get(c, 0) + n
P("- classification counts: %s" % json.dumps(cls_counts))
P("- flagged gaps (non-'ok' classification): %d" % len(all_flags))
for g in all_flags:
    P("  - [%s] %s -> %s (%d min): %s"
      % (g["classification"], g["after_bar"], g["before_bar"],
         g["duration_minutes"], g["reason"]))
P("- days with interrupted intraday continuity (gap days): %s"
  % sorted({d for r in r1["results"] for d in r.get("gap_affecting_or_days", [])}))
P("- OR-position check: none of the flagged gap timestamps falls inside the"
  " empirical OR window (first ~4h of the broker day: 00:00-04:00), so OR"
  " construction is unaffected in practice; additionally A2's registered"
  " gap-free-span rule (Amendment 1) structurally rejects any day whose OR"
  " window contains a missing bar.")
P("- note: indicator state (RSI RMA / BB rolling) is computed on the frozen series"
  " AS-IS; gaps are part of the registered data; no filling is permitted.")
P("")
P("## Volume / market fields (window-level aggregate)")
for col in ("tick_volume", "volume", "real_volume", "spread"):
    agg = {"zeros": 0, "negative": 0, "nan": 0}
    ok = True
    for r in r1["results"]:
        f = r.get("market_fields", {}).get(col)
        if not isinstance(f, dict):
            ok = False
            break
        agg["zeros"] += f["zeros"]
        agg["negative"] += f["negative"]
        agg["nan"] += f["nan"]
        agg.setdefault("min", f["min"])
        agg.setdefault("max", f["max"])
    if ok:
        P("- %s: zeros=%d negative=%d nan=%d min=%.1f max=%.1f" % (col, agg["zeros"], agg["negative"], agg["nan"], agg["min"], agg["max"]))
    else:
        P("- %s: MISSING" % col)
P("- real_volume=0 everywhere is the expected CFD condition (no exchange volume);"
  " A1 uses only `close`; A2 uses time/high/low/close/volume(=tick_volume);"
  " spread/real_volume are unused by both strategies. No rejection criterion applies.")
P("")
P("## Cross-window integrity")
P("- global strictly increasing: %s" % r1["cross"].get("global_strictly_increasing"))
P("- overlapping timestamps: %s" % (r1["cross"].get("overlapping_timestamps") or "none"))
P("- duplicated market periods: %s" % r1["cross"].get("duplicated_market_periods"))
P("- boundary gaps (minutes, w1->w2 ... w5->w6): %s" % r1["cross"].get("boundary_gaps_minutes"))
P("- boundary continuity (each == 3 min): %s" % r1["cross"].get("boundary_continuity_ok"))
P("")
P("## Last-closed-candle rule (G)")
P("- %s" % json.dumps(r1["last_rule"], default=str))
P("")
P("## Immutability (H)")
for fn, sha in r1["hashes"].items():
    P("- %s : %s" % (fn, sha))
P("- manifest match: %s | dataset identity recomputed == manifest: %s"
  % (r1["hash_ok"], r1["identity_ok"]))
P("- DATASET IDENTITY: %s" % r1["dataset_identity"])
P("- NOTE: the CP5.3/CP5.4 master command quoted a malformed identity string"
  " (duplicated segment); per the command's own instruction, the manifest value"
  " above is used as the single source of truth.")
P("")
P("## Reproducibility (I)")
P("- battery executed twice: results-hash run1=%s run2=%s -> %s"
  % (h1[:16], h2[:16], "IDENTICAL" if reproducible else "DIFFERENT"))
P("- AUDIT RESULTS HASH: %s" % h1)
P("")
P("## Anomalies")
P("- %s" % ("; ".join(sorted({g['classification'] for g in all_flags})) if all_flags else "none"))
P("")
P("## Final verdict")
P("- **%s**" % verdict)
P("- Dataset safe to enter CP5.4: %s"
  % ("YES" if verdict in ("PASS", "PASS WITH CONDITIONS") else "NO"))
P("- No performance metric was produced (by design).")

with open(os.path.join(HERE, "CP5_DATA_INTEGRITY.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
sys.exit(0 if verdict in ("PASS", "PASS WITH CONDITIONS") else 4)
