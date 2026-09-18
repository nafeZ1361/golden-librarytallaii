# tests/test_loop2_risk_cap.py — LOOP 2 (D4/D5) tests
# D4: no code path can size risk above HARD_RISK_CAP_PERCENT (2.0), including
#     adversarial callers passing risk=50 or max_risk=100.
# D5: bot.ipynb first cell contains the production guard; bot_runner.py remains
#     the authorized entry point; no real MT5, no orders.

import os, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import importlib

m = importlib.import_module("module.mt5")

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("T1 HARD_RISK_CAP_PERCENT exists and == 2.0")
def _():
    assert getattr(m, "HARD_RISK_CAP_PERCENT", None) == 2.0


@case("T2 risk_corrector: adversarial (risk=50, max_risk=100, huge deficit) -> <= 2.0")
def _():
    m.count_tp = lambda: 3
    m.profit_today = lambda: -100000.0  # adversarial deficit
    r = m.risk_corrector(risk=50, starting_balance=5000, rr=2, max_risk=100)
    assert r <= m.HARD_RISK_CAP_PERCENT, r


@case("T3 risk_corrector: normal escalation attempt (risk=1, deficit) -> between 1 and 2")
def _():
    m.count_tp = lambda: 3
    # profit_today would need MT5; monkeypatch to a big loss to force deficit
    m.profit_today = lambda: -100000.0
    r = m.risk_corrector(risk=1.0, starting_balance=5000, rr=2, max_risk=100)
    assert 1.0 <= r <= 2.0, r


@case("T4 risk_corrector: no deficit -> returns base risk (<= cap)")
def _():
    m.count_tp = lambda: 3
    m.profit_today = lambda: 100000.0
    r = m.risk_corrector(risk=1.0, starting_balance=5000, rr=2, max_risk=100)
    assert r <= 2.0, r


@case("T5 risk_corrector_comment: adversarial -> <= 2.0")
def _():
    m.count_org_tp_comment = lambda c: 5
    m.total_profit_today_with_comment = lambda c: -100000.0
    r = m.risk_corrector_comment("X", risk=25, starting_balance=5000, rr=2, max_risk=100)
    assert r <= m.HARD_RISK_CAP_PERCENT, r


@case("T6 risk_corrector_comment: escalation capped at 2.0 exactly")
def _():
    m.count_org_tp_comment = lambda c: 5
    m.total_profit_today_with_comment = lambda c: -100000.0
    r = m.risk_corrector_comment("X", risk=1.0, starting_balance=5000, rr=2, max_risk=100)
    assert r == 2.0, r


@case("T7 bot.ipynb first cell = production guard (D5)")
def _():
    nb = json.load(open(os.path.join(ROOT, "bot.ipynb"), encoding="utf-8"))
    first_src = "".join(nb["cells"][0]["source"])
    assert "ALLOW_NOTEBOOK_TRADING" in first_src, "guard missing"
    assert "bot_runner.py" in first_src


@case("T8 guard actually blocks: raising SystemExit when env unset")
def _():
    os.environ.pop("ALLOW_NOTEBOOK_TRADING", None)
    nb = json.load(open(os.path.join(ROOT, "bot.ipynb"), encoding="utf-8"))
    guard_src = "".join(nb["cells"][0]["source"])
    try:
        exec(compile(guard_src, "guard", "exec"), {"__name__": "__main__"})
    except SystemExit as ex:
        assert "not a production" in str(ex)
        return
    raise AssertionError("guard did not block")


@case("T9 bot_runner.py is intact: config present, escalator never CALLED")
def _():
    import re
    src = open(os.path.join(ROOT, "bot_runner.py"), encoding="utf-8").read()
    assert "DRY_RUN" in src and "ALLOW_LIVE" in src and "RISK_PCT" in src
    assert not re.search(r"risk_corrector\w*\s*\(", src), \
        "escalator must never be CALLED in the runner (docstring mention is fine)"


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
