# CP5 DATA FREEZE REPORT (v2 — corrected validation)
Generated (local wall clock): 2026-09-04T23:38:40
Supersedes the v1 report of 2026-09-04T23:32 (preserved verbatim as `CP5_DATA_FREEZE_v1_superseded.md`). The frozen CSV files themselves are UNTOUCHED — they were acquired exactly once and their hashes are unchanged.

## VALIDATOR DEFECT LOG (full disclosure, per protocol)
- DEFECT-1 (v1 report, corrected here): the v1 OHLC check used a wrong column-index mapping (it tested low/close as if they were high/low), so it reported ohlc_valid=False on all six windows although the data is valid. Corrected battery: 0 violations on all rules, all windows.
- DEFECT-2 (v1 report, corrected here): the completeness probe mislabeled the ascending copy_rates_from_pos(0,2) rows. Facts: probe returned opens [17:30:00, 17:33:00]; the frozen last bar is 17:30:00. Therefore 17:33 was the FORMING bar at probe time and the market was OPEN — start_pos=1 excluded exactly the forming bar, as registered. The v1 label 'market appears CLOSED' was wrong; there is NO closure-related exclusion in the frozen set.
- Both defects were in the VALIDATOR only. No data file was modified, re-fetched, or repaired.

## A. Acquisition (from v1 manifest — unchanged)
- branch: code-refactoring-guide-41a87 | HEAD: 9184e5b4f5f10aaaafd257fe8a05aaf61c6e5ab5
- baseline-lock-v1 -> baseline-lock-v1
- cp5-source-freeze-v1 -> cp5-source-freeze-v1
- MT5 terminal version: 500.6140.21 Aug 2026 | retrieved_at_local: 2026-09-04T23:32:56
- symbol_info: digits=2 point=0.01 tick_size=0.01 tick_value=1.0
- spec: XAUUSD. 3m | 6 windows x 14400 bars | start_pos=1 | loader=research_harness.load_windows | candle_type=plain

## B. Integrity checks (CORRECTED battery, disk-only)
- cp5_window_1_df.csv: bars=14400 span=2025-12-10 21:39:00 .. 2026-01-27 12:00:00 | increasing=True dups=0 gaps={'daily_break': 24, 'weekend': 9} other=[] | OHLC_valid=True nan/inf=0 volume_ok=True grid=True contiguous=None | hash_match=True
- cp5_window_2_df.csv: bars=14400 span=2026-01-27 12:03:00 .. 2026-03-11 21:06:00 | increasing=True dups=0 gaps={'daily_break': 25, 'weekend': 6} other=[] | OHLC_valid=True nan/inf=0 volume_ok=True grid=True contiguous=True | hash_match=True
- cp5_window_3_df.csv: bars=14400 span=2026-03-11 21:09:00 .. 2026-04-27 07:12:00 | increasing=True dups=0 gaps={'daily_break': 27, 'weekend': 7} other=[] | OHLC_valid=True nan/inf=0 volume_ok=True grid=True contiguous=True | hash_match=True
- cp5_window_4_df.csv: bars=14400 span=2026-04-27 07:15:00 .. 2026-06-09 17:24:00 | increasing=True dups=0 gaps={'daily_break': 26, 'weekend': 6} other=[] | OHLC_valid=True nan/inf=0 volume_ok=True grid=True contiguous=True | hash_match=True
- cp5_window_5_df.csv: bars=14400 span=2026-06-09 17:27:00 .. 2026-07-23 09:54:00 | increasing=True dups=0 gaps={'daily_break': 26, 'weekend': 6} other=[] | OHLC_valid=True nan/inf=0 volume_ok=True grid=True contiguous=True | hash_match=True
- cp5_window_6_df.csv: bars=14400 span=2026-07-23 09:57:00 .. 2026-09-04 17:30:00 | increasing=True dups=0 gaps={'daily_break': 25, 'weekend': 6} other=[] | OHLC_valid=True nan/inf=0 volume_ok=True grid=True contiguous=True | hash_match=True

## C. Hashes (re-verified from disk against the manifest)
- cp5_window_1_df.csv : 19d478230a5067e771e28f45030be82fd337c3b5e3f4fc4092fd134ff579f1a7
- cp5_window_2_df.csv : 62b0a0b235ba14419f5a1430f41fd2cfadbf75b5ff3d0bb4d6ff005c3a4201c0
- cp5_window_3_df.csv : a2751e384366a5aac666808d1fcb01052400fbd36bae9951f5af248dd7269ee4
- cp5_window_4_df.csv : 3b51580294b4246da830369c878b921a8e64dc7e65b6de17e468d2baeb4a33e2
- cp5_window_5_df.csv : a53458353261370836267843088852fe9557ef41cc2757f94f25c4680d965d53
- cp5_window_6_df.csv : 888f2bfe20e61fbad44cbfcb8cbb151141c125a9f67a8453a74ba0bdbcc750f2
- DATASET IDENTITY (sha256 over the six file hashes, in order): be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3

## D. Dataset identity
- dataset_sha256_combined: be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3 (unchanged from acquisition)
- Any future CP5 step must read ONLY these six frozen files and cite this manifest + dataset identity.
- Registration chain: pre-registration fcf71cb -> Amendment1/source-freeze 9184e5b (tag cp5-source-freeze-v1) -> this freeze (acquired 2026-09-04T23:32, validated v2).

## E. Anomalies
- none — v1 anomalies resolved as validator defects (see defect log)

## F. Final freeze verdict
- **FROZEN** — frozen dataset: project_audit/stability_windows_cache/cp5_window_{1..6}_df.csv
- This report contains NO performance metric by design.
