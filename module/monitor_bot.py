# module/monitor_bot.py — CP23: READ-ONLY Telegram monitor bot
#
# Purpose: remote visibility into the project (status/health/monitoring) via
# Telegram. CONNECTS the project to Telegram for NOTIFICATIONS and QUERIES.
#
# HARD SAFETY RULES (structural, verified by tests/test_monitor_bot.py):
#   1. This module contains NO order capability: it never imports or calls
#      create_order / pending_order / close_* / modify_* / order_send. It
#      CANNOT trade — by construction (research verdict: NO PROVEN EDGE,
#      LIVE DENIED).
#   2. READ-ONLY commands only: /start /help /status /health /events.
#   3. Access control: only chat IDs listed in TELEGRAM_ALLOWED_CHATS
#      (comma-separated numeric IDs) may use commands — fail-closed.
#   4. Credentials: TELEGRAM_BOT_TOKEN via environment only; never printed.
#   5. Import-safe: if telebot is not installed, the module imports with
#      MONITOR_AVAILABLE=False and every command function stays testable.

import os
import os as _os
import subprocess as _subprocess
import hashlib as _hashlib
import json as _json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

try:
    import telebot
    MONITOR_AVAILABLE = True
except ImportError:
    telebot = None
    MONITOR_AVAILABLE = False

TOKEN = _os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHATS = {s.strip() for s in _os.environ.get(
    "TELEGRAM_ALLOWED_CHATS", "").split(",") if s.strip()}

bot = telebot.TeleBot(TOKEN) if (MONITOR_AVAILABLE and TOKEN) else None

# CP23 LOOP: route the Telegram API through a local proxy when configured
# (TELEGRAM_PROXY, e.g. http://127.0.0.1:8227) — api.telegram.org is blocked
# on some networks; the desktop app already uses such a path.
PROXY = _os.environ.get("TELEGRAM_PROXY", "")
if MONITOR_AVAILABLE and telebot is not None and PROXY:
    telebot.apihelper.proxy = {"http": PROXY, "https": PROXY}


def is_allowed(chat_id):
    """Fail-closed: if no allowlist is configured, EVERYONE is denied."""
    if not ALLOWED_CHATS:
        return False
    return str(chat_id) in ALLOWED_CHATS


def _git(*args):
    try:
        return _subprocess.run(["git"] + list(args), capture_output=True,
                               text=True, cwd=ROOT, timeout=20).stdout.strip()
    except Exception as ex:  # noqa: BLE001
        return "unavailable (%r)" % (ex,)


def _sha256_file(path):
    h = _hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _file_sha16(rel):
    try:
        return _sha256_file(os.path.join(ROOT, rel))[:16]
    except OSError:
        return "MISSING"


def build_status_text():
    lines = ["== GOLDEN LIBRARY — STATUS =="]
    lines.append("branch: %s | HEAD: %s" % (_git("branch", "--show-current"),
                                            _git("rev-parse", "--short", "HEAD")))
    lines.append("research verdict: NO PROVEN EDGE (CP9/CP18 — unchanged)")
    lines.append("live authorization: DENIED")
    lines.append("safety status: PASS (CP19-CP22)")
    lines.append("variant budget: 5/10 consumed (A1-v1, A2-v1, A2-v2, fade, session)")
    lines.append("forward monitoring: DORMANT — one-shot eval at >=300 events or 180d")
    lines.append("tags: baseline-lock-v1 | cp5-source-freeze-v1 | cp5-source-freeze-v1")
    return "\n".join(lines)


def build_health_text():
    lines = ["== HEALTH CHECK =="]
    checks = []
    for rel, expect in [
        ("project_audit/stability_windows_cache/cp5_window_1_df.csv",
         json_identity_cp5()),
        ("project_audit/stability_windows_cache/cp6_window_1_df.csv",
         json_identity_cp6()),
        ("project_audit/stability_windows_cache/r1_window_1_df.csv",
         json_identity_r1()),
    ]:
        ok = (_file_sha16(rel) == expect[:16]) if expect else False
        checks.append("%s: %s" % (os.path.basename(rel), "OK" if ok else "MISMATCH/MISSING"))
    lines.append("frozen data spot-checks: " + " | ".join(checks))
    clean = _git("status", "--porcelain")
    tracked_dirty = [l for l in clean.splitlines() if not l.startswith("??")]
    lines.append("working tree (tracked): %s" % ("CLEAN" if not tracked_dirty else "DIRTY"))
    lines.append("untracked groups: %d" % sum(1 for l in clean.splitlines() if l.startswith("??")))
    lines.append("research artifacts: %s" % ("present" if os.path.exists(
        os.path.join(ROOT, "project_audit", "FINAL_PROJECT_VERDICT.md")) else "MISSING"))
    return "\n".join(lines)


