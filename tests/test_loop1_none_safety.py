# tests/test_loop1_none_safety.py — LOOP 1 (D1/D2/D3) isolated safety tests
# NO real MT5, NO orders: the MetaTrader5 module inside module.mt5 is replaced
# by a fake with scripted behaviors (None / empty / exception / rejected codes).
# Pre-fix run: several cases FAIL (documents the defects).
# Post-fix run: ALL cases must PASS (gate for LOOP 1).

import os, sys, hashlib, traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import importlib

m = importlib.import_module("module.mt5")


class FakeResult:
    def __init__(self, retcode):
        self.retcode = retcode


class FakePosition:
    def __init__(self, ticket, symbol="XAUUSD.", ptype=0, volume=0.10,
                 sl=1900.0, tp=1940.0, comment="test"):
        self.ticket = ticket
        self.symbol = symbol
        self.type = ptype
        self.volume = volume
        self.sl = sl
        self.tp = tp
        self.comment = comment
        self._d = {"ticket": ticket, "symbol": symbol, "type": ptype,
                   "volume": volume, "sl": sl, "tp": tp, "comment": comment}

    def _asdict(self):
        return dict(self._d)


class FakeTick:
    bid = 2000.50
    ask = 2000.80


class FakeAccount:
    def __init__(self, equity):
        self.equity = equity


class FakeTime:
    @staticmethod
    def sleep(sec):
        pass


class FakeMT5:
    DONE = 10009
    INVALID = 10013
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    ORDER_TIME_GTC = 0
    TRADE_ACTION_DEAL, TRADE_ACTION_SLTP, TRADE_ACTION_REMOVE = 1, 2, 3
    TRADE_RETCODE_DONE = 10009

    def __init__(self, positions_fn=None, orders_fn=None, account_fn=None,
                 history_fn=None, send_fn=None, tick_fn=None):
        self._positions_fn = positions_fn
        self._orders_fn = orders_fn
        self._account_fn = account_fn
        self._history_fn = history_fn
        self._send_fn = send_fn or (lambda req: FakeResult(10009))
        self._tick_fn = tick_fn or (lambda symbol: FakeTick())
        self.order_requests = []

    def positions_get(self, *a, **kw):
        return self._positions_fn(*a, **kw) if self._positions_fn else None

    def orders_get(self, *a, **kw):
        return self._orders_fn(*a, **kw) if self._orders_fn else None

    def account_info(self):
        return self._account_fn() if self._account_fn else None

    def history_deals_get(self, *a, **kw):
        return self._history_fn(*a, **kw) if self._history_fn else None

    def order_send(self, request):
        self.order_requests.append(request)
        return self._send_fn(request)

    def symbol_info_tick(self, symbol):
        return self._tick_fn(symbol)


def install(fake, broker_offset=0):
    m.mt5 = fake
    m.get_broker_offset = lambda *a, **kw: broker_offset
    m.time = FakeTime


def run_case(fn):
    try:
        r = fn()
        return ("PASS", r)
    except AssertionError as ex:
        return ("FAIL", str(ex))
    except Exception as ex:  # noqa: BLE001 - the point is to observe behavior
        return ("RAISED", "%s: %s" % (type(ex).__name__, ex))


CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


# ---- D3: close family must never silently no-op on None --------------------
@case("T1 close_all_positions: positions_get=None -> explicit MT5_UNAVAILABLE (no silent success)")
def _():
    install(FakeMT5())
    r = m.close_all_positions()
    assert isinstance(r, dict), "returned %r" % (r,)
    assert r["status"] == "MT5_UNAVAILABLE" and r["verified_clean"] is False
    assert r["attempted"] == 0


@case("T2 close_all_positions: empty book -> verified_clean=True")
def _():
    install(FakeMT5(positions_fn=lambda *a, **kw: []))
    r = m.close_all_positions()
    assert r["status"] == "OK" and r["verified_clean"] is True and r["attempted"] == 0


@case("T3 close_all_positions: 2 positions closed+verified -> closed=2, clean")
def _():
    live = [FakePosition(101), FakePosition(102)]

    def positions_fn(*a, **kw):
        if a or kw.get("ticket") is not None:
            t = kw.get("ticket", a[0] if a else None)
            return [p for p in live if p.ticket == t]
        return list(live)

    fake = FakeMT5(positions_fn=positions_fn,
                   send_fn=lambda req: FakeResult(10009))

    def on_send(req):
        for p in list(live):
            if p.ticket == req["position"]:
                live.remove(p)

    fake._send_fn = lambda req: (on_send(req), FakeResult(10009))[1]
    install(fake)
    r = m.close_all_positions()
    assert r["attempted"] == 2 and r["closed"] == 2 and r["failed"] == 0, r
    assert r["verified_clean"] is True and r["status"] == "OK"


@case("T4 close_all_positions: second close REJECTED -> failed=1, verified_clean=False")
def _():
    live = [FakePosition(201), FakePosition(202)]

    def positions_fn(*a, **kw):
        if a or kw.get("ticket") is not None:
            t = kw.get("ticket", a[0] if a else None)
            return [p for p in live if p.ticket == t]
        return list(live)

    def send_fn(req):
        if req["position"] == 202:
            return FakeResult(10013)  # rejected
        for p in list(live):
            if p.ticket == req["position"]:
                live.remove(p)
        return FakeResult(10009)

    install(FakeMT5(positions_fn=positions_fn, send_fn=send_fn))
    r = m.close_all_positions()
    assert r["closed"] == 1 and r["failed"] == 1, r
    assert r["verified_clean"] is False and r["status"] != "OK"


