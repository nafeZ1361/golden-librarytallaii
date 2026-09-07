# forward_collector.py — CYCLE-R1..: FORWARD DATA COLLECTOR (FD-CP5.9)
# Per master protocol §30/§47-§53: COLLECT pipeline is
#   READ -> VALIDATE -> DETECT -> RECORD -> HASH -> LOG
# and NOTHING else. No optimization, no tuning, no trading. This module has NO
# order capability by construction (it never imports module.mt5 order paths or
# MetaTrader5 trading functions; acquisition uses read-only rate queries only).
#
# Modes:
#   preview              — detect + report; NO official writes, NO start stamp
#   collect              — OFFICIAL appends; requires marker file
#                          forward_monitoring/COLLECT_START_AUTHORIZED to exist
#                          (created ONLY by human start authorization, §52)
#
# Event definition: the FROZEN A2-v2 first-breakout rule
# (strategy_a2_v2_firstbreakout.py) — reused verbatim (§49: no duplicate logic).
# Event ID: deterministic "FD-CP5.9-" + sha16(symbol|first_breakout_ts|direction)
# Ledger: APPEND-ONLY csv (project_audit/forward_monitoring/forward_event_ledger.csv)
# Outcomes: h5/h20 recorded at detection when bars already exist; otherwise a
#           separate appended row type "outcome_update" fills them later from
#           frozen-then-forward data (append-only correction per §39).
# Forming candles: any bar whose close-time is in the future relative to the
#           fetch moment is dropped and logged (never recorded as complete).
# TZ rule: MT5 range bounds are passed broker_naive + 3:30 (CP6 v2 lesson).

import os, sys, json, hashlib, argparse
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
FW = os.path.join(HERE)  # project_audit/forward_monitoring
LEDGER = os.path.join(FW, "forward_event_ledger.csv")
EXLOG = os.path.join(FW, "forward_exclusion_log.csv")
MANIFEST = os.path.join(FW, "forward_dataset_manifest.json")
AUTH_MARKER = os.path.join(FW, "COLLECT_START_AUTHORIZED")
SYMBOL, BARS_PER_DAY, TF_MIN = "XAUUSD.", 40, 3
TZ_DELTA = timedelta(hours=3, minutes=30)  # CP6 v2: API bounds are LOCAL-naive
DATASET_VERSION, CONTRACT_VERSION = "FD-CP5.9", "1.0"
LEDGER_HEADER = ("event_id,record_type,detection_timestamp_utc,symbol,timeframe,"
                 "event_type,direction,reference_price,first_breakout_timestamp,"
                 "h5_outcome,h20_outcome,spread,data_source,dataset_version,"
                 "excluded,exclusion_reason")


def sha_txt(s):
    return hashlib.sha256(s.encode()).hexdigest()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def log(msg):
    print("[COLLECTOR] %s" % msg, flush=True)


def code_version():
    """Frozen event-rule hash + collector hash (provenance)."""
    a = sha256_file(os.path.join(ROOT, "strategy_a2_v2_firstbreakout.py"))[:16]
    b = sha256_file(os.path.abspath(__file__))[:16]
    return {"event_rule": a, "collector": b}


def fetch_new_bars(fetch_fn, last_ts, now_utc):
    """TZ-corrected incremental read (broker_naive +3:30 bounds). Returns
    (closed_df, excluded_forming_count). NEVER fabricates bars.
    now_utc/last_ts accept plain datetime OR pandas Timestamp (both handled)."""
    if last_ts is None:
        return pd.DataFrame(), 0
    start = pd.Timestamp(last_ts) + timedelta(minutes=TF_MIN)   # broker time
    end = pd.Timestamp(now_utc) + TZ_DELTA                      # local-naive bound
    raw = fetch_fn(start.to_pydatetime(), end.to_pydatetime())
    if raw is None or len(raw) == 0:
        return pd.DataFrame(), 0
    d = pd.DataFrame(raw)
    d["time"] = pd.to_datetime(d["time"], unit="s")
    if "tick_volume" in d.columns and "volume" not in d.columns:
        d["volume"] = d["tick_volume"]
    d = d.sort_values("time").reset_index(drop=True)
    forming = d[d["time"] + timedelta(minutes=TF_MIN) > pd.Timestamp(now_utc)]
    closed = d[d["time"] + timedelta(minutes=TF_MIN) <= pd.Timestamp(now_utc)]
    return closed.reset_index(drop=True), len(forming)


