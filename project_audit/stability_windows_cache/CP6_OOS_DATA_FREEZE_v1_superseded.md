# CP6 — INDEPENDENT OOS DATA FREEZE
Generated: 2026-09-05T16:55:41 | REGISTERED OOS DEFINITION (before any evaluation):
- PRIMARY OOS = 6 x 14,400 M3 bars immediately PRECEDING the frozen CP5 boundary (last OOS bar = 2025-12-10 21:36; frozen first = 2025-12-10 21:39).
  This period was never fetched/used in any audited phase (all prior phases used 'latest-N' windows starting 2025-12-09/10).
- SUPPLEMENT = forward fragment strictly after 2026-09-04 17:30 (underpowered, reported separately, never merged).
- One-shot evaluation with frozen parameters; no tuning; no optimization.

- MT5 (500, 6140, '21 Aug 2026') | symbol digits=2 point=0.01
- retrieved_at_local: 2026-09-05T16:56:27 | timezone: naive broker-server (never converted)
- primary OOS fetch: requested range 2023-12-10..2025-12-10 21:36; got 86400 rows; took LAST 86400
- forward fragment: 198 bars after 2026-09-04 17:30:00
- OOS window 1: bars=14400 span=2025-03-20 00:24..2025-05-05 10:54 inc=True dups=0 gaps={"daily_break": 26, "weekend": 7} ohlc=True nan=0 grid=True cont=None sha=2327688beee6
- OOS window 2: bars=14400 span=2025-05-05 10:57..2025-06-17 20:48 inc=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=668ca3dc0efb
- OOS window 3: bars=14400 span=2025-06-17 20:51..2025-07-31 11:42 inc=True dups=0 gaps={"daily_break": 27, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=57ff0451b5bb
- OOS window 4: bars=14400 span=2025-07-31 11:45..2025-09-12 21:30 inc=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=585437dc2548
- OOS window 5: bars=14400 span=2025-09-12 21:33..2025-10-28 04:51 inc=True dups=0 gaps={"weekend": 7, "daily_break": 25} ohlc=True nan=0 grid=True cont=True sha=8cb55180ab8c
- OOS window 6: bars=14400 span=2025-10-28 04:54..2025-12-10 18:06 inc=True dups=0 gaps={"daily_break": 26, "weekend": 6} ohlc=True nan=0 grid=True cont=True sha=e68a5c04f5a8
- boundary continuity: OOS last (2025-12-10 18:06:00) +3min == frozen first (2025-12-10 21:39:00): False
- fragment: 198 bars 2026-09-04 14:03..2026-09-04 23:54 all_after_frozen=False sha=81fe24abfa97

## OOS dataset identity: 692ea48beb7f2aea862d17b283a4244c5f163120eaa603df4585aa2d03b2bcca
## Verdict: FROZEN | anomalies: OOS does not abut the frozen boundary; fragment contains bars at/before frozen last
- MT5 closed (read-only).
