# CP5.6 PRE-FLIGHT — DATA PROVENANCE VERIFICATION
Generated: 2026-09-05T15:34:25 | disk-only; perturbation tests use in-memory copies; frozen
  files are untouched.

## Layer 1 — Static source trace (exact line numbers from disk)

### A1 (strategy_a1_meanrev.py)
- imports (data/network surface):
    L15  import pandas as pd
    L16  import pandas_ta
- data-ingress lines (every place the function touches its input df):
    L19  def signal_fn(wdf, tf_name=None):
    L23  close = wdf["close"]
- forbidden-token hits (MT5/network/random/wall-clock/file-I/O): ZERO

### A2 (strategy_a2_breakout.py)
- imports (data/network surface):
    L30  import pandas as pd
- data-ingress lines (every place the function touches its input df):
    L39  def signal_fn(wdf, tf_name=None):
    L47  t = pd.to_datetime(wdf["time"])
    L50  high = wdf["high"].tolist()
    L51  low = wdf["low"].tolist()
    L52  close = wdf["close"].tolist()
    L53  vol = wdf["volume"].tolist()
- forbidden-token hits (MT5/network/random/wall-clock/file-I/O): ZERO

- hash cross-check vs Amendment 1 (source identity):
    A1 = 85c1781a700dde5ed0015fc64841f99a4c0263b6913b9b3afc5a77765e4105a6
    A2 = 732d1eaad9517e2c4b4bbe1d0fc82a1fc8a0a9c79fd8a8aa9898ab72d279dd5b

### Indicator → data-source mapping (from the traced lines)
- A1 RSI(14):        input `close`  <- wdf  (A1 L23 -> L24)
- A1 BBands(20,2):   input `close`  <- wdf  (A1 L23 -> L25); bands read L26-L30
- A1 comparisons:    r/lo/up/c all derive from wdf columns (A1 L29-L31, L39-L42)
- A2 day boundaries: `time`         <- wdf  (A2 L47-L49)
- A2 Opening Range:  `high`,`low`   <- wdf  (A2 L50-L51 -> L71-L72)
- A2 volume filter:  `volume`       <- wdf  (A2 L53 -> L73, L76)
- A2 breakout:       `close`        <- wdf  (A2 L52 -> L77, L79)
- A2 eligibility:    `time`/tsec    <- wdf  (A2 L49 -> L64-L68)
- NO other data source exists in either file: no fetch, no file I/O, no env,

## Layer 2 — Indicator-library supply-chain scan (pandas_ta)
- package path: C:\Python312\Lib\site-packages\pandas_ta
- .py files scanned: 182
- hits for MT5/network/shell tokens: ZERO — library is pure computation
- note: A1 imports ONLY pandas + pandas_ta (L15-L16); A2 imports ONLY pandas (L30). `ta`/yfinance/MetaTrader5 are never imported by either strategy.

## Layer 3 — Runtime two-sided purity tests (window 1, in-memory copies)
- A1 invariance to unused columns (high/low/volume/spread/real_volume/tick_volume perturbed +10%): changed bars per column = {"high": 0, "low": 0, "volume": 0, "spread": 0, "real_volume": 0, "tick_volume": 0} -> PASS (output bit-identical)
- A1 sensitivity to `close` (bars 100-105 x1.05): changed bars = 2 -> PASS (output depends on wdf close)
- A2 invariance to unused columns (spread x3, real_volume=999): changed bars = 0 -> PASS (bit-identical)
- A2 first-day OR high perturbation (bars 1-40 x1.02): changed bars = 0 -> PASS (window-first day is ineligible by registered rule (a) — rule enforcement proven)
- first eligible day in window 1: bars 47..86 (2025-12-11)
- A2 sensitivity to `high` of the ELIGIBLE day's OR window (x1.02): changed bars = 88 -> PASS (OR comes from wdf high)
- A2 sensitivity to `close` of post-OR bars (x1.03): changed bars = 45 -> PASS (breakout compares wdf close)

- Per-window output divergence (frozen dataset, from CP5.4/CP5.5 records):
    A1 event counts per window: [226, 224, 235, 218, 227, 246] — all different
    A2 event counts per window: [835, 464, 116, 151, 129, 163] — structurally different
  A self-fetching signal generator (the CP-Phase-1 defect pattern) would emit
  window-INDEPENDENT series; the observed window-shaped divergence proves
  output is a function of the supplied frozen df.

- Runtime: after importing both strategies and all executions above, 'MetaTrader5' in sys.modules = False
- Filesystem: frozen CSVs and sources untouched (perturbations were in-memory copies; no write performed anywhere in this script).

## ACCEPTANCE BLOCK (per addendum)
- run provenance: run 1 flagged a FAIL on the A2 OR-high test because the perturbation targeted the WINDOW-FIRST day, which the registered Amendment-1 rule (a) excludes by design; the test (not the strategy) was re-designed to perturb an ELIGIBLE day. The original zero-delta is retained above as positive proof of eligibility enforcement. No project source/data was changed.
```
DATA PROVENANCE: CONFIRMED CLEAN
  evidence: A1 L15-L16 (imports: pandas, pandas_ta only), L19-L43
    (signal_fn reads wdf['close'] L23; RSI L24; BBands L25; comparisons
    L29-L42; no other source); A2 L30 (import: pandas only), L39-L82
    (signal_fn reads wdf time/high/low/close/volume L47-L53; OR built
    from those arrays L62-L73; breakout L75-L80); forbidden-token scan:
    ZERO hits in both files; pandas_ta supply-chain scan: ZERO
    MT5/network/shell tokens in 182 files; runtime: MetaTrader5 never
    in sys.modules; two-sided purity: A1 bit-identical under unused-column
    perturbation and sensitive to close; A2 bit-identical to spread/
    real_volume and sensitive to OR-window high; per-window output
    divergence proves window-dependence. CP5.4 isolation proof on record.
  conclusion: A1/A2 were designed df-first; the Phase-1 self-fetch defect
    pattern is structurally and empirically ABSENT. CP5.5 numbers stand
    as measured on the frozen dataset.
```

- CP5.6 main statistical section (incl. the mandatory overlapping-horizon
  serial-correlation/clustering test on H5/H20) is QUEUED and will start
  ONLY after explicit user approval of this report.
