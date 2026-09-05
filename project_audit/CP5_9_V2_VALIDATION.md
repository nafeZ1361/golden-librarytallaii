# CP5.9 — A2-v2 EVALUATION (in-sample + independent OOS, one-shot)
Generated: 2026-09-05T17:42:53 | registered: family m=2, SEED=55056, N_BOOT=10000, BLOCK_LEN=h.
  Datasets: in-sample = CP5 frozen (be4fa581...); OOS = archive (060ba244...).

- determinism A/B (12 windows): PASS | v2-events subset-of-v1-events: PASS
- cp5_h5: n=161 rate=54.66% rho1=0.004 deff=0.980 | HAC-Bonf LB=45.86% | MBB-Bonf LB=45.96% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(61.29)), (2, 27, np.float64(59.26)), (3, 20, np.float64(35.0)), (4, 26, np.float64(69.23)), (5, 26, np.float64(50.0)), (6, 31, np.float64(48.39))]
- cp5_h20: n=160 rate=55.62% rho1=-0.133 deff=0.381 | HAC-Bonf LB=46.82% | MBB-Bonf LB=50.62% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(58.06)), (2, 27, np.float64(59.26)), (3, 20, np.float64(50.0)), (4, 25, np.float64(56.0)), (5, 26, np.float64(53.85)), (6, 31, np.float64(54.84))]
- oosv2_h5: n=189 rate=40.74% rho1=-0.056 deff=0.884 | HAC-Bonf LB=32.73% | MBB-Bonf LB=33.33% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(41.94)), (2, 32, np.float64(34.38)), (3, 31, np.float64(41.94)), (4, 32, np.float64(53.12)), (5, 31, np.float64(32.26)), (6, 32, np.float64(40.62))]
- oosv2_h20: n=189 rate=49.21% rho1=-0.053 deff=0.866 | HAC-Bonf LB=41.06% | MBB-Bonf LB=41.80% -> NO PROVEN DIRECTIONAL EDGE | per-window [(1, 31, np.float64(45.16)), (2, 32, np.float64(59.38)), (3, 31, np.float64(48.39)), (4, 32, np.float64(59.38)), (5, 31, np.float64(38.71)), (6, 32, np.float64(43.75))]

## Economic context (informational — frozen engine, registered geometry)
- cp5 C0: trades=161 net=$5200 expectancy=$32.30
- cp5 C1: trades=161 net=$5200 expectancy=$32.30
    (C1 expectancy after 3.5-pip cost: $28.80/trade)
- oosv2 C0: trades=164 net=$2200 expectancy=$13.41
- oosv2 C1: trades=164 net=$2200 expectancy=$13.41
    (C1 expectancy after 3.5-pip cost: $9.91/trade)

## CP5.9 verdicts (registered rule: advance iff BOTH datasets CANDIDATE same horizon)
- v2 h5: in-sample=False | OOS=False -> RETIRED (failed already in-sample)
- v2 h20: in-sample=False | OOS=False -> RETIRED (failed already in-sample)
