"""Stage 7 configuration and command-line entry point.

Usage:
    python3 -u -m stage7.config <evidence_dir> <run_id>

Example:
    python3 -u -m stage7.config stage7/evidence/run1 run1

Writes all evidence artifacts into <evidence_dir> and prints a JSON summary to
stdout. Deterministic: identical inputs produce byte-identical evidence files.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

STAGE7_VERSION = "stage7-v1"

# ---------------------------------------------------------------- dataset ---
DATASET_PATH = Path("stage7_data/raw/XAUUSD_m1_ftmo.csv")
DATASET_SHA256 = "a7d856d8eacde8c2828abadd61d1fe7f977cbbf2c00269921a5798c18e886414"
DATASET_ROWS = 480_087
DATASET_FIRST_TIMESTAMP = "2025-01-02 01:05:00"
DATASET_LAST_TIMESTAMP = "2026-05-15 23:49:00"
SYMBOL = "XAUUSD"
TIMEFRAME = "M1"
TIMEZONE = "UTC (broker-naive; no conversion applied)"
DELIMITER = ","
ENCODING = "utf-8"
PROVIDER = "MT5 terminal export, FTMO-Server4 (GitHub user Gianniskas)"
SOURCE_URL = ("https://raw.githubusercontent.com/Gianniskas/"
              "mt5-m1-bars-us500-eurusd-xauusd/main/XAUUSD_m1.csv")
ACQUISITION_DATE_UTC = "2026-09-29T19:22:00Z"
ORIGINAL_FILENAME = "XAUUSD_m1.csv"
LOCAL_FILENAME = "XAUUSD_m1_ftmo.csv"
FILE_SIZE_BYTES = 27_646_937

# --------------------------------------------------------------- contract ---
HORIZON = 5
TARGET_NAME = "label_5"
PURGE = 5
EMBARGO = 60
DECISION_LAG = 1
TRAIN_RATIO = 0.70
HOLDOUT_RATIO = 0.30
FEATURE_COUNT = 26
RANDOM_SEED = 42
MODEL_NAME = "logistic_regression"
CHUNK_ROWS = 20_000

# ------------------------------------------------------------ backtest ------
INITIAL_EQUITY = 100_000.00
POSITION_FRACTION = 0.10          # fraction of current equity risked per trade
LOT_USD_PER_PRICE_UNIT = 1.0      # 1 unit exposure per USD price move (research sizing)
SPREAD_COST_USD = 0.30            # round-trip cost modelled on every trade (XAUUSD typical)


@dataclass(frozen=True)
class Stage7Config:
    version: str = STAGE7_VERSION
    dataset_path: str = str(DATASET_PATH)
    dataset_sha256: str = DATASET_SHA256
    expected_rows: int = DATASET_ROWS
    symbol: str = SYMBOL
    timeframe: str = TIMEFRAME
    horizon: int = HORIZON
    target_name: str = TARGET_NAME
    purge: int = PURGE
    embargo: int = EMBARGO
    decision_lag: int = DECISION_LAG
    train_ratio: float = TRAIN_RATIO
    holdout_ratio: float = HOLDOUT_RATIO
    feature_count: int = FEATURE_COUNT
    random_seed: int = RANDOM_SEED
    model_name: str = MODEL_NAME
    chunk_rows: int = CHUNK_ROWS
    initial_equity: float = INITIAL_EQUITY
    position_fraction: float = POSITION_FRACTION
    lot_usd_per_price_unit: float = LOT_USD_PER_PRICE_UNIT
    spread_cost_usd: float = SPREAD_COST_USD

    def to_dict(self) -> dict:
        return asdict(self)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print(json.dumps({"status": "error",
                          "message": "usage: python3 -u -m stage7.config <evidence_dir> <run_id>"}))
        return 2
    evidence_dir = Path(args[0])
    run_id = args[1]
    if not run_id or any(sep in run_id for sep in ("/", "\\")):
        print(json.dumps({"status": "error", "message": "run_id must be a plain name"}))
        return 2

    from stage7.pipeline import run_pipeline

    summary = run_pipeline(Stage7Config(), evidence_dir, run_id)
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0 if summary.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
