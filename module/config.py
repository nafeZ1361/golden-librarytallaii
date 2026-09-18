"""Central runtime configuration for the trading system."""

from __future__ import annotations

import os


# Keep this stable for the lifetime of a deployed bot instance.
MAGIC_NUMBER = int(os.getenv("MT5_MAGIC_NUMBER", "26080901"))
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()
