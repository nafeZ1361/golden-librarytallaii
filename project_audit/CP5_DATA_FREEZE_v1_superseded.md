# CP5 DATA FREEZE REPORT
Generated (local wall clock): 2026-09-04T23:32:26
Registered spec: CP5_PRE_REGISTRATION.md §B/§D3 — XAUUSD., 3m, 6 windows x 14400 bars, start_pos=1.
Scope: acquisition + integrity + freeze ONLY. No strategy execution, no performance metric.

## A. Acquisition
- branch: code-refactoring-guide-41a87
- HEAD: 9184e5b4f5f10aaaafd257fe8a05aaf61c6e5ab5
- baseline-lock-v1 -> dd526e588cdfbe5b961d02be5f1d71b265b8f8e3
- cp5-source-freeze-v1 -> 9184e5b4f5f10aaaafd257fe8a05aaf61c6e5ab5
- MT5 terminal version: 500.6140.21 Aug 2026 | initialize: OK
- symbol_info: digits=2 point=0.01 tick_size=0.01 tick_value=1.0 trade_mode=4
- retrieval timestamp (local wall clock): 2026-09-04T23:32:56
- timezone representation: NAIVE broker-server time (per CP1; never converted)
- acquisition method: research_harness.load_windows (frozen at cp5-source-freeze-v1)
- requested: 6 windows x 14400 bars = 86400 bars (single bulk fetch, start_pos=1)
- actual windows returned: 6
- completeness probe: pos0(open)=2026-09-04 17:30:00 pos1(open)=2026-09-04 17:33:00
- probe verdict: market appears CLOSED at retrieval; per registered start_pos=1 rule the newest complete bar is excluded by construction — documented, NOT repaired
- window 1: bars=14400/14400 span=2025-12-10 21:39:00 .. 2026-01-27 12:00:00 | increasing=True dups=0 gaps={"daily_break": 24, "weekend": 9} ohlc_valid=False nan/inf=0 grid_ok=True contiguous=None sha256=19d478230a5067e7...
- window 2: bars=14400/14400 span=2026-01-27 12:03:00 .. 2026-03-11 21:06:00 | increasing=True dups=0 gaps={"daily_break": 25, "weekend": 6} ohlc_valid=False nan/inf=0 grid_ok=True contiguous=True sha256=62b0a0b235ba1441...
- window 3: bars=14400/14400 span=2026-03-11 21:09:00 .. 2026-04-27 07:12:00 | increasing=True dups=0 gaps={"daily_break": 27, "weekend": 7} ohlc_valid=False nan/inf=0 grid_ok=True contiguous=True sha256=a2751e384366a5aa...
- window 4: bars=14400/14400 span=2026-04-27 07:15:00 .. 2026-06-09 17:24:00 | increasing=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc_valid=False nan/inf=0 grid_ok=True contiguous=True sha256=3b51580294b4246d...
- window 5: bars=14400/14400 span=2026-06-09 17:27:00 .. 2026-07-23 09:54:00 | increasing=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc_valid=False nan/inf=0 grid_ok=True contiguous=True sha256=a534583532613708...
- window 6: bars=14400/14400 span=2026-07-23 09:57:00 .. 2026-09-04 17:30:00 | increasing=True dups=0 gaps={"daily_break": 25, "weekend": 6} ohlc_valid=False nan/inf=0 grid_ok=True contiguous=True sha256=888f2bfe20e61fba...
- global: total_bars=86400 (expected 86400) strictly_increasing=True duplicate_timestamps=0 window_contiguity=checked-above

## B. Integrity checks
- bar counts: 6/6 exact (14,400)
- ordering: strictly increasing 6/6 | duplicates: 0 (global)
- gaps: classified per window (daily_break / weekend); unclassified gaps => anomaly
- OHLC validity: FAIL | NaN/Inf: total 0 | volume validity: 6/6 PASS
- final-candle completeness: start_pos=1 by construction (CP1 proof) + pos0/pos1 probe above

## C. Hashes
- cp5_window_1_df.csv : 19d478230a5067e771e28f45030be82fd337c3b5e3f4fc4092fd134ff579f1a7
- cp5_window_2_df.csv : 62b0a0b235ba14419f5a1430f41fd2cfadbf75b5ff3d0bb4d6ff005c3a4201c0
- cp5_window_3_df.csv : a2751e384366a5aac666808d1fcb01052400fbd36bae9951f5af248dd7269ee4
- cp5_window_4_df.csv : 3b51580294b4246da830369c878b921a8e64dc7e65b6de17e468d2baeb4a33e2
- cp5_window_5_df.csv : a53458353261370836267843088852fe9557ef41cc2757f94f25c4680d965d53
- cp5_window_6_df.csv : 888f2bfe20e61fbad44cbfcb8cbb151141c125a9f67a8453a74ba0bdbcc750f2
- DATASET IDENTITY (sha256 over the six file hashes, in order): be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3

## D. Dataset identity
- Any future CP5 step must read ONLY these six frozen files and cite this manifest + dataset_sha256_combined.
- Registration chain: pre-registration fcf71cb -> Amendment1/source-freeze 9184e5b (tag cp5-source-freeze-v1) -> this freeze.

## E. Anomalies
- market closed at retrieval: newest complete bar excluded by the registered start_pos=1 rule

## F. Final freeze verdict
- **FROZEN** — dataset frozen at project_audit/stability_windows_cache/cp5_window_{1..6}_df.csv
- This report contains NO performance metric by design.
- MT5 connection closed (read-only session).
