# DATA REGISTRY — Golden Library (R1)

Generated: 2026-09-05 | Source of truth: the frozen manifests. Every research
run MUST cite the dataset identity hash it used.

## Registered datasets (immutable/frozen)

| ID | Symbol/TF | Period (broker time) | Bars | Identity (sha256-combined) | Candle convention | Status |
|---|---|---|---|---|---|---|
| DS-CP5-MAIN | XAUUSD. / M3 | 2025-12-10 21:39 → 2026-09-04 17:30 | 86,400 | `be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3` | plain OHLC, naive broker tz | **BURNED** (IS for A1-v1/A2-v1/A2-v2) |
| DS-CP6-OOS | XAUUSD. / M3 | 2025-03-20 03:54 → 2025-12-10 21:36 | 86,400 | `3d615ad8d241b70e566050535e0889380e1869b85a26830e5fbd08f48e2f1a3c` | plain | **BURNED** (OOS for A1-v1/A2-v1 → FAILED REPLICATION) |
| DS-ARCH-OOS | XAUUSD. / M3 | 2024-06-26 11:21 → 2025-03-20 03:51 | 86,400 | `060ba2440aa495ab28097d9ed810a5e3bcdf09b00ffba1d15b2e536cea2ea1d7` | plain | **BURNED** (OOS for A2-v2 → RETIRED) |
| DS-FRAG-FWD | XAUUSD. / M3 | 2026-09-04 17:33 → 2026-09-04 23:54 | 128 | (in CP6 manifest) | plain | supplement only — underpowered, never verdict-relevant |

## Data quality record (per dataset)

- Acquisition: MT5 read-only, ONE bulk fetch, `start_pos=1` (DS-CP5) /
  TZ-corrected `copy_rates_range` bounds (DS-CP6-OOS, DS-ARCH-OOS — the
  +3:30 local-to-broker fix is MANDATORY for any future range fetch).
- Timezone: naive broker-server time, never converted in research data.
- Gaps: all classified (daily break / weekend); DS-CP5 had 6 flagged gaps
  (1 missing bar + 2 holiday closures + 3 intraday) — none inside OR windows;
  DS-CP6-OOS and DS-ARCH-OOS: zero unclassified gaps.
- Duplicates: 0 everywhere. NaN/Inf: 0 everywhere. OHLC validity: PASS everywhere.
- Spread model: NOT modeled in research economics (C0/C1/C2 constant-pip
  arithmetic only — registered limitation; per-trade cost ledger = required
  gate before any DEMO claim).
- Incomplete candle policy: `start_pos=1` / probe-verified exclusion (CP5.2).

## Consumption ledger (anti-reuse rule — §3 No OOS Reuse)

| Period | Consumed by | Reusable for |
|---|---|---|
| 2025-12-10 → 2026-09-04 | CP5.5/5.6/5.7 IS (A1-v1, A2-v1, A2-v2) | NOTHING directional (burned) |
| 2025-03-20 → 2025-12-10 | CP6 OOS (A1-v1/A2-v1 replication) | NOTHING directional (burned) |
| 2024-06-26 → 2025-03-20 | CP5.9 OOS (A2-v2) | NOTHING directional (burned) |
| **2021-06-20 → 2024-06-26** | **NOBODY — UNSEEN RESERVE** (~230k M3 bars available) | OOS for exactly ONE future hypothesis family (first-come rule) |
| **post 2026-09-04 (forward stream)** | 128-bar fragment only | the cleanest future OOS — accumulates daily |

Rule: a new hypothesis may consume an unseen reserve ONCE. After its verdict
(either direction), that period is burned for that hypothesis family.
