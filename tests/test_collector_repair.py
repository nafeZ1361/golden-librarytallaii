# tests/test_collector_repair.py — COLLECTOR REPAIR PASS tests (R1-R4)
# R1 ledger cursor (header-validated, name-based, fail-closed)
# R2 detection context (mid-day start must not lose events; context != official)
# R3 outcome completion (append-only outcome_update, idempotent)
# R4 180-day termination gate (vs FORWARD_START_TIMESTAMP; NULL -> STOP)
# T-ISO trading isolation. NO real MT5, NO orders, NO official collection.

import os, sys, importlib
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "project_audit", "forward_monitoring"))

fc = importlib.import_module("forward_collector")

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


class FakeResult:
    def __init__(self, retcode):
        self.retcode = retcode


def event_row(eid, ts, direction="buy", ref="2005.0", h5="", h20=""):
    r = {c: "" for c in fc.LEDGER_COLUMNS}
    r.update({"event_id": eid, "record_type": "event",
              "symbol": "XAUUSD.", "timeframe": "M3",
              "event_type": "first_breakout", "direction": direction,
              "reference_price": ref, "first_breakout_timestamp": ts,
              "h5_outcome": h5, "h20_outcome": h20,
              "dataset_version": "FD-CP5.9"})
    return r


def write_ledger(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(fc.LEDGER_COLUMNS) + "\n")
        for r in rows:
            f.write(",".join(str(r.get(c, "")) for c in fc.LEDGER_COLUMNS) + "\n")


def make_days(specs):
    """specs: list of (start, n_bars, breakout_at|None). Continuous 3-min bars
    with real overnight gaps between days."""
    frames = []
    for start, n, br in specs:
        t0 = pd.Timestamp(start)
        rows = []
        or_high = 2001.0
        for i in range(n):
            ts = t0 + timedelta(minutes=3 * i)
            o = 2000.0
            c, h, vol = o, o + 1.0, 100
            day_i = i
            if br is not None and i == br:
                c = 2005.0
                h = 2006.0
                vol = 300
            rows.append({"time": ts, "open": o, "high": max(h, o, c),
                         "low": min(o - 1.0, c), "close": c, "volume": vol,
                         "spread": 5})
        frames.append(pd.DataFrame(rows))
    return pd.concat(frames).reset_index(drop=True)


def temp_ledger(rows):
    path = os.path.join(fc.FW, "_repair_ledger.csv")
    write_ledger(path, rows)
    fc.LEDGER = path  # isolate official ledger during the test
    return path


# ---------------- T-R1 / T-R1B ----------------
@case("T-R1 cursor reads first_breakout_timestamp (NOT reference_price); monotonic")
def _():
    rows = [event_row("E1", "2026-09-10 02:00:00", ref="2005.0"),
            event_row("E2", "2026-09-10 05:00:00", ref="2010.0")]
    p = temp_ledger(rows)
    ts = fc.last_ledger_ts(p)
    assert ts == pd.Timestamp("2026-09-10 05:00:00"), ts
    # counter-evidence: cursor must NOT be the last row's reference_price
    # ("2010.0" is not a parseable datetime on pandas 2.3.3, so compare text)
    assert "2010" not in str(ts), "cursor swallowed reference_price!"


@case("T-R1B corrupt ledger: missing timestamp / bad header -> FAIL CLOSED")
def _():
    rows = [event_row("E1", "2026-09-10 02:00:00")]
    rows[0]["first_breakout_timestamp"] = ""  # missing
    p = temp_ledger(rows)
    try:
        fc.last_ledger_ts(p)
        raise AssertionError("expected LedgerCorruptError")
    except fc.LedgerCorruptError:
        pass
    # bad header
    with open(p, "w", encoding="utf-8") as f:
        f.write("a,b,c\n1,2,3\n")
    try:
        fc.last_ledger_ts(p)
        raise AssertionError("expected LedgerCorruptError on bad header")
    except fc.LedgerCorruptError:
        pass


# ---------------- T-R2 / T-R2B ----------------
@case("T-R2 mid-day collector start: 3-day context frame still finds the day's event")
def _():
    # days: Sep 7 (filler), Sep 8 (breakout at bar 55), Sep 9 (filler, partial end)
    df = make_days([("2026-09-07 01:00", 460, None),
                    ("2026-09-08 01:00", 460, 55),
                    ("2026-09-09 01:00", 200, None)])
    full_ev = fc.detect_events(df)[0]
    assert any(e["first_breakout_timestamp"].startswith("2026-09-08") for e in full_ev), \
        "scenario must contain the Sep-8 event"
    # a collector starting at Sep 9 05:00 with a 3-day CONTEXT window covers
    # Sep 8 from its start -> the event IS re-detected in context
    context_start = pd.Timestamp("2026-09-09 05:00") - timedelta(days=3)
    ctx = df[pd.to_datetime(df["time"]) >= context_start]
    ctx_ev = fc.detect_events(ctx)[0]
    sep8 = [e for e in ctx_ev if e["first_breakout_timestamp"].startswith("2026-09-08")]
    assert sep8, "3-day context lost a real event!"
    # counter-evidence: a frame starting MID-DAY (after OR) cannot see it —
    # which is exactly why the context rule is mandatory
    mid = df[pd.to_datetime(df["time"]) >= pd.Timestamp("2026-09-08 06:00")]
    assert fc.detect_events(mid)[0] == [] or all(
        not e["first_breakout_timestamp"].startswith("2026-09-08")
        for e in fc.detect_events(mid)[0])
    assert fc.DETECTION_CONTEXT_DAYS >= 2


