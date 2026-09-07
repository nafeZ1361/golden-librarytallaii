# tests/test_cp20_integration.py — CP20 INTEGRATION SAFETY TEST
# 12 mandatory failure scenarios, exercised IN COMBINATION through the same
# module surface the runner uses. Mock/stub only — NO real MT5, NO orders.

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


class FakePosition:
    def __init__(self, ticket, ptype=0, comment="X"):
        self.ticket = ticket
        self.type = ptype
        self.comment = comment
        self.symbol = "XAUUSD."
        self.volume = 0.10
        self.sl = 1900.0
        self.tp = 1940.0

    def _asdict(self):
        return {"ticket": self.ticket, "symbol": self.symbol, "type": self.type,
                "volume": self.volume, "sl": self.sl, "tp": self.tp,
                "comment": self.comment}


class FakeTick:
    bid, ask = 2000.50, 2000.80


class FakeAccount:
    def __init__(self, equity):
        self.equity = equity


class FakeResp:
    def __init__(self, status):
        self.status_code = status

    def json(self):
        return []


class FakeTime:
    @staticmethod
    def sleep(sec):
        pass


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
                 history_fn=None, send_fn=None, tick_fn=None, symbol_info_fn=None):
        self._positions_fn = positions_fn
        self._orders_fn = orders_fn
        self._account_fn = account_fn
        self._history_fn = history_fn
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

    def history_deals_get(self, *a, **kw):
        return self._history_fn(*a, **kw) if self._history_fn else None

    def order_send(self, request):
        self.order_requests.append(request)
        return self._send_fn(request)

    def symbol_info_tick(self, s):
        return self._tick_fn(s)

    def symbol_info(self, s):
        return self._symbol_info_fn(s)


class FakeRequests:
    RequestException = real_requests.RequestException

    def __init__(self, behavior):
        self._behavior = behavior

    def get(self, url, timeout=None):
        kind, val = self._behavior
        if kind == "raise":
            raise real_requests.ConnectionError(val)
        return val


def install(fake, broker_offset=0, count_tp=0, profit=0.0, pnl=None,
            stub_pnl=True):
    m.mt5 = fake
    m.get_broker_offset = lambda *a, **kw: broker_offset
    m.time = FakeTime
    m.count_tp = lambda: count_tp
    if pnl is not None:
        m.pnl_today = pnl
    elif stub_pnl:
        m.pnl_today = lambda: profit
    # else: leave the REAL pnl_today in place (fail-safe path under test)


def utc_h():
    return datetime.now(timezone.utc).hour


# ---- 1) MT5 fully unavailable: the system must HALT SAFELY -----------------
@case("INT1 MT5 unavailable: kill-switches fail-safe TRIGGERED, closes report MT5_UNAVAILABLE, news fail-open")
def _():
    install(FakeMT5(), stub_pnl=False)  # real pnl_today vs all-None MT5
    assert m.daily_draw_down_checker(5000, 5) is True
    assert m.total_draw_down(5000, 12) is True
    r = m.close_all_positions()
    assert r["status"] == "MT5_UNAVAILABLE" and r["verified_clean"] is False
    m.requests = FakeRequests(("raise", "down"))
    assert m.fetch_economic_news("USD") == []


# ---- 2) positions_get() = None ---------------------------------------------
@case("INT2 positions_get=None: closes refuse silently-no-op; counters raise (fail-safe)")
def _():
    install(FakeMT5())
    r = m.close_all_positions()
    assert r["status"] == "MT5_UNAVAILABLE" and r["attempted"] == 0
    try:
        m.count_position_now("buy", "XAUUSD.")
        raise AssertionError("expected MT5DataError")
    except m.MT5DataError:
        pass


# ---- 3) account_info() = None ----------------------------------------------
@case("INT3 account_info=None: total_draw_down fail-safe TRIGGERED")
def _():
    install(FakeMT5(account_fn=lambda: None))
    assert m.total_draw_down(5000, 12) is True


