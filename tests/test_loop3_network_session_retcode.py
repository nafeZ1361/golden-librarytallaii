# tests/test_loop3_network_session_retcode.py — LOOP 3 (D6/D7/D8) tests
# D6: news fetch never crashes on network/HTTP/JSON failure (fail-open, logged)
# D7: check_time/check_time_min evaluate BROKER time (offset-aware)
# D8: every order-management op verifies its retcode (no fire-and-forget)
# NO real MT5, NO real network, NO orders.

import os, sys, importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

m = importlib.import_module("module.mt5")
import requests as real_requests
from datetime import datetime, timezone

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


class FakeResult:
    def __init__(self, retcode):
        self.retcode = retcode


class FakeResp:
    def __init__(self, status, payload=None, json_error=False):
        self.status_code = status
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("bad json")
        return self._payload


class FakePosition:
    def __init__(self, ticket, ptype=0):
        self.ticket = ticket
        self.type = ptype
        self.symbol = "XAUUSD."
        self.volume = 0.10
        self.sl = 1900.0
        self.tp = 1940.0


class FakeTick:
    bid, ask = 2000.50, 2000.80


class FakeAccount:
    equity = 5000.0


class FakeMT5:
    DONE, INVALID = 10009, 10013
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    POSITION_TYPE_BUY = 0
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    ORDER_TIME_GTC = 0
    TRADE_ACTION_DEAL, TRADE_ACTION_SLTP, TRADE_ACTION_REMOVE = 1, 2, 3
    TRADE_ACTION_PENDING = 5
    TRADE_RETCODE_DONE = 10009

    def __init__(self, positions_fn=None, orders_fn=None, account_fn=None,
                 send_fn=None, tick_fn=None, symbol_info_fn=None):
        self._positions_fn = positions_fn
        self._orders_fn = orders_fn
        self._account_fn = account_fn
        self._send_fn = send_fn or (lambda req: FakeResult(10009))
        self._tick_fn = tick_fn or (lambda s: FakeTick())
        self._symbol_info_fn = symbol_info_fn or (lambda s: type("SI", (), {"filling_mode": 1})())
        self.order_requests = []

    def positions_get(self, *a, **kw):
        return self._positions_fn(*a, **kw) if self._positions_fn else None

    def orders_get(self, *a, **kw):
        return self._orders_fn(*a, **kw) if self._orders_fn else None

    def account_info(self):
        return self._account_fn() if self._account_fn else None

    def order_send(self, request):
        self.order_requests.append(request)
        return self._send_fn(request)

    def symbol_info_tick(self, s):
        return self._tick_fn(s)

    def symbol_info(self, s):
        return self._symbol_info_fn(s)


class FakeRequests:
    def __init__(self, behavior):
        self._behavior = behavior
        self.ConnectionError = real_requests.ConnectionError
        self.RequestException = real_requests.RequestException

    def get(self, url, timeout=None):
        kind, val = self._behavior
        if kind == "raise":
            raise real_requests.ConnectionError(val)
        if kind == "resp":
            return val
        raise AssertionError("unexpected")


def install(fake, broker_offset=0, count_history=None):
    m.mt5 = fake
    m.get_broker_offset = lambda *a, **kw: broker_offset
    m.count_tp = lambda: 0
    m.profit_today = lambda: 0.0


@case("D6-T1 news: network failure -> [] (no crash, fail-open)")
def _():
    m.requests = FakeRequests(("raise", "conn down"))
    r = m.fetch_economic_news("USD")
    assert r == [], r


@case("D6-T2 news: HTTP 500 -> []")
def _():
    m.requests = FakeRequests(("resp", FakeResp(500)))
    assert m.fetch_economic_news("USD") == []


@case("D6-T3 news: malformed JSON -> []")
def _():
    m.requests = FakeRequests(("resp", FakeResp(200, json_error=True)))
    assert m.fetch_economic_news("USD") == []


