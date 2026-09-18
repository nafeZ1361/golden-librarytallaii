#!/usr/bin/env python3
"""Manual, approval-gated staged volume controller.

Usage:
  volume_step.py status
  volume_step.py size --balance 1000 --entry 2000 --sl 1990 --tick-size 0.01 --tick-value 1 --trades 20 --profit 30
  volume_step.py approve --volume 0.02 --risk-percent 1 --reason '3-day stable PAPER' --approved-by operator
  volume_step.py rollback --volume 0.01 --reason 'drawdown increased' --approved-by operator
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from module.volume_control import VolumeController, calculate_risk_volume, risk_corrected_percent


def controller() -> VolumeController:
    return VolumeController(
        os.getenv("VOLUME_STATE_PATH", "volume_state.json"),
        os.getenv("VOLUME_CHANGE_LOG", "logs/volume_changes.log"),
        float(os.getenv("MAX_VOLUME_TARGET", "0.01")),
        int(os.getenv("MIN_OBSERVATION_DAYS", "3")),
    )


def cmd_status(args):
    c = controller()
    print(json.dumps(c.state, ensure_ascii=False, indent=2))
    print(f"MAX_VOLUME_TARGET={c.max_target} MIN_OBSERVATION_DAYS={c.min_observation_days}")


def cmd_size(args):
    corrected = risk_corrected_percent(args.base_risk, args.balance, args.rr, args.trades, args.profit, args.max_risk)
    volume = calculate_risk_volume(args.balance, corrected, args.entry, args.sl, args.tick_size, args.tick_value, args.volume_step, args.min_volume, args.broker_max, float(os.getenv("MAX_VOLUME_TARGET", "0.01")))
    print(json.dumps({"risk_percent": corrected, "calculated_volume": volume, "max_volume_target": float(os.getenv("MAX_VOLUME_TARGET", "0.01"))}, indent=2))


def cmd_approve(args):
    c = controller()
    started = c.state.get("observation_started", "")
    if started:
        days = (date.today() - date.fromisoformat(started)).days
        if days < c.min_observation_days:
            raise SystemExit(f"NO-GO: only {days} observation day(s); require {c.min_observation_days}")
    change = c.record_change(args.volume, args.risk_percent, args.reason, args.approved_by)
    print(json.dumps(change.__dict__, ensure_ascii=False, indent=2))


def cmd_rollback(args):
    change = controller().rollback(args.volume, args.reason, args.approved_by)
    print(json.dumps(change.__dict__, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    size = sub.add_parser("size")
    for name, typ in [("balance", float), ("entry", float), ("sl", float), ("tick-size", float), ("tick-value", float), ("trades", int), ("profit", float)]: size.add_argument("--" + name, required=True, type=typ)
    size.add_argument("--base-risk", type=float, default=1.0); size.add_argument("--rr", type=float, default=2.0); size.add_argument("--max-risk", type=float, default=2.0); size.add_argument("--volume-step", type=float, default=0.01); size.add_argument("--min-volume", type=float, default=0.01); size.add_argument("--broker-max", type=float, default=100.0); size.set_defaults(func=cmd_size)
    approve = sub.add_parser("approve")
    approve.add_argument("--volume", required=True, type=float); approve.add_argument("--risk-percent", required=True, type=float); approve.add_argument("--reason", required=True); approve.add_argument("--approved-by", required=True); approve.set_defaults(func=cmd_approve)
    rollback = sub.add_parser("rollback")
    rollback.add_argument("--volume", required=True, type=float); rollback.add_argument("--reason", required=True); rollback.add_argument("--approved-by", required=True); rollback.set_defaults(func=cmd_rollback)
    args = parser.parse_args(); args.func(args)


if __name__ == "__main__": main()
