#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from module.performance import calculate_performance
from module.telegram_alerts import TelegramAlertNotifier


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def build_report(root: Path, date: str) -> str:
    states = load_json(root / os.getenv("TRADE_STATE_PATH", "trade_state.json"), {})
    counts = Counter(str(item.get("state", "UNKNOWN")) for item in states.values())
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_paths = list(log_dir.glob("**/*.jsonl"))
    alerts = []
    for path in log_paths:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            timestamp = str(row.get("timestamp", ""))
            if date not in timestamp:
                continue
            if str(row.get("level", "")).upper() in {"ERROR", "CRITICAL"} or row.get("event") in {"recovery_timeout", "recovery_error", "trade_rejected"}:
                alerts.append(row)
    paper = load_json(root / os.getenv("PAPER_STATE_PATH", "paper_state.json"), {})
    profits = [float(p.get("profit", 0.0)) for p in paper.get("positions", {}).values() if p.get("status") == "CLOSED"]
    metrics = calculate_performance(profits, initial_balance=float(os.getenv("INITIAL_BALANCE", "0")))
    rejected = counts.get("REJECTED", 0)
    threshold = int(os.getenv("DAILY_ALERT_THRESHOLD", "5"))
    prefix = "⚠️ WARNING: " if rejected + len(alerts) >= threshold else ""
    lines = [f"# {prefix}Daily PAPER Report — {date}", "", f"Generated at: {datetime.now(timezone.utc).isoformat()}", "", "## State counts", ""]
    lines.extend(f"- **{state}**: {count}" for state, count in sorted(counts.items()))
    lines.extend(["", "## Performance", "", f"- Net PnL: **{metrics['net_profit']:.4f}**", f"- Profit Factor: **{metrics['profit_factor']}**", f"- Sharpe: **{metrics['sharpe']:.4f}**", f"- Max Drawdown: **{metrics['max_drawdown']:.4f}**", f"- Closed trades: **{metrics['trades']}**", "", f"## Alerts ({len(alerts)})", ""])
    lines.extend(f"- `{row.get('timestamp', '')}` `{row.get('event', row.get('level', ''))}`: {row.get('message', '')}" for row in alerts[:100])
    return "\n".join(lines) + "\n"


def main():
    root = Path(__file__).resolve().parents[1]
    date = os.getenv("REPORT_DATE", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    report = build_report(root, date)
    path = root / "reports" / f"daily_{date.replace('-', '')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    print(path)
    notifier = TelegramAlertNotifier()
    if notifier.enabled:
        notifier.send(report)


if __name__ == "__main__":
    main()