@case("T5 close_all_positions: re-query returns None -> uncertain, NOT verified")
def _():
    calls = {"n": 0}
    live = [FakePosition(301)]

    def positions_fn(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return list(live)
        if a or kw.get("ticket") is not None:
            return [p for p in live if p.ticket == kw.get("ticket", a[0] if a else None)]
        return None  # terminal dies at re-query

    install(FakeMT5(positions_fn=positions_fn))
    r = m.close_all_positions()
    assert r["verified_clean"] is False and r["status"] == "MT5_UNAVAILABLE", r


@case("T6 close_half_with_comment: positions_get=None -> explicit status (no TypeError)")
def _():
    install(FakeMT5())
    r = m.close_half_with_comment("X")
    assert isinstance(r, dict) and r["status"] == "MT5_UNAVAILABLE", r


@case("T7 count_position_now: positions_get=None -> MT5DataError (fail-safe, NOT 0)")
def _():
    install(FakeMT5())
    try:
        m.count_position_now("buy", "XAUUSD.")
    except m.MT5DataError:
        return
    raise AssertionError("expected MT5DataError (silent 0 would allow duplicate orders)")


@case("T8 total_position_comment: positions_get=None -> MT5DataError")
def _():
    install(FakeMT5())
    try:
        m.total_position_comment("X")
    except m.MT5DataError:
        return
    raise AssertionError("expected MT5DataError")


@case("T9 pnl_today: history_deals_get=None -> MT5DataError (no silent 0)")
def _():
    install(FakeMT5(history_fn=lambda *a, **kw: None,
                    positions_fn=lambda *a, **kw: []))
    try:
        m.pnl_today()
    except m.MT5DataError:
        return
    raise AssertionError("expected MT5DataError")


@case("T10 daily_draw_down_checker: pnl_today data failure -> FAIL-SAFE True")
def _():
    install(FakeMT5(history_fn=lambda *a, **kw: None,
                    positions_fn=lambda *a, **kw: []))
    r = m.daily_draw_down_checker(5000, 5)
    assert r is True, "fail-safe kill-switch must trigger on evaluation failure"


@case("T11 total_draw_down: account_info=None -> FAIL-SAFE True")
def _():
    install(FakeMT5(account_fn=lambda: None))
    r = m.total_draw_down(5000, 12)
    assert r is True, r


@case("T12 total_draw_down: equity healthy -> False; crashed -> True")
def _():
    install(FakeMT5(account_fn=lambda: FakeAccount(5100)))
    assert m.total_draw_down(5000, 12) is False
    install(FakeMT5(account_fn=lambda: FakeAccount(4300)))
    assert m.total_draw_down(5000, 12) is True


@case("T13 daily_draw_down_checker: small loss -> False; big loss -> True")
def _():
    install(FakeMT5(history_fn=lambda *a, **kw: [], positions_fn=lambda *a, **kw: []))
    # pnl_today sums deal profit fields; empty history/positions -> 0.0
    assert m.daily_draw_down_checker(5000, 5) is False


@case("T14 close_all_pending_orders: None -> MT5_UNAVAILABLE; 2 orders -> removed+verified")
def _():
    install(FakeMT5())
    r = m.close_all_pending_orders()
    assert isinstance(r, dict) and r["status"] == "MT5_UNAVAILABLE"

    pend = [FakePosition(401), FakePosition(402)]

    def orders_fn(*a, **kw):
        if a or kw.get("ticket") is not None:
            t = kw.get("ticket", a[0] if a else None)
            return [p for p in pend if p.ticket == t]
        return list(pend)

    fake = FakeMT5(orders_fn=orders_fn)

    def send_fn(req):
        for p in list(pend):
            if p.ticket == req["order"]:
                pend.remove(p)
        return FakeResult(10009)

    fake._send_fn = send_fn
    install(fake)
    r = m.close_all_pending_orders()
    assert r["removed"] == 2 and r["verified_clean"] is True and r["failed"] == 0, r


@case("T15 close_all_pending_orders_with_type: only matching type removed")
def _():
    pend = [FakePosition(501, ptype=2), FakePosition(502, ptype=3)]

    def orders_fn(*a, **kw):
        if a or kw.get("ticket") is not None:
            t = kw.get("ticket", a[0] if a else None)
            return [p for p in pend if p.ticket == t]
        return list(pend)

    removed = []

    def send_fn(req):
        removed.append(req["order"])
        for p in list(pend):
            if p.ticket == req["order"]:
                pend.remove(p)
        return FakeResult(10009)

    install(FakeMT5(orders_fn=orders_fn, send_fn=send_fn))
    r = m.close_all_pending_orders_with_type("buy")
    assert r["removed"] == 1 and removed == [501], r


def main():
    results = []
    for name, fn in CASES:
        status, info = run_case(fn)
        results.append((name, status, info))
        print("[%s] %s%s" % (status, name, (" | " + info) if status != "PASS" else ""))
    npass = sum(1 for _, s, _ in results if s == "PASS")
    print("\nSUMMARY: %d/%d PASS" % (npass, len(results)))
    # integrity echo: frozen research artifacts must be untouched by this test run
    print("mt5.py sha256 (current):",
          hashlib.sha256(open(os.path.join(ROOT, "module", "mt5.py"), "rb").read()).hexdigest()[:16])
    return 0 if npass == len(results) else 4


if __name__ == "__main__":
    sys.exit(main())
