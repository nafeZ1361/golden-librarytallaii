"""Conservative, approval-gated position sizing and staged volume changes."""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def risk_corrected_percent(base_risk: float, starting_balance: float, rr: float, total_trades: int, current_profit: float, max_risk: float) -> float:
    """Mirror the project's risk_corrector formula without requiring MT5."""
    if starting_balance <= 0 or rr <= 0:
        raise ValueError("starting_balance and rr must be positive")
    initial_risk = starting_balance * (base_risk / 100.0)
    target_profit = initial_risk * rr * max(1, total_trades)
    deficit = target_profit - current_profit
    if deficit <= 0:
        return min(base_risk, max_risk)
    adjusted = round((deficit / rr) / starting_balance * 100.0, 2)
    return min(max(adjusted, base_risk), max_risk)


def calculate_risk_volume(balance: float, risk_percent: float, entry: float, stop_loss: float, tick_size: float, tick_value: float, volume_step: float = 0.01, min_volume: float = 0.01, max_volume: float = 1.0, max_target: float = 0.01) -> float:
    """Size by money risk and hard-cap it at MAX_VOLUME_TARGET."""
    distance = abs(float(entry) - float(stop_loss))
    if balance <= 0 or risk_percent <= 0 or distance <= 0 or tick_size <= 0 or tick_value <= 0:
        return 0.0
    risk_money = balance * risk_percent / 100.0
    loss_per_lot = distance / tick_size * tick_value
    raw = risk_money / loss_per_lot
    cap = min(float(max_volume), float(max_target))
    if cap <= 0:
        return 0.0
    sized = min(raw, cap)
    sized = math.floor(sized / volume_step) * volume_step
    if sized < min_volume and raw >= min_volume and min_volume <= cap:
        sized = min_volume
    return round(min(sized, cap), 8)


@dataclass
class VolumeChange:
    timestamp: str
    old_volume: float
    new_volume: float
    risk_percent: float
    reason: str
    approved_by: str
    status: str = "APPROVED"


class VolumeController:
    """Persist volume history and require a manual approval per stage."""
    def __init__(self, state_path: str | Path = "volume_state.json", log_path: str | Path = "logs/volume_changes.log", max_target: float = 0.01, min_observation_days: int = 3):
        self.state_path = Path(state_path)
        self.log_path = Path(log_path)
        self.max_target = float(max_target)
        self.min_observation_days = int(min_observation_days)
        self.state = self._load()

    def _load(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"current_volume": 0.01, "observation_started": "", "changes": []}

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def record_change(self, new_volume: float, risk_percent: float, reason: str, approved_by: str) -> VolumeChange:
        old = float(self.state.get("current_volume", 0.01))
        new = min(float(new_volume), self.max_target)
        if new <= 0 or new < old:
            raise ValueError("new volume must be positive and not below current volume; use rollback() to decrease")
        if new > self.max_target:
            raise ValueError("new volume exceeds MAX_VOLUME_TARGET")
        change = VolumeChange(datetime.now(timezone.utc).isoformat(), old, new, float(risk_percent), reason, approved_by)
        self.state["current_volume"] = new
        self.state.setdefault("changes", []).append(asdict(change))
        self.state["observation_started"] = datetime.now(timezone.utc).date().isoformat()
        self._save()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(change), ensure_ascii=False) + "\n")
        return change

    def rollback(self, volume: float, reason: str, approved_by: str) -> VolumeChange:
        old = float(self.state.get("current_volume", 0.01))
        new = float(volume)
        if new <= 0 or new >= old:
            raise ValueError("rollback volume must be positive and lower than current volume")
        change = VolumeChange(datetime.now(timezone.utc).isoformat(), old, new, 0.0, reason, approved_by, "ROLLBACK")
        self.state["current_volume"] = new
        self.state.setdefault("changes", []).append(asdict(change))
        self._save()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(change), ensure_ascii=False) + "\n")
        return change
