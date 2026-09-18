# tests/test_monitor_bot.py — CP23 monitor bot safety + behavior tests
# The monitor bot MUST be read-only: no order capability, allowlist fail-closed,
# import-safe without telebot, status/health text builders correct.

import os, sys, importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_ALLOWED_CHATS", None)

mb = importlib.import_module("module.monitor_bot")

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("T1 import-safe without telebot/token; bot object is None")
def _():
    assert mb.MONITOR_AVAILABLE in (True, False)
    assert mb.bot is None and mb.TOKEN == ""


@case("T2 NO order capability: no real order-API CALLS in the source")
def _():
    import re
    src = open(os.path.join(ROOT, "module", "monitor_bot.py"), encoding="utf-8").read()
    # match actual call sites, not documentation mentions
    patterns = [r"order_send\s*\(", r"create_order\s*\(", r"pending_order\s*\(",
                r"close_order\s*\(", r"close_all\w*\s*\(", r"modify_tp\s*\(",
                r"modify_stop\s*\(", r"remove_order\s*\(", r"positions_get\s*\(",
                r"history_deals_get\s*\(", r"import\s+MetaTrader5"]
    for pat in patterns:
        assert not re.search(pat, src), "order capability found: %s" % pat


@case("T3 allowlist fail-closed: no allowlist configured -> EVERYONE denied")
def _():
    mb.ALLOWED_CHATS = set()
    assert mb.is_allowed(12345) is False
    assert mb.is_allowed("12345") is False


@case("T4 allowlist: configured ID allowed, others denied (str/int both)")
def _():
    mb.ALLOWED_CHATS = {"111", "222"}
    assert mb.is_allowed(111) is True
    assert mb.is_allowed("111") is True
    assert mb.is_allowed(999) is False
    mb.ALLOWED_CHATS = set()  # restore fail-closed default


@case("T5 status text: contains the real verdicts and tags")
def _():
    txt = mb.build_status_text()
    assert "NO PROVEN EDGE" in txt and "DENIED" in txt
    assert "baseline-lock-v1" in txt and "cp5-source-freeze-v1" in txt
    assert "5/10" in txt


@case("T6 health text: frozen spot-checks report OK (data intact)")
def _():
    txt = mb.build_health_text()
    assert txt.count("OK") >= 3, txt
    assert "MISMATCH" not in txt and "MISSING" not in txt.split("research artifacts")[0]


@case("T7 events text: contract is DORMANT with registered trigger")
def _():
    txt = mb.build_events_text()
    assert "DORMANT" in txt and "300" in txt


@case("T8 command dispatch honors allowlist (denied returns [denied])")
def _():
    mb.ALLOWED_CHATS = {"111"}
    msg = type("M", (), {"chat": type("C", (), {"id": 999})()})()
    assert mb.cmd_status(msg) == "[denied]"
    mb.ALLOWED_CHATS = set()


@case("T9 bot_runner: notify wiring present, order path untouched by telegram")
def _():
    src = open(os.path.join(ROOT, "bot_runner.py"), encoding="utf-8").read()
    assert "send_message_to_channel" in src  # notify wiring exists
    import re
    assert not re.search(r"risk_corrector\w*\s*\(", src)  # escalator never called


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