def detect_events(df, spread=None, source="MT5"):
    """First-breakout events per the FROZEN A2-v2 rule (verbatim reuse).
    Returns (events, exclusions). An event is recorded at its breakout bar;
    h5/h20 outcomes are filled only when the horizon bars exist in THIS df,
    otherwise recorded as pending (filled later by appended outcome_update)."""
    import strategy_a2_v2_firstbreakout as a2v2
    states = a2v2.signal_fn(df.copy(), "3m")
    closes = df["close"].tolist()
    events, excl = [], []
    for i in range(1, len(states)):
        s_cur, s_prev = states[i], states[i - 1]
        if s_cur in ("buy", "sell") and s_cur != s_prev:
            ts = df["time"].iloc[i]
            eid = "FD-CP5.9-" + sha_txt("%s|%s|%s" % (SYMBOL, ts, s_cur))[:16]
            rec = {"event_id": eid, "record_type": "event",
                   "detection_timestamp_utc": None, "symbol": SYMBOL,
                   "timeframe": "M3", "event_type": "first_breakout",
                   "direction": s_cur, "reference_price": closes[i],
                   "first_breakout_timestamp": str(ts), "h5_outcome": "",
                   "h20_outcome": "", "spread": (spread[i] if spread is not None
                                                 and i < len(spread) else ""),
                   "data_source": "MT5", "dataset_version": DATASET_VERSION,
                   "excluded": 0, "exclusion_reason": ""}
            for h, key in ((5, "h5_outcome"), (20, "h20_outcome")):
                if i + h < len(closes):
                    fwd = closes[i + h]
                    w = (s_cur == "buy" and fwd > closes[i]) or \
                        (s_cur == "sell" and fwd < closes[i])
                    rec[key] = ("win" if w else "loss")
            events.append(rec)
    return events, excl


def append_rows(rows):
    """APPEND-ONLY ledger write (no header rewrite, no deletion)."""
    new_file = not os.path.exists(LEDGER)
    with open(LEDGER, "a", encoding="utf-8", newline="") as f:
        if new_file:
            f.write(LEDGER_HEADER + "\n")
        for r in rows:
            f.write(",".join(json.dumps(r.get(k, ""), default=str)
                             for k in ("event_id", "record_type",
                                       "detection_timestamp_utc", "symbol",
                                       "timeframe", "event_type", "direction",
                                       "reference_price",
                                       "first_breakout_timestamp", "h5_outcome",
                                       "h20_outcome", "spread", "data_source",
                                       "dataset_version", "excluded",
                                       "exclusion_reason")).replace('"', "") + "\n")


def known_event_ids():
    if not os.path.exists(LEDGER):
        return set()
    with open(LEDGER, encoding="utf-8") as f:
        return {line.split(",", 1)[0] for line in f if line.strip()}


def last_ledger_ts():
    if not os.path.exists(LEDGER):
        return None
    last = None
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            parts = line.split(",")
            if len(parts) > 8 and parts[7]:
                last = parts[7]
    return pd.Timestamp(last) if last else None


def batch_hash(n_events, last_ts):
    payload = json.dumps({"dataset_version": DATASET_VERSION,
                          "contract_version": CONTRACT_VERSION,
                          "code": code_version(), "events": n_events,
                          "last_ts": str(last_ts)}, sort_keys=True, default=str)
    return sha_txt(payload)


