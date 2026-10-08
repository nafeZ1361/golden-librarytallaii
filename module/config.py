"""Central runtime configuration for the trading system."""

from __future__ import annotations

import os


# Keep this stable for the lifetime of a deployed bot instance.
MAGIC_NUMBER = int(os.getenv("MT5_MAGIC_NUMBER", "26080901"))
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()

# ---------------------------------------------------------------- risk ---
# Single source of truth for runtime risk limits (forensic finding F-004):
# the RISK_* environment variables listed below, materialized exclusively
# through RiskLimits.from_env() in module/risk.py. No component may hardcode
# RiskLimits defaults; construct risk validators with RiskLimits.from_env()
# so this contract stays authoritative.
#
#   RISK_MAX_VOLUME           trade volume cap          (default 1.0)
#   MAX_VOLUME_TARGET         optional stricter cap     (default 0 = off)
#   RISK_MAX_DAILY_LOSS       daily loss cap            (default 0.0 = off)
#   RISK_MAX_SPREAD           spread cap                (default 0.0 = off)
#   RISK_MAX_OPEN_POSITIONS   open-position cap         (default 0 = off)
#   RISK_MAX_DRAWDOWN_PCT     drawdown cap, percent     (default 20.0)