# ---- 4) network failure -----------------------------------------------------
@case("INT4 network failure: news fail-open [], kill-switches still evaluate")
def _():
    m.requests = FakeRequests(("raise", "no network"))
    install(FakeMT5(account_fn=lambda: FakeAccount(5000),
                    history_fn=lambda *a, **kw: [], positions_fn=lambda *a, **kw: []))
    assert m.fetch_economic_news("USD") == []
    assert m.daily_draw_down_checker(5000, 5) is False  # healthy book evaluates


# ---- 5) news service failure (HTTP 503) ------------------------------------
@case("INT5 news HTTP 503: fail-open [] with log")
def _():
    m.requests = FakeRequests(("resp", FakeResp(503)))
    assert m.fetch_economic_news("USD") == []


# ---- 6) order rejection -----------------------------------------------------
@case("INT6 create_order rejected: retcode surfaced, no success claim")
def _():
    install(FakeMT5(send_fn=lambda req: FakeResult(10013)))
    r = m.create_order("XAUUSD.", 0.1, 0)
    assert r.retcode == 10013


# ---- 7) close rejection -----------------------------------------------------
@case("INT7 close rejected: failed=1, verified_clean=False")
def _():
    live = [FakePosition(701)]

    def positions_fn(*a, **kw):
        if a or kw.get("ticket") is not None:
            t = kw.get("ticket", a[0] if a else None)
            return [p for p in live if p.ticket == t]
        return list(live)

    def send_fn(req):
        return FakeResult(10013)

    install(FakeMT5(positions_fn=positions_fn, send_fn=send_fn))
    r = m.close_all_positions()
    assert r["failed"] == 1 and r["verified_clean"] is False


# ---- 8) invalid tick --------------------------------------------------------
@case("INT8 invalid tick (None): close_order and create_order refuse locally")
def _():
    install(FakeMT5(positions_fn=lambda *a, **kw: [FakePosition(801)],
                    tick_fn=lambda s: None))
    assert m.close_order(801) is None
    r = m.create_order("XAUUSD.", 0.1, 0)
    assert r is None


# ---- 9) session closed ------------------------------------------------------
@case("INT9 session closed: check_time False for outside-hours window")
def _():
    utc_h = utc_h_fn()
    install(FakeMT5(), broker_offset=(3 - utc_h) % 24)  # force broker hour = 03
    assert m.check_time(3, 4) is True
    assert m.check_time(5, 6) is False


def utc_h_fn():
    return datetime.now(timezone.utc).hour


# ---- 10) excessive risk -----------------------------------------------------
@case("INT10 excessive risk: escalator hard-capped at 2.0 under adversarial input")
def _():
    install(FakeMT5())
    m.count_tp = lambda: 5
    m.profit_today = lambda: -100000.0
    r = m.risk_corrector(risk=50, starting_balance=5000, rr=2, max_risk=100)
    assert r <= m.HARD_RISK_CAP_PERCENT == 2.0


# ---- 11) duplicate invocation ----------------------------------------------
@case("INT11 duplicate close invocation: idempotent, second call sees empty book")
def _():
    live = [FakePosition(1101)]

    def positions_fn(*a, **kw):
        if a or kw.get("ticket") is not None:
            t = kw.get("ticket", a[0] if a else None)
            return [p for p in live if p.ticket == t]
        return list(live)

    def send_fn(req):
        for p in list(live):
            if p.ticket == req["position"]:
                live.remove(p)
        return FakeResult(10009)

    install(FakeMT5(positions_fn=positions_fn, send_fn=send_fn))
    r1 = m.close_all_positions()
    r2 = m.close_all_positions()
    assert r1["closed"] == 1 and r1["verified_clean"] is True
    assert r2["attempted"] == 0 and r2["verified_clean"] is True and r2["status"] == "OK"


# ---- 12) exception inside safety gate ---------------------------------------
@case("INT12 exception inside safety gate: broad fail-safe TRIGGERED")
def _():
    def boom():
        raise ValueError("unexpected deal record")
    install(FakeMT5())
    m.pnl_today = boom
    assert m.daily_draw_down_checker(5000, 5) is True


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
