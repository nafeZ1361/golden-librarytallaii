"""Small append-only operational memory for decisions and lessons learned."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SecondBrain:
    """Record operational facts; never changes strategy or places orders."""

    def __init__(self, path: str | Path = "memory/events.jsonl") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, kind: str, title: str, details: str = "", **metadata: Any) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "title": title,
            "details": details,
            "metadata": metadata,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