@case("T-R2B detection context NEVER becomes official events (dedupe + boundary)")
def _():
    rows = [event_row("FD-CP5.9-" + fc.sha_txt("XAUUSD.|2026-09-08 02:45:00|buy")[:16],
                      "2026-09-08 02:45:00")]
    p = temp_ledger(rows)
    known = fc.known_event_ids(p)
    df = make_days([("2026-09-08 01:00", 460, 55)])
    evs = fc.detect_events(df)[0]
    start_ts = pd.Timestamp("2026-09-05 00:00:00")
    new = [e for e in evs if e["event_id"] not in known
           and pd.Timestamp(e["first_breakout_timestamp"]) > start_ts]
    assert new == [], "context re-detection leaked into official events"
    # and a pre-forward event is excluded even if unknown
    df2 = make_days([("2026-09-04 01:00", 460, 55)])
    evs2 = fc.detect_events(df2)[0]
    new2 = [e for e in evs2 if e["event_id"] not in known
            and pd.Timestamp(e["first_breakout_timestamp"]) > start_ts]
    assert new2 == [], "pre-forward event must never be official"


# ---------------- T-R3 / T-R3B ----------------
@case("T-R3 event h5 PENDING -> outcome_update appended; original row untouched")
def _():
    ev = event_row("E-R3", "2026-09-08 02:00:00", ref="2005.0")
    p = temp_ledger([ev])
    original_line = open(p, encoding="utf-8").read().splitlines()[1]
    # closed frame: event bar + 7 bars (h5 complete, h20 NOT)
    t0 = pd.Timestamp("2026-09-08 02:00:00")
    bars = [{"time": t0 + timedelta(minutes=3 * i),
             "close": 2006.0 if i == 5 else 2005.5} for i in range(8)]
    closed = pd.DataFrame(bars)
    n = fc.update_outcomes(closed)
    assert n == 1, n
    lines = open(p, encoding="utf-8").read().splitlines()
    assert lines[1] == original_line, "original event row was rewritten!"
    upd = [l for l in lines if "outcome_update" in l]
    assert len(upd) == 1 and "win" in upd[0] and "h5" not in upd[0].split(",")[9], upd
    # h20 must still be pending (frame ends before +20)
    assert upd[0].split(",")[10] == "", "h20 must not be fabricated"


@case("T-R3B idempotent: re-running updater creates NO duplicate outcome")
def _():
    ev = event_row("E-R3B", "2026-09-08 02:00:00", ref="2005.0")
    p = temp_ledger([ev])
    t0 = pd.Timestamp("2026-09-08 02:00:00")
    bars = [{"time": t0 + timedelta(minutes=3 * i),
             "close": 2006.0 if i == 5 else 2005.5} for i in range(8)]
    n1 = fc.update_outcomes(pd.DataFrame(bars))
    n2 = fc.update_outcomes(pd.DataFrame(bars))
    assert n1 == 1 and n2 == 0, (n1, n2)
    lines = open(p, encoding="utf-8").read().splitlines()
    assert sum(1 for l in lines if "outcome_update" in l) == 1


# ---------------- T-R4 / T-R4B ----------------
@case("T-R4 termination gate: T0+179d CONTINUE, T0+180d STOP_FREEZE, 300 events STOP")
def _():
    T0 = pd.Timestamp("2026-09-05 00:00:00")
    assert fc.check_termination(10, T0, T0 + timedelta(days=179))[0] == "CONTINUE"
    assert fc.check_termination(10, T0, T0 + timedelta(days=180))[0] == "STOP_FREEZE"
    assert fc.check_termination(300, T0, T0 + timedelta(days=1))[0] == "STOP_FREEZE"
    assert fc.check_termination(299, T0, T0 + timedelta(days=1))[0] == "CONTINUE"


@case("T-R4B FORWARD_START_TIMESTAMP = NULL -> STOP (no collection)")
def _():
    d, reason = fc.check_termination(10, None, datetime(2026, 9, 8))
    assert d == "STOP" and "NULL" in reason, (d, reason)


# ---------------- T-ISO ----------------
@case("T-ISO trading isolation: zero order-API call sites in collector v2")
def _():
    import re
    src = open(os.path.join(ROOT, "project_audit", "forward_monitoring",
                            "forward_collector.py"), encoding="utf-8").read()
    for pat in (r"order_send\s*\(", r"create_order\s*\(", r"pending_order\s*\(",
                r"close_order\s*\(", r"close_all\w*\s*\(", r"modify_tp\s*\(",
                r"modify_stop\s*\(", r"remove_order\s*\(",
                r"\bpositions_get\s*\(", r"history_deals_get\s*\(",
                r"import\s+MetaTrader5\s*$"):
        assert not re.search(pat, src), "order capability found: %s" % pat


@case("T-DET determinism x3: identical inputs -> identical events/IDs/outcomes")
def _():
    df = make_days([("2026-09-07 01:00", 460, None),
                    ("2026-09-08 01:00", 460, 55),
                    ("2026-09-09 01:00", 460, None)])
    runs = []
    for _ in range(3):
        evs = fc.detect_events(df.copy())[0]
        runs.append([(e["event_id"], e["direction"], e["reference_price"],
                      e["first_breakout_timestamp"], e["h5_outcome"],
                      e["h20_outcome"]) for e in evs])
    assert runs[0] == runs[1] == runs[2]


def main():
    npass = 0
    for name, fn in CASES:
        try:
            note = fn()
            npass += 1
            print("[PASS] %s%s" % (name, (" | " + str(note)) if note else ""))
        except AssertionError as ex:
            print("[FAIL] %s | %s" % (name, ex))
        except Exception as ex:  # noqa: BLE001
            print("[RAISED] %s | %s: %s" % (name, type(ex).__name__, ex))
    print("\nSUMMARY: %d/%d PASS" % (npass, len(CASES)))
    return 0 if npass == len(CASES) else 4


if __name__ == "__main__":
    sys.exit(main())