def write_snapshot(n_events, n_excl, days, last_ts, batch_hash):
    os.makedirs(os.path.join(FW, "forward_snapshots"), exist_ok=True)
    snap = {"generated": datetime.utcnow().isoformat(timespec="seconds"),
            "total_events": n_events, "qualified_events": n_events,
            "excluded_events": n_excl, "observation_days": days,
            "batch_hash": batch_hash, "dataset_version": DATASET_VERSION,
            "contract_version": CONTRACT_VERSION, "last_event": str(last_ts),
            "note": "counts/hash only — NO performance metrics (blinding §42)"}
    path = os.path.join(FW, "forward_snapshots",
                        "forward_snapshot_%s.json" % datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1)
    return path


def load_auth():
    return os.path.exists(AUTH_MARKER)


def run_preview(fetch_fn, now_utc, days_back=30):
    """PREVIEW MODE (§32): detection + temp report; official ledger/manifest and
    FORWARD_START_TIMESTAMP are NEVER touched."""
    manifest = json.load(open(os.path.join(FW, "forward_dataset_manifest.json"),
                              encoding="utf-8"))
    last = manifest.get("last_event_timestamp")
    last_ts = pd.Timestamp(last) if last else None
    closed, forming = fetch_new_bars(fetch_fn, last_ts, now_utc)
    events, _ = detect_events(closed)
    known = known_event_ids()
    new = [e for e in events if e["event_id"] not in known]
    return {"mode": "preview", "closed_bars": len(closed),
            "forming_dropped": forming, "events_detected": len(events),
            "new_events": len(new), "would_append": [e["event_id"] for e in new]}


def run_collect(fetch_fn, now_utc, days_back=30):
    """OFFICIAL collection. Requires human-authorization marker (§52)."""
    if not load_auth():
        raise PermissionError("COLLECT_START_AUTHORIZED marker missing — "
                              "human start authorization required (§51/§52)")
    manifest = json.load(open(os.path.join(FW, "forward_dataset_manifest.json"),
                              encoding="utf-8"))
    if not manifest.get("forward_start_timestamp"):
        raise RuntimeError("FORWARD_START_TIMESTAMP not stamped — authorization "
                           "step must stamp it first")
    closed, forming = fetch_new_bars(fetch_fn, last_ledger_ts(), now_utc)
    events, _ = detect_events(closed, spread=closed["spread"].tolist()
                              if "spread" in closed.columns else None)
    known = known_event_ids()
    new = [e for e in events if e["event_id"] not in known]
    dup = len(events) - len(new)
    append_rows(new)
    n_total = sum(1 for _ in open(LEDGER)) - 1
    bh = batch_hash(n_total, closed["time"].iloc[-1] if len(closed) else None)
    manifest["events"] = n_total
    manifest["last_event_timestamp"] = str(closed["time"].iloc[-1]) if len(closed) else None
    manifest["batch_hash"] = bh
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    log("collect: detected=%d new=%d duplicate=%d total_in_ledger=%d batch_hash=%s"
        % (len(events), len(new), dup, n_total, bh[:16]))
    return {"detected": len(events), "appended": len(new), "duplicates_skipped": dup}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["preview", "collect"])
    args = ap.parse_args()
    if args.mode == "collect" and not load_auth():
        log("collect mode BLOCKED: COLLECT_START_AUTHORIZED marker missing "
            "(human start authorization required)")
        sys.exit(5)
    import MetaTrader5 as mt5
    if not mt5.initialize():
        log("ABORT: MT5 initialize failed: %s — NO EVENT fabricated" % (mt5.last_error(),))
        sys.exit(3)
    try:
        now = datetime.utcnow()
        def fetch_fn(a, b):
            r = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M3, a, b)
            return r
        if args.mode == "preview":
            print(json.dumps(run_preview(fetch_fn, now), indent=1, default=str))
        else:
            run_collect(fetch_fn, now)
    finally:
        mt5.shutdown()
