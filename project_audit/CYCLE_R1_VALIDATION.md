# CYCLE-R1 — EVALUATION (one-shot; contracts committed a9b00d2 BEFORE this run)
Generated: 2026-09-05T22:26:42 | OOS identity f5b0124b363acaa0b3364618ccdc9f584bb21a043301df95f6b646a26faa410a
  | constants unchanged (SEED=55056, N_BOOT=10000, BLOCK_LEN=h, NW_LAG=h).
- note: freeze manifest honestly recorded ONE unclassified 345-min day-boundary gap in r1 w1 (documented, not repaired; day-boundary => no OR/indicator impact).

- determinism gate (A/B, a4 on cp5+r1, a2v2 on r1): PASS

## H-V3-1 (fade of first-breakouts) — IS = DS-ARCH-OOS
- A3-fade IS h5: n=189 rate=59.26% rho1=-0.056 deff=0.884 | HAC-Bonf LB=51.25% | MBB-Bonf LB=51.85% -> CANDIDATE | per-window [(1, 31, np.float64(58.06)), (2, 32, np.float64(65.62)), (3, 31, np.float64(58.06)), (4, 32, np.float64(46.88)), (5, 31, np.float64(67.74)), (6, 32, np.float64(59.38))]
- A3-fade IS h20: n=189 rate=50.79% rho1=-0.053 deff=0.866 | HAC-Bonf LB=42.64% | MBB-Bonf LB=43.39% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(54.84)), (2, 32, np.float64(40.62)), (3, 31, np.float64(51.61)), (4, 32, np.float64(40.62)), (5, 31, np.float64(61.29)), (6, 32, np.float64(56.25))]

## H-V3-1 — OOS = DS-R1-RESERVE (one-shot)
- A3-fade OOS h5: n=185 rate=57.30% rho1=-0.011 deff=0.914 | HAC-Bonf LB=49.15% | MBB-Bonf LB=48.65% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(54.84)), (2, 31, np.float64(48.39)), (3, 31, np.float64(54.84)), (4, 30, np.float64(56.67)), (5, 31, np.float64(51.61)), (6, 31, np.float64(77.42))]
- A3-fade OOS h20: n=185 rate=54.59% rho1=-0.107 deff=0.944 | HAC-Bonf LB=46.39% | MBB-Bonf LB=45.41% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(58.06)), (2, 31, np.float64(41.94)), (3, 31, np.float64(48.39)), (4, 30, np.float64(60.0)), (5, 31, np.float64(51.61)), (6, 31, np.float64(67.74))]

## H-V3-2 (session-conditioned breakout) — IS = DS-CP5-MAIN
- A4 IS h5: n=156 rate=50.00% rho1=-0.058 deff=0.959 | HAC-Bonf LB=41.03% | MBB-Bonf LB=41.03% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 30, np.float64(60.0)), (2, 26, np.float64(46.15)), (3, 19, np.float64(26.32)), (4, 26, np.float64(65.38)), (5, 25, np.float64(40.0)), (6, 30, np.float64(53.33))]
- A4 IS h20: n=155 rate=52.90% rho1=-0.211 deff=0.361 | HAC-Bonf LB=43.92% | MBB-Bonf LB=47.10% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 30, np.float64(53.33)), (2, 26, np.float64(57.69)), (3, 19, np.float64(42.11)), (4, 25, np.float64(60.0)), (5, 25, np.float64(52.0)), (6, 30, np.float64(50.0))]

## H-V3-2 — OOS = DS-R1-RESERVE (one-shot)
- A4 OOS h5: n=183 rate=47.54% rho1=0.053 deff=1.216 | HAC-Bonf LB=38.42% | MBB-Bonf LB=37.43% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(38.71)), (2, 31, np.float64(51.61)), (3, 31, np.float64(54.84)), (4, 29, np.float64(51.72)), (5, 31, np.float64(38.71)), (6, 30, np.float64(50.0))]
- A4 OOS h20: n=183 rate=46.45% rho1=-0.093 deff=0.469 | HAC-Bonf LB=38.18% | MBB-Bonf LB=39.89% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(45.16)), (2, 31, np.float64(45.16)), (3, 31, np.float64(51.61)), (4, 29, np.float64(41.38)), (5, 31, np.float64(48.39)), (6, 30, np.float64(46.67))]

## Economic context (informational)
- A4-continuation (R1 OOS): trades=124 netC0=$2000 expC0=$16.13 expC1=$12.63
- A3-fade(inverted) (R1 OOS): trades=133 netC0=$2600 expC0=$19.55 expC1=$16.05

## CYCLE-R1 verdicts (registered rule: ADVANCE iff h5 AND h20 CANDIDATE on IS and OOS)
- H-V3-1 fade: IS failed | OOS failed -> RETIRED
- H-V3-2 session: IS failed | OOS failed -> RETIRED
