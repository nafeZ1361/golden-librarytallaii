#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE_DIR="${ARCHIVE_DIR:-$ROOT/archive/paper_$STAMP}"
LOG_DIR="${LOG_DIR:-$ROOT/logs/paper_run_$(date -u +%Y%m%d)}"
mkdir -p "$ARCHIVE_DIR" "$LOG_DIR"

for state in paper_state.json trade_state.json; do
  if [[ -e "$state" ]]; then
    mv "$state" "$ARCHIVE_DIR/"
  fi
done

export TRADING_MODE=PAPER
export ENABLE_LIVE_TRADING=NO
export LOG_DIR
export PAPER_STATE_PATH="$ROOT/paper_state.json"
export TRADE_STATE_PATH="$ROOT/trade_state.json"
export MEMORY_PATH="${MEMORY_PATH:-$ROOT/memory/events.jsonl}"
export RISK_MAX_VOLUME="${RISK_MAX_VOLUME:-0.01}"
export RISK_MAX_DAILY_LOSS="${RISK_MAX_DAILY_LOSS:-50}"
export RISK_MAX_OPEN_POSITIONS="${RISK_MAX_OPEN_POSITIONS:-1}"
export LOOP_INTERVAL_SECONDS="${LOOP_INTERVAL_SECONDS:-5}"

mkdir -p "$(dirname "$MEMORY_PATH")"
export PAPER_RUN_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 scripts/notify_paper_start.py

PIDFILE="${PIDFILE:-$ROOT/paper_main.pid}"
if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "PAPER already running with PID $(cat "$PIDFILE")" >&2
  exit 1
fi
nohup python3 main.py >> "$LOG_DIR/main.stdout.log" 2>&1 &
echo $! > "$PIDFILE"
echo "PAPER started: pid=$(cat "$PIDFILE") log_dir=$LOG_DIR archive=$ARCHIVE_DIR"
