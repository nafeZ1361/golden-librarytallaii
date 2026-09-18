"""Read-only Flask dashboard for the trading bot.

The dashboard never sends orders. It reads persisted state, logs, and an
optional injected MT5 adapter. Protect it with DASHBOARD_TOKEN when exposed
beyond localhost.
"""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, render_template_string

from module.config import MAGIC_NUMBER, TRADING_MODE
from module.paper import PaperBroker
from module.performance import calculate_performance


HTML = """<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'><title>Golden Library Monitor</title>
<style>body{font-family:system-ui;background:#101827;color:#e5e7eb;margin:24px}h1{color:#fbbf24}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.card{background:#1f2937;border-radius:12px;padding:16px;box-shadow:0 2px 8px #0004}pre{white-space:pre-wrap;max-height:420px;overflow:auto;color:#cbd5e1}.ok{color:#34d399}.warn{color:#fbbf24}</style></head>
<body><h1>Golden Library — داشبورد ربات</h1><div class='grid'><div class='card'><h3>وضعیت</h3><div id='status'>در حال بارگذاری...</div></div><div class='card'><h3>پوزیشن‌ها</h3><pre id='positions'></pre></div><div class='card'><h3>آخرین لاگ‌ها</h3><pre id='logs'></pre></div><div class='card'><h3>مغز دوم / Memory</h3><pre id='memory'></pre></div></div>
<script>async function load(){for(const [id,url] of [['status','/api/status'],['positions','/api/positions'],['logs','/api/logs?limit=30'],['memory','/api/memory?limit=30']]){try{let r=await fetch(url);let x=await r.json();document.getElementById(id).textContent=JSON.stringify(x,null,2)}catch(e){document.getElementById(id).textContent='خطا: '+e}}}load();setInterval(load,5000)</script></body></html>"""


def create_app(mt5_api: Any = None, root: str | os.PathLike[str] | None = None) -> Flask:
    root_path = Path(root or Path(__file__).resolve().parent)
    app = Flask(__name__)
    state_path = root_path / "trade_state.json"
    log_path = root_path / os.getenv("LOG_DIR", "logs") / "trading.jsonl"
    memory_path = root_path / "memory" / "events.jsonl"
    token = os.getenv("DASHBOARD_TOKEN")
    dashboard_host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if dashboard_host not in local_hosts and not token:
        raise RuntimeError("DASHBOARD_TOKEN is required when dashboard is not bound to localhost")
    if mt5_api is None and TRADING_MODE == "PAPER":
        mt5_api = PaperBroker(root_path / "paper_state.json", magic_number=MAGIC_NUMBER)

    @app.before_request
    def protect_dashboard():
        if token and request.headers.get("X-Dashboard-Token") != token:
            return jsonify({"error": "unauthorized"}), 401

    def read_json(path: Path, limit: int = 100) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line in deque(path.read_text(encoding="utf-8").splitlines(), maxlen=limit):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    @app.get("/")
    def index():
        return render_template_string(HTML)

    @app.get("/api/status")
    def status():
        state = {}
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                state = {"error": "invalid state file"}
        counts: dict[str, int] = {}
        for record in state.values() if isinstance(state, dict) else []:
            value = record.get("state", "UNKNOWN")
            counts[value] = counts.get(value, 0) + 1
        payload = {"mode": TRADING_MODE, "magic_number": MAGIC_NUMBER, "state_counts": counts, "updated_at": datetime.now(timezone.utc).isoformat()}
        if TRADING_MODE == "PAPER" and isinstance(mt5_api, PaperBroker):
            payload["paper"] = {"ledger": mt5_api.reconcile(), "drawdown": mt5_api.max_drawdown()}
        return jsonify(payload)

    @app.get("/api/positions")
    def positions():
        if mt5_api is None:
            return jsonify({"connected": False, "source": "none", "positions": []})
        try:
            raw = mt5_api.positions_get() or ()
            items = []
            for p in raw:
                if getattr(p, "magic", MAGIC_NUMBER) != MAGIC_NUMBER:
                    continue
                items.append({"ticket": getattr(p, "ticket", 0), "trade_id": getattr(p, "trade_id", ""), "symbol": getattr(p, "symbol", ""), "volume": getattr(p, "volume", 0), "type": getattr(p, "type", getattr(p, "order_type", 0)), "price": getattr(p, "price", 0), "current_price": getattr(p, "current_price", 0), "sl": getattr(p, "sl", 0), "tp": getattr(p, "tp", 0), "profit": getattr(p, "profit", 0), "comment": getattr(p, "comment", "")})
            return jsonify({"connected": True, "source": "paper" if TRADING_MODE == "PAPER" else "mt5", "positions": items})
        except Exception as exc:
            return jsonify({"connected": False, "error": str(exc), "positions": []}), 503

    @app.get("/api/logs")
    def logs():
        return jsonify(read_json(log_path, min(int(request.args.get("limit", 100)), 500)))

    @app.get("/api/memory")
    def memory():
        return jsonify(read_json(memory_path, min(int(request.args.get("limit", 100)), 500)))

    @app.get("/api/performance")
    def performance():
        if not isinstance(mt5_api, PaperBroker):
            return jsonify({"error": "performance endpoint currently exposes Paper results only"}), 400
        profits = [float(position.profit) for position in mt5_api.positions.values() if position.status == "CLOSED"]
        return jsonify(calculate_performance(profits, initial_balance=mt5_api.initial_balance))

    return app


if __name__ == "__main__":
    create_app().run(host=os.getenv("DASHBOARD_HOST", "127.0.0.1"), port=int(os.getenv("DASHBOARD_PORT", "5000")), debug=False)
