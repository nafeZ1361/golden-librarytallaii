# CP5.3 DATA INTEGRITY AUDIT
Generated: 2026-09-05T14:35:52 | mode: disk-only, independent validator, no MT5, no data modification

## Methodology
- Independent validator (this script): dual parsing (pandas AND stdlib csv) with bit-exact numeric comparison and timestamp round-trip checks; OHLC battery re-implemented by column NAME; gap forensics classifies EVERY non-3-minute interval (not blanket 'market closed'); cross-window boundary analysis; immutability by SHA-256; whole battery executed twice with identical results-hash requirement. The freeze validator's conclusions were NOT relied upon.

## Six-window table
| W | rows | span | incr | dups | grid | OHLC | NaN | parse fidelity | flags |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 14400 | 2025-12-10 21:39:00 .. 2026-01-27 12:00:00 | True | 0 | True | True | 0 | True | 3 |
| 2 | 14400 | 2026-01-27 12:03:00 .. 2026-03-11 21:06:00 | True | 0 | True | True | 0 | True | 0 |
| 3 | 14400 | 2026-03-11 21:09:00 .. 2026-04-27 07:12:00 | True | 0 | True | True | 0 | True | 2 |
| 4 | 14400 | 2026-04-27 07:15:00 .. 2026-06-09 17:24:00 | True | 0 | True | True | 0 | True | 1 |
| 5 | 14400 | 2026-06-09 17:27:00 .. 2026-07-23 09:54:00 | True | 0 | True | True | 0 | True | 0 |
| 6 | 14400 | 2026-07-23 09:57:00 .. 2026-09-04 17:30:00 | True | 0 | True | True | 0 | True | 0 |

## Column order (documented)
`time, open, high, low, close, tick_volume, spread, real_volume, volume`

## Gap forensics
- total non-3-minute intervals across 6 windows: 193
- classification counts: {"weekend_closure": 38, "single_missing_bar": 1, "daily_session_break": 149, "holiday_extended_closure": 2, "intraday_gap": 3}
- flagged gaps (non-'ok' classification): 6
  - [single_missing_bar] 2025-12-12 17:24:00 -> 2025-12-12 17:30:00 (6 min): one 3-minute bar absent inside a trading day; flagged
  - [holiday_extended_closure] 2025-12-24 20:42:00 -> 2025-12-26 01:00:00 (1698 min): day-boundary gap > 4h but < 36h; consistent with an extended holiday session; flagged for the record
  - [holiday_extended_closure] 2025-12-31 23:57:00 -> 2026-01-02 01:00:00 (1503 min): day-boundary gap > 4h but < 36h; consistent with an extended holiday session; flagged for the record
  - [intraday_gap] 2026-03-25 16:06:00 -> 2026-03-25 16:21:00 (15 min): non-3-minute interval INSIDE a trading day; unexplained by session structure; flagged — affects that day's OR span continuity and indicator continuity
  - [intraday_gap] 2026-04-23 21:33:00 -> 2026-04-23 21:48:00 (15 min): non-3-minute interval INSIDE a trading day; unexplained by session structure; flagged — affects that day's OR span continuity and indicator continuity
  - [intraday_gap] 2026-05-04 18:30:00 -> 2026-05-04 18:39:00 (9 min): non-3-minute interval INSIDE a trading day; unexplained by session structure; flagged — affects that day's OR span continuity and indicator continuity
- days with interrupted intraday continuity (gap days): ['2025-12-12', '2026-03-25', '2026-04-23', '2026-05-04']
- OR-position check: none of the flagged gap timestamps falls inside the empirical OR window (first ~4h of the broker day: 00:00-04:00), so OR construction is unaffected in practice; additionally A2's registered gap-free-span rule (Amendment 1) structurally rejects any day whose OR window contains a missing bar.
- note: indicator state (RSI RMA / BB rolling) is computed on the frozen series AS-IS; gaps are part of the registered data; no filling is permitted.

## Volume / market fields (window-level aggregate)
- tick_volume: zeros=0 negative=0 nan=0 min=3.0 max=6799.0
- volume: zeros=0 negative=0 nan=0 min=3.0 max=6799.0
- real_volume: zeros=86400 negative=0 nan=0 min=0.0 max=0.0
- spread: zeros=0 negative=0 nan=0 min=3.0 max=90.0
- real_volume=0 everywhere is the expected CFD condition (no exchange volume); A1 uses only `close`; A2 uses time/high/low/close/volume(=tick_volume); spread/real_volume are unused by both strategies. No rejection criterion applies.

## Cross-window integrity
- global strictly increasing: True
- overlapping timestamps: none
- duplicated market periods: 0
- boundary gaps (minutes, w1->w2 ... w5->w6): [3, 3, 3, 3, 3]
- boundary continuity (each == 3 min): True

## Last-closed-candle rule (G)
- {"start_pos_registered": 1, "retrieved_at_local": "2026-09-04T23:32:56", "acquisition_probe_recorded": "position1(open)=17:30:00 == frozen last bar; position0(open)=17:33:00 was the forming bar (CP5_DATA_FREEZE.md v1/v2 probe section)", "forming_candle_excluded": true, "last_frozen_candle_closed": true, "note": "verified against recorded acquisition evidence; no MT5 contact"}

## Immutability (H)
- cp5_window_1_df.csv : 19d478230a5067e771e28f45030be82fd337c3b5e3f4fc4092fd134ff579f1a7
- cp5_window_2_df.csv : 62b0a0b235ba14419f5a1430f41fd2cfadbf75b5ff3d0bb4d6ff005c3a4201c0
- cp5_window_3_df.csv : a2751e384366a5aac666808d1fcb01052400fbd36bae9951f5af248dd7269ee4
- cp5_window_4_df.csv : 3b51580294b4246da830369c878b921a8e64dc7e65b6de17e468d2baeb4a33e2
- cp5_window_5_df.csv : a53458353261370836267843088852fe9557ef41cc2757f94f25c4680d965d53
- cp5_window_6_df.csv : 888f2bfe20e61fbad44cbfcb8cbb151141c125a9f67a8453a74ba0bdbcc750f2
- manifest match: True | dataset identity recomputed == manifest: True
- DATASET IDENTITY: be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3
- NOTE: the CP5.3/CP5.4 master command quoted a malformed identity string (duplicated segment); per the command's own instruction, the manifest value above is used as the single source of truth.

## Reproducibility (I)
- battery executed twice: results-hash run1=ce86180fbd60a8bc run2=ce86180fbd60a8bc -> IDENTICAL
- AUDIT RESULTS HASH: ce86180fbd60a8bc00b73995da8ad1f8582493e2cc3606199811e8969688b83e

## Anomalies
- holiday_extended_closure; intraday_gap; single_missing_bar

## Final verdict
- **PASS WITH CONDITIONS**
- Dataset safe to enter CP5.4: YES
- No performance metric was produced (by design).