def _manifest_first_sha(fname, key="windows"):
    try:
        with open(os.path.join(ROOT, "project_audit", fname), encoding="utf-8") as f:
            man = _json.load(f)
        if key == "windows":
            return man["windows"][0]["sha256"]
        return man.get("dataset_sha256_combined", "")
    except Exception:  # noqa: BLE001
        return ""


def json_identity_cp5():
    return _manifest_first_sha("CP5_DATA_FREEZE_manifest.json")


def json_identity_cp6():
    return _manifest_first_sha("CP6_OOS_DATA_FREEZE_manifest.json")


def json_identity_r1():
    return _manifest_first_sha("CYCLE_R1_OOS_FREEZE_manifest.json")


def build_events_text():
    lines = ["== FORWARD MONITORING =="]
    lines.append("contract: DORMANT (one-shot eval at >=300 events or 180d)")
    try:
        with open(os.path.join(ROOT, "project_audit",
                               "FORWARD_MONITORING_CONTRACT.md"), encoding="utf-8") as f:
            head = [l for l in f.read().splitlines() if l.startswith("- Population") or
                    l.startswith("- Trigger") or l.startswith("- Acceptance")]
        lines += head[:3]
    except OSError:
        lines.append("contract file missing!")
    lines.append("rule: no interim statistical peeks (bookkeeping only)")
    return "\n".join(lines)


# ---------------- command handlers (registered only if configured) ----------
HELP_TEXT = ("commands (read-only):\n"
             "/status - research/safety state\n"
             "/health - frozen-data + repo health\n"
             "/events - forward monitoring contract\n"
             "/help - this text")


def cmd_start(message):
    if not is_allowed(message.chat.id):
        return "[denied]"
    return HELP_TEXT


def cmd_help(message):
    if not is_allowed(message.chat.id):
        return "[denied]"
    return HELP_TEXT


def cmd_status(message):
    if not is_allowed(message.chat.id):
        return "[denied]"
    return build_status_text()


def cmd_health(message):
    if not is_allowed(message.chat.id):
        return "[denied]"
    return build_health_text()


def cmd_events(message):
    if not is_allowed(message.chat.id):
        return "[denied]"
    return build_events_text()


COMMANDS = {"/start": cmd_start, "/help": cmd_help, "/status": cmd_status,
            "/health": cmd_health, "/events": cmd_events}


def register_handlers(tb):
    """Register read-only handlers on a configured telebot instance."""
    if tb is None:
        return False

    @tb.message_handler(func=lambda msg: msg.text in COMMANDS)
    def dispatch(message):
        if not is_allowed(message.chat.id):
            tb.send_message(message.chat.id, "[denied] chat not in allowlist")
            return
        tb.send_message(message.chat.id, COMMANDS[message.text](message))

    @tb.message_handler(func=lambda msg: True)
    def fallback(message):
        if not is_allowed(message.chat.id):
            return  # silent for unknown senders
        tb.send_message(message.chat.id, "unknown command. " + HELP_TEXT)
    return True


def run_polling():
    """Blocking polling loop. Requires MONITOR_AVAILABLE and a token."""
    if not (MONITOR_AVAILABLE and TOKEN):
        print("[MONITOR] disabled: telebot missing or TELEGRAM_BOT_TOKEN unset")
        return
    tb = telebot.TeleBot(TOKEN)
    register_handlers(tb)
    print("[MONITOR] polling started (read-only commands; allowlist=%d chats)"
          % len(ALLOWED_CHATS))
    tb.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    run_polling()