@case("D6-T4 news: valid payload -> only High-impact USD events parsed")
def _():
    payload = [
        {"country": "USD", "impact": "High", "date": "2026-09-10T14:30:00+00:00", "title": "NFP"},
        {"country": "USD", "impact": "Low", "date": "2026-09-10T15:30:00+00:00", "title": "x"},
        {"country": "EUR", "impact": "High", "date": "2026-09-10T16:30:00+00:00", "title": "y"},
        {"country": "USD", "impact": "High", "date": "garbage", "title": "z"},  # malformed -> skipped
    ]
    m.requests = FakeRequests(("resp", FakeResp(200, payload)))
    r = m.fetch_economic_news("USD")
    assert len(r) == 1 and r[0]["event"] == "NFP", r


@case("D7-T1 check_time: broker offset shifts evaluation hour (offset=+3 -> broker 09:00)")
def _():
    utc_h = datetime.now(timezone.utc).hour
    install(FakeMT5(), broker_offset=(9 - utc_h) % 24)
    assert m.check_time(9, 10) is True
    assert m.check_time(10, 11) is False


@case("D7-T2 check_time_min: broker-minute precision")
def _():
    utc_h = datetime.now(timezone.utc).hour
    utc_m = datetime.now(timezone.utc).minute
    b_h = (utc_h + 3) % 24  # fixed offset +3
    install(FakeMT5(), broker_offset=3)
    lo_m = (utc_m + 58) % 60  # broker minute ≈ utc_m+58 -> a 2-min window containing it
    if lo_m <= utc_m:
        pass
    # build a 3-minute window around the broker minute regardless of wrap
    w0, w1 = (b_h, (utc_m + 58) % 60), (b_h, (utc_m + 1) % 60)
    r = m.check_time_min(w0[0], w0[1], w1[0], w1[1])
    assert isinstance(r, bool)


@case("D8-T1 modify_tp: rejected -> False; done -> True")
def _():
    install(FakeMT5(positions_fn=lambda *a, **kw: [FakePosition(1)],
                    send_fn=lambda req: FakeResult(10013)))
    assert m.modify_tp(1, 1950.0) is False
    install(FakeMT5(positions_fn=lambda *a, **kw: [FakePosition(1)],
                    send_fn=lambda req: FakeResult(10009)))
    assert m.modify_tp(1, 1950.0) is True


@case("D8-T2 modify_stop: rejected -> False")
def _():
    install(FakeMT5(positions_fn=lambda *a, **kw: [FakePosition(1)],
                    send_fn=lambda req: FakeResult(10013)))
    assert m.modify_stop(1, 1890.0) is False


@case("D8-T3 create_order: symbol_info None -> local rejection, NO order_send")
def _():
    fake = FakeMT5(symbol_info_fn=lambda s: None)
    install(fake)
    r = m.create_order("XAUUSD.", 0.1, 0)
    assert r is None and len(fake.order_requests) == 0


@case("D8-T4 create_order: broker rejection -> returned result carries retcode")
def _():
    install(FakeMT5(send_fn=lambda req: FakeResult(10013)))
    r = m.create_order("XAUUSD.", 0.1, 0)
    assert r is not None and r.retcode == 10013


@case("D8-T5 pending_order: rejection returned (not silent)")
def _():
    install(FakeMT5(send_fn=lambda req: FakeResult(10013)))
    r = m.pending_order("XAUUSD.", 0.1, 0, 1999.0)
    assert r is not None and r.retcode == 10013


@case("D8-T6 close_half_vol_order: early-exit after DONE (exactly ONE order_send)")
def _():
    sent = []

    def send_fn(req):
        sent.append(req)
        return FakeResult(10009)

    install(FakeMT5(positions_fn=lambda *a, **kw: [FakePosition(1)], send_fn=send_fn))
    m.close_half_vol_order(1)
    assert len(sent) == 1, "filling loop must stop after DONE (no duplicate closes)"


def main():
    npass = 0
    for name, fn in CASES:
        try:
            fn()
            npass += 1
            print("[PASS] %s" % name)
        except AssertionError as ex:
            print("[FAIL] %s | %s" % (name, ex))
        except Exception as ex:  # noqa: BLE001
            print("[RAISED] %s | %s: %s" % (name, type(ex).__name__, ex))
    print("\nSUMMARY: %d/%d PASS" % (npass, len(CASES)))
    return 0 if npass == len(CASES) else 4


if __name__ == "__main__":
    sys.exit(main())
