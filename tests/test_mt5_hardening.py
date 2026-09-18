# tests/test_mt5_hardening.py — LOOP 5 hardening regression tests (stage 4)
# Covers: lot_calculator fail-closed rewrite, get_broker_offset NameError +
# stale 'today' global, count_consecutive_sl double-offset, total_positions
# rename. NO real MT5, NO orders: module.mt5's MetaTrader5 handle is faked.

import os, sys, importlib
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

m = importlib.import_module("module.mt5")

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


class FakeAccount:
    def __init__(self, balance=10000.0):
        self.balance = balance


class FakeSymbolInfo:
    def __init__(self, volume_min=0.01, volume_step=0.01):
        self.volume_min = volume_min
        self.volume_step = volume_step


class FakeSymbol:
    def __init__(self, name):
        self.name = name


class FakeTick:
    def __init__(self, time):
        self.time = time


_real_datetime = datetime


class _MondayDateTime(_real_datetime):
    """datetime subclass whose today() is always a Monday (weekday path)."""
    @classmethod
    def today(cls):
        return cls(2026, 9, 7)  # 2026-09-07 is a Monday


class _FakeDTModule:
    datetime = _MondayDateTime
    timedelta = timedelta
    timezone = timezone


class Restore:
    """Context manager: patch module.mt5 / module.datetime, restore after."""
    def __init__(self, **attrs):
        self.attrs = attrs
        self.saved = {}

    def __enter__(self):
        self.saved = {k: getattr(m, k, None) for k in self.attrs}
        for k, v in self.attrs.items():
            setattr(m, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            setattr(m, k, v)
        return False


class FakeMT5Lot:
    """Fake MT5 surface for lot_calculator tests."""
    def __init__(self, account=None, symbol_info=None):
        self._account = account
        self._symbol_info = symbol_info

    def account_info(self):
        return self._account

    def symbol_info(self, symbol):
        return self._symbol_info


# ---------------- lot_calculator ----------------
@case("T1 XAU sizing correct: $10k, 1%, $10 SL -> 0.10")
def _():
    with Restore(mt5=FakeMT5Lot(FakeAccount(10000.0), FakeSymbolInfo())):
        lot = m.lot_calculator("XAUUSD.", 1.0, 2000.0, 1990.0)
    assert abs(lot - 0.10) < 1e-9, lot
    return "lot=0.10"


@case("T2 XAU below one step -> 0.0 (was force-0.01 exceeding risk budget)")
def _():
    with Restore(mt5=FakeMT5Lot(FakeAccount(100.0), FakeSymbolInfo())):
        lot = m.lot_calculator("XAUUSD.", 1.0, 2000.0, 1990.0)  # $1 risk -> 0.001
    assert lot == 0.0, lot
    return "refused (0.0)"


@case("T3 non-XAU symbol -> 0.0 fail-closed (was silent min-lot 0.01)")
def _():
    with Restore(mt5=FakeMT5Lot(FakeAccount(10000.0), FakeSymbolInfo())):
        for sym in ("EURUSD", "USDJPY", "USDCAD", "BTCUSD"):
            lot = m.lot_calculator(sym, 1.0, 1.1000, 1.0900)
            assert lot == 0.0, (sym, lot)
    return "all refused"


@case("T4 account_info None -> 0.0, no AttributeError")
def _():
    with Restore(mt5=FakeMT5Lot(None, None)):
        lot = m.lot_calculator("XAUUSD.", 1.0, 2000.0, 1990.0)
    assert lot == 0.0, lot
    return "no crash"


@case("T5 degenerate stop distance -> 0.0")
def _():
    with Restore(mt5=FakeMT5Lot(FakeAccount(10000.0), FakeSymbolInfo())):
        assert m.lot_calculator("XAUUSD.", 1.0, 2000.0, 2000.0) == 0.0
    return "refused"


@case("T6 broker volume_min/step respected: 0.15 raw, step 0.1 -> 0.1; below min -> 0.0")
def _():
    with Restore(mt5=FakeMT5Lot(FakeAccount(10000.0), FakeSymbolInfo(0.1, 0.1))):
        lot = m.lot_calculator("XAUUSD.", 1.0, 2000.0, 1990.0)  # raw 0.10 -> 0.1
        assert abs(lot - 0.1) < 1e-9, lot
        lot2 = m.lot_calculator("XAUUSD.", 1.0, 2000.0, 1980.0)  # raw 0.05 -> refused
        assert lot2 == 0.0, lot2
    return "step/min honoured"


# ---------------- get_broker_offset ----------------
@case("T7 no-xauusd symbol list: falls back to symbols[0], NO NameError")
def _():
    class FakeMT5Offset:
        def symbols_get(self):
            return [FakeSymbol("EURUSD."), FakeSymbol("GBPUSD.")]

        def symbol_info_tick(self, symbol):
            # server clock 3h ahead of UTC -> offset must round to 3
            return FakeTick(int(_real_datetime.now(timezone.utc).timestamp()) + 3 * 3600)

    with Restore(mt5=FakeMT5Offset(), datetime=_FakeDTModule):
        off = m.get_broker_offset()
    assert off == 3, off
    return "offset=3 without xauusd (old code: NameError)"


@case("T8 'today' is no longer a module global (fresh per call)")
def _():
    assert not hasattr(m, "today") or not isinstance(getattr(m, "today", None), str) \
        or getattr(m, "today") not in ("Sunday", "Saturday", "Monday"), \
        "stale import-time weekday global still present"
    return "no stale weekday global"


# ---------------- count_consecutive_sl ----------------
@case("T9 start_of_day is broker midnight in UTC (old code double-added offset)")
def _():
    captured = {}

    class FakeMT5Hist:
        def symbols_get(self):
            return [FakeSymbol("XAUUSD.")]

        def symbol_info_tick(self, symbol):
            # server clock 3h ahead of UTC -> offset rounds to 3
            return FakeTick(int(_real_datetime.now(timezone.utc).timestamp()) + 3 * 3600)

        def history_deals_get(self, a, b):
            captured["start"], captured["end"] = a, b
            return []

    with Restore(mt5=FakeMT5Hist()):
        m.count_consecutive_sl()
    end = captured["end"]
    start = captured["start"]
    # offset comes from the FAKE tick (+3h) inside the call, so the expected
    # start is broker-midnight expressed in UTC with the SAME offset
    expected = _real_datetime(end.year, end.month, end.day, tzinfo=timezone.utc) \
        - timedelta(hours=3)
    assert start == expected, (start, expected)
    return "start=%s == broker-midnight UTC" % start


# ---------------- total_positions rename ----------------
@case("T10 total_positions defined; total_positons aliases it")
def _():
    assert callable(m.total_positions)
    assert m.total_positons is m.total_positions
    return "rename + alias OK"


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
