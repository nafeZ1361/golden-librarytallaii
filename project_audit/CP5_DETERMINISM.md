# CP5.4 DETERMINISM AUDIT
Generated: 2026-09-05T14:39:21 | disk-only; inputs = the six frozen CSVs (dataset identity
  be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3); sources = cp5-source-freeze-v1 versions. No performance metric is computed.

## Methodology
- Execution A and Execution B each INDEPENDENTLY reload the frozen CSV and call the same frozen signal_fn; normalization (time-string -> datetime64) is verified not to alter any numeric value (raw-vs-parsed assertion).
- Compared: row counts, input mutation (deep-copy snapshot vs assert_frame_equal), state validity, elementwise-identical serialized output, SHA-256 of the full state list.
- Third-order isolation: window 1 executed FIRST (phase 1), windows 2..6 next (phase 2), then window 1 AGAIN (phase 3): phase1 hash must equal phase3 hash -> no hidden global state / cross-window contamination / previous-execution dependency.
- Runtime proof: MetaTrader5 must be absent from sys.modules after all strategy executions; filesystem snapshot of ROOT/project_audit/cache must be byte- and mtime-identical before/after.

## Static source scan (pattern hits; empty list = clean)
- A1: CLEAN
- A2: CLEAN
- research_harness: [[28, "\\bmt5\\.", "raw = mt5.copy_rates_from_pos(\"XAUUSD.\", mt5.TIMEFRAME_M3, 1, total)"], [44, "\\bmt5\\.", "tf_const = {\"15m\": mt5.TIMEFRAME_M15, \"1h\": mt5.TIMEFRAME_H1}[tf]"], [47, "\\bmt5\\.", "rates = mt5.copy_rates_range(\"XAUUSD.\", tf_const,"], [66, "\\bmt5\\.", "raw = mt5.copy_rates_from_pos(\"XAUUSD.\", mt5.TIMEFRAME_M3, 1, 14400 * n_windows)"], [202, "\\bmt5\\.", "pip = (10 ** -mt5.symbol_info(symbol).digits) * 10"], [203, "\\bmt5\\.", "info = mt5.symbol_info(symbol)"]]
- note: library-internal behavior (pandas/pandas_ta) is not scanned; the empirical A==B + isolation tests are the runtime proof of determinism.
- research_harness hits are in its MT5 loader functions (load_windows/window_bounds_from_m3/verify_engine_equivalence), which CP5.4 never calls — this stage reads only the frozen CSVs; the sys.modules proof below confirms no MT5 import at runtime.

## Determinism results (A vs B, per window)

### A1
| phase | window | rows_out | buy | sell | hold | events | A hash | B hash | A==B | mutated |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 14400 | 103 | 123 | 14174 | 226 | fb6872111ec2bd4a | fb6872111ec2bd4a | True | False/False |
| 2 | 2 | 14400 | 113 | 111 | 14176 | 224 | e3b809431e7f3c82 | e3b809431e7f3c82 | True | False/False |
| 2 | 3 | 14400 | 125 | 110 | 14165 | 235 | 7184c542edc340f0 | 7184c542edc340f0 | True | False/False |
| 2 | 4 | 14400 | 118 | 100 | 14182 | 218 | 435231064993eb11 | 435231064993eb11 | True | False/False |
| 2 | 5 | 14400 | 122 | 105 | 14173 | 227 | 57379f67f5b18dc7 | 57379f67f5b18dc7 | True | False/False |
| 2 | 6 | 14400 | 123 | 123 | 14154 | 246 | 62594e22a1739b0c | 62594e22a1739b0c | True | False/False |
| 3 | 1 | 14400 | 103 | 123 | 14174 | 226 | fb6872111ec2bd4a | fb6872111ec2bd4a | True | False/False |
- all windows A==B: True | isolation (phase1 w1 hash == phase3 w1 hash): True
- w1 hash first-seen : fb6872111ec2bd4acee3002fd50f71c5f136fbc3860f29a311c16e6a9dd3a743
- w1 hash re-executed: fb6872111ec2bd4acee3002fd50f71c5f136fbc3860f29a311c16e6a9dd3a743

### A2
| phase | window | rows_out | buy | sell | hold | events | A hash | B hash | A==B | mutated |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 14400 | 3923 | 1483 | 8994 | 5406 | e5e71187b05adb79 | e5e71187b05adb79 | True | False/False |
| 2 | 2 | 14400 | 1407 | 1283 | 11710 | 2690 | f9e86b21223c116d | f9e86b21223c116d | True | False/False |
| 2 | 3 | 14400 | 247 | 156 | 13997 | 403 | d9cfc78f7b8bedc4 | d9cfc78f7b8bedc4 | True | False/False |
| 2 | 4 | 14400 | 75 | 257 | 14068 | 332 | 5aa52f818c1240f0 | 5aa52f818c1240f0 | True | False/False |
| 2 | 5 | 14400 | 129 | 204 | 14067 | 333 | 1b60befaf901d4da | 1b60befaf901d4da | True | False/False |
| 2 | 6 | 14400 | 289 | 234 | 13877 | 523 | 8fbc4346725b79b2 | 8fbc4346725b79b2 | True | False/False |
| 3 | 1 | 14400 | 3923 | 1483 | 8994 | 5406 | e5e71187b05adb79 | e5e71187b05adb79 | True | False/False |
- all windows A==B: True | isolation (phase1 w1 hash == phase3 w1 hash): True
- w1 hash first-seen : e5e71187b05adb79a6781c1403f854e5e84e72beb3ea794e29956870199c43a2
- w1 hash re-executed: e5e71187b05adb79a6781c1403f854e5e84e72beb3ea794e29956870199c43a2

## Runtime environment proofs
- MetaTrader5 imported during ANY strategy execution: NO (absent from sys.modules after all executions)
- filesystem snapshot identical before/after all executions: YES
- input mutation: none detected in any execution (see table)
- cross-window state contamination: none detected (isolation test)
- previous-execution dependency: none detected (isolation test)

## Anomalies
- none

## Final verdict
- **PASS**
- If PASS: signal generation from the frozen dataset is deterministic and reproducible; the dataset is safe to proceed toward CP5.5 (performance evaluation) ONLY upon explicit user authorization.
- No performance metric was produced (by design).
