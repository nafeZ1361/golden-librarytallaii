# Canonical Market Data Flow

Live and backtest candle consumers use the same path: MT5 M1 bars are fetched with `TIMEFRAME_M1`, then aggregated by `module.timeframe_data.resample_m1_ohlcv` using the same timestamp alignment and OHLCV rules. Higher native MT5 timeframe requests are not used by the canonical loaders.

`module.mt5.candle`, `module.mt5.heikin_ashi`, and `backtest.hashem_backtest.backtest_candle` all call `fetch_m1_resampled`. This contract prevents live/backtest divergence caused by mixing broker-native higher-timeframe bars with locally resampled bars.

The project does not implement an economic-calendar/news provider. Any legacy notebook flag is explicitly disabled and must not be interpreted as an active news filter.

`module/experiments/grid_hedge.py` is an isolated, pure planning module. It is not imported by `main.py` or the production notebook path.
