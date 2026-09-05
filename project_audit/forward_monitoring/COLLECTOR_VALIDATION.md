# COLLECTOR VALIDATION — FORWARD MONITORING (FD-CP5.9)

Generated: 2026-09-05 | Collector: `forward_monitoring/forward_collector.py`
Contract: FORWARD_MONITORING_CONTRACT.md (5babd92) v1.0 | Dataset: FD-CP5.9
Event rule: FROZEN `strategy_a2_v2_firstbreakout.py` (10abbc99…) — reused
verbatim (§49: no duplicate pipeline).

```text
Collector:                  forward_collector.py (preview/collect modes)
Contract:                   v1.0 (>=300 qualified events OR 180 days; fade h5)
Code Version:               event_rule 10abbc99… + collector (this commit)
Dataset Version:            FD-CP5.9 (FORWARD_START_TIMESTAMP = NULL)

Lookahead:                  PASS (T1 prefix-stability: events never move/appear
                                  earlier under frame truncation)
Forming Candle:             PASS (T2 via fetch_new_bars: future-close bar
                                  dropped, counted as excluded)
First Breakout:             PASS (T3: sustained breakout run -> exactly ONE
                                  event at the first qualifying bar)
Duplicate:                  PASS (T4: deterministic IDs; re-detection yields
                                  identical set; collector skips known ids)
Timestamp:                  PASS (T5: canonical sort restores order; dups collapsed)
Timezone:                   PASS (T6: +3:30 wrapper; T11/T12 use TZ-corrected
                                  incremental fetch)
Horizon:                    PASS (T7: outcomes only when horizon bars exist —
                                  near-frame-end event stays PENDING)
Ledger:                     PASS (T8: append-only verified — no history rewrite)
Hash:                       PASS (T9: tamper changes sha256; batch hash recorded)
Determinism:                PASS (T10: identical runs -> identical IDs/timestamps)
MT5 Failure:                PASS (T11: None/empty -> NO EVENT, no fabrication)
Network Failure:            PASS (T12: exception path -> NO EVENT, logged)
Trading Isolation:          PASS (T13: zero order-API call sites in collector)
Artifact Isolation:         PASS (T14: writes confined to forward_monitoring/)
Empty Data:                 PASS (T15: empty frame -> zero events, no crash)
```

## Notes

- Test-harness defects found and fixed during validation (audit-script class,
  per error-recovery law): T2 inclusive-boundary expectation, T3 synthetic days
  lacked a real session break (the collector's eligibility rule correctly
  rejected them), T7 near-end scenario crossed midnight (day became
  OR-ineligible by design). Production collector needed ONE real fix found by
  these tests: `.to_pydatetime()` on plain datetime in the fetch path.
- Preview mode (§32) is the default until human start authorization;
  `collect` mode requires the COLLECT_START_AUTHORIZED marker file.

## HARD START GATE (§51)

```text
COLLECTOR VALIDATED

FORWARD_START_TIMESTAMP: NOT SET
OFFICIAL EVENTS:         0
STATUS:                  READY FOR HUMAN START AUTHORIZATION
```
