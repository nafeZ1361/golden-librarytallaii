# CP6 — INDEPENDENT OOS VALIDATION (one-shot, frozen parameters)
Generated: 2026-09-05T17:04:54 | OOS dataset identity:
  3d615ad8d241b70e566050535e0889380e1869b85a26830e5fbd08f48e2f1a3c
  (6 x 14,400 M3 bars 2025-03-20..2025-12-10 21:36, preceding the frozen CP5 boundary — never used in design/selection; + 128-bar forward fragment reported separately). Registered constants unchanged: SEED=55056,
  N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h, Bonferroni m=4. NO tuning occurred.

- pre-flight: OOS CSV hashes == manifest: True | verdict: FROZEN | anomalies: []

## Determinism gate (A/B, frozen functions, OOS windows)
- determinism: PASS (all A==B byte-identical)

## One-shot evaluation (h5/h20, per window and aggregate)
- A1_h5: n=1337 rate=49.29% | rho1=0.030 deff=1.042 | HAC-Bonf LB=46.16% | Boot-Bonf LB=45.85% -> NO PROVEN DIRECTIONAL EDGE ON OOS
    per-window rates: ['w1: 43.4', 'w2: 49.1', 'w3: 46.1', 'w4: 56.2', 'w5: 45.2', 'w6: 57.3']
- A1_h20: n=1335 rate=51.46% | rho1=0.103 deff=1.130 | HAC-Bonf LB=48.20% | Boot-Bonf LB=47.87% -> NO PROVEN DIRECTIONAL EDGE ON OOS
    per-window rates: ['w1: 47.1', 'w2: 48.9', 'w3: 59.2', 'w4: 57.6', 'w5: 44.0', 'w6: 54.3']
- A2_h5: n=4957 rate=50.96% | rho1=0.077 deff=1.130 | HAC-Bonf LB=49.27% | Boot-Bonf LB=49.07% -> NO PROVEN DIRECTIONAL EDGE ON OOS
    per-window rates: ['w1: 51.9', 'w2: 50.2', 'w3: 52.3', 'w4: 52.1', 'w5: 50.9', 'w6: 48.6']
- A2_h20: n=4949 rate=50.50% | rho1=0.394 deff=2.137 | HAC-Bonf LB=48.17% | Boot-Bonf LB=47.92% -> NO PROVEN DIRECTIONAL EDGE ON OOS
    per-window rates: ['w1: 58.2', 'w2: 48.9', 'w3: 51.4', 'w4: 48.5', 'w5: 49.2', 'w6: 47.7']

## Economic context (informational — C0/C1, frozen engine, event-mapping)
- A1: trades=624 netC0=$-2700 expC0=$-4.33 expC1=$-7.83
- A2: trades=822 netC0=$3300 expC0=$4.01 expC1=$0.51

## CP6 verdicts (registered framing)
- A1-h5 (the CP5.6 surviving candidate): OOS rate=49.29% (n=1337), corrected LBs: HAC-Bonf 46.16%, Boot-Bonf 45.85% -> FAILED REPLICATION
- A1-h20: NO PROVEN DIRECTIONAL EDGE ON OOS
- A2-h5: NO PROVEN DIRECTIONAL EDGE ON OOS (no CP5.6 candidate existed; reported as measured)
- A2-h20: NO PROVEN DIRECTIONAL EDGE ON OOS
- Forward fragment (128 bars): underpowered supplement — NOT used for any verdict; retained as evidence of strict-forward behavior.
