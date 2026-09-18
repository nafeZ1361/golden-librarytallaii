# tests/test_loop4_quarantine_credentials.py — LOOP 4 (D9/D10/D12) tests

import os, sys, importlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("TELEGRAM_CHANNEL_ID", None)

tg = importlib.import_module("module.telegram")
stg = importlib.import_module("module.stg")

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


@case("T1 telegram imports without telebot installed (import-safe)")
def _():
    assert tg.TELEGRAM_AVAILABLE in (True, False)
    assert tg.bot is None or tg.TELEGRAM_AVAILABLE is True


@case("T2 no hardcoded placeholder token remains; unconfigured -> bot is None")
def _():
    src = open(os.path.join(ROOT, "module", "telegram.py"), encoding="utf-8").read()
    assert "yorToken" not in src, "placeholder token still hardcoded"
    assert "337250342" not in src, "channel id still hardcoded"
    assert tg.TOKEN == "" and tg.CHANNEL_ID == "" and tg.bot is None


@case("T3 send functions no-op safely when unconfigured (no exception, no token leak)")
def _():
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert tg.send_message_to_channel("hello") is False
        assert tg.send_image_to_channel("whatever.png") is False
    out = buf.getvalue()
    assert "TESTTOKEN" not in out and "yorToken" not in out


@case("T4 env-provided credentials are picked up (no hardcode)")
def _():
    os.environ["TELEGRAM_BOT_TOKEN"] = "ENVTESTTOKEN"
    tg2 = importlib.reload(tg)
    assert tg2.TOKEN == "ENVTESTTOKEN" or tg2.bot is not None
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    importlib.reload(tg)  # restore unconfigured state


@case("T5 abcd_strategy is QUARANTINED (banner present, function intact)")
def _():
    src = open(os.path.join(ROOT, "module", "stg.py"), encoding="utf-8").read()
    assert "QUARANTINED (CP19 LOOP-4 / D9)" in src
    assert "def abcd_strategy(" in src  # function still exists (not deleted)
    assert hasattr(stg, "abcd_strategy")


@case("T6 Gartley/Butterfly registered as MISSING DEPENDENCY (no hidden def, audit doc updated)")
def _():
    stg_src = open(os.path.join(ROOT, "module", "stg.py"), encoding="utf-8").read()
    assert "def Gartley" not in stg_src and "def Butterfly" not in stg_src
    audit = open(os.path.join(ROOT, "project_audit",
                              "CP19_ENGINEERING_SAFETY_AUDIT.md"), encoding="utf-8").read()
    assert "MISSING DEPENDENCY" in audit


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
