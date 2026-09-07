# CP6 — INDEPENDENT OOS DATA FREEZE (v2 — timezone-corrected bounds)
Generated: 2026-09-05T17:03:01 | REGISTERED OOS DEFINITION (before any evaluation):
- PRIMARY OOS = 6 x 14,400 M3 bars immediately PRECEDING the frozen CP5 boundary (last OOS bar = 2025-12-10 21:36; frozen first = 2025-12-10 21:39).
  This period was never fetched/used in any audited phase (all prior phases used 'latest-N' windows starting 2025-12-09/10).
- SUPPLEMENT = forward fragment strictly after 2026-09-04 17:30 (underpowered, reported separately, never merged).
- One-shot evaluation with frozen parameters; no tuning; no optimization.

## v1 -> v2 defect record (error-handler loop)
- v1 bounds were passed broker-naive; the API interprets them Tehran-naive and converts to UTC (-3:30), so v1 data ended at broker 18:06 and the fragment overlapped the frozen period. CLASS: audit-script error (timezone).
- Diagnostic with +3:30 bounds proved broker history around the boundary is continuous (only the normal 63-min daily break) -> the hole was an artifact.
- v1 artifacts preserved as *_superseded; v2 = complete re-acquisition with corrected bounds (authorized: the v1 freeze failed its own registered definition; no scientific result existed on v1).
- Related historical note: CP4d's M15/H1 fetch used the same naive-bound API call (same -3:30 shift, span 3.5h earlier than intended). Impact: none on its verdict (all CIs wide and included 50%); recorded for provenance.

- MT5 (500, 6140, '21 Aug 2026') | symbol digits=2 point=0.01
- retrieved_at_local: 2026-09-05T17:03:01 | timezone: naive broker-server (never converted)
- primary OOS fetch: requested range 2023-12-10..2025-12-10 21:36; got 86400 rows; took LAST 86400
- forward fragment: 128 bars after 2026-09-04 17:30:00
- OOS window 1: bars=14400 span=2025-03-20 03:54..2025-05-05 14:24 inc=True dups=0 gaps={"daily_break": 26, "weekend": 7} ohlc=True nan=0 grid=True cont=None sha=b7baacd30fa7
- OOS window 2: bars=14400 span=2025-05-05 14:27..2025-06-18 01:18 inc=True dups=0 gaps={"daily_break": 27, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=e99866542b8d
- OOS window 3: bars=14400 span=2025-06-18 01:21..2025-07-31 15:12 inc=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=6a5954f4149f
- OOS window 4: bars=14400 span=2025-07-31 15:15..2025-09-15 02:03 inc=True dups=0 gaps={"daily_break": 26, "weekend": 7} ohlc=True nan=0 grid=True cont=True sha=4e7285351017
- OOS window 5: bars=14400 span=2025-09-15 02:06..2025-10-28 08:21 inc=True dups=0 gaps={"daily_break": 25, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=e19f4bc7559b
- OOS window 6: bars=14400 span=2025-10-28 08:24..2025-12-10 21:36 inc=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=cf7ed5d1ceac
- boundary continuity: OOS last (2025-12-10 21:36:00) +3min == frozen first (2025-12-10 21:39:00): True
- fragment: 128 bars 2026-09-04 17:33..2026-09-04 23:54 all_after_frozen=True sha=3770aae0f9cc

## OOS dataset identity: 3d615ad8d241b70e566050535e0889380e1869b85a26830e5fbd08f48e2f1a3c
## Verdict: FROZEN | anomalies: none
- MT5 closed (read-only).
