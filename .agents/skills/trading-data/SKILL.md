---
name: trading-data
description: Validate XAUUSD historical datasets, provenance, chronology, schema, hashes, and data-source boundaries.
---

# Trading Data

- Treat raw historical data as immutable input.
- Record symbol, timeframe, timezone convention, source, start/end, row count, and SHA256 where available.
- Validate required columns and numeric values.
- Check duplicates, nulls, chronology, and OHLC consistency.
- Do not silently repair invalid market data.
- MT5 can provide historical data acquisition only; ML/replay should consume files or canonical DataFrames.
- Never commit secrets, credentials, or terminal configuration.
