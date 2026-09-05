# CP5.5 CONTROLLED PERFORMANCE EVALUATION
Generated: 2026-09-05T14:52:37

## Run provenance note
- Run 1 (14:50) crashed in Phase E on an audit-script key-name error (max_drawdown_pct vs the frozen harness's max_drawdown) AFTER hit-rate printing, BEFORE economic computation. Fix was mechanical (audit artifact only; frozen sources untouched; rule 19 compliant). All decision rules were frozen BEFORE run 1; NO rule was changed after any result was seen.

## Phase A — Pre-flight
- branch=code-refactoring-guide-41a87 HEAD=9184e5b4f5f10aaaafd257fe8a05aaf61c6e5ab5
- baseline-lock-v1=dd526e588cdf | cp5-source-freeze-v1=9184e5b4f5f1 | HEAD==freeze-tag: True
- source hashes match Amendment 1: True
- six CSV hashes match manifest: True | dataset identity recomputed OK: True
- DATASET IDENTITY: be4fa581f59c635d22da49ef4443c5801e0e60cd5852d6a9b0fdca822186a2a3
- CP5.3 = PASS WITH CONDITIONS (6 documented flagged gaps; none inside the empirical OR window) | CP5.4 = PASS (deterministic, isolated, MT5-free)
- gate to proceed: OK

## Registered decision rules (fixed BEFORE results — from pre-registration)
- PRIMARY cells only: A1xH5, A1xH20, A2xH5, A2xH20 (exploratory A2-M15/H1 are NOT computable: no M15/H1 data was ever frozen — reported as deferred).
- D: CI includes 50% -> NO PROVEN DIRECTIONAL EDGE (cell); CI entirely below 50% -> EVIDENCE AGAINST DIRECTION (cell); CI entirely above -> CANDIDATE DIRECTIONAL EDGE (cell; not sufficient alone).
- K strategy verdict: PROVISIONAL/PROVEN EDGE requires ALL of: statistical gate in BOTH primary horizons (h5 AND h20 aggregate CI lower bound > 50%; strict conjunctive rule prevents horizon cherry-picking), economic gate (aggregate expectancy > 0 AND >=3/5 OOS fold-positions positive AND >=3/6 windows positive), and cost gate C1 (expectancy stays > 0) — C1/C2 are computed ONLY for strategies passing the statistical gate (registered §13). If only one horizon passes -> cell reported as CANDIDATE, strategy = NO PROVEN EDGE. No per-cell minimum-N was pre-registered; empty-event cells are INCONCLUSIVE (no post-hoc threshold is invented).
- ECON-MAPPING (execution note, fixed pre-computation): economic entries = exactly the run-start events counted by the registered hit-rate metric (harness trig=conf=event series). Rationale: hypotheses are stated over fresh events; sustained-run re-entries would be a different, unregistered hypothesis. For A1 both mappings coincide.
- HA-NOTE (documented per master-command rule 18): the command's economics block lists 'HA' (the baseline control's candle type); the registered and frozen definition for A1/A2 is PLAIN candles (pre-registration §B/D2, Amendment 1) and the frozen dataset is plain candles. The command itself defers to 'the economic definition registered in baseline/pre-registration' — plain-candle signals with baseline economics (SL100/TP200/2%/$5000) are therefore used. Recorded BEFORE any metric was computed.

## Phase B — Signal generation (frozen sources, frozen data)
- window 1: A1 events=226 | A2 events=835
- window 2: A1 events=224 | A2 events=464
- window 3: A1 events=235 | A2 events=116
- window 4: A1 events=218 | A2 events=151
- window 5: A1 events=227 | A2 events=129
- window 6: A1 events=246 | A2 events=163

## Phases C+D — Pre-registered hit-rate cells (per window and aggregate)
- A1 H5 aggregate: events=1376 rate=55.60% wald95=[52.97, 58.22] -> CANDIDATE DIRECTIONAL EDGE
- A1 H20 aggregate: events=1374 rate=51.97% wald95=[49.32, 54.61] -> NO PROVEN DIRECTIONAL EDGE
- A2 H5 aggregate: events=1855 rate=52.56% wald95=[50.29, 54.83] -> CANDIDATE DIRECTIONAL EDGE
- A2 H20 aggregate: events=1851 rate=51.65% wald95=[49.37, 53.92] -> NO PROVEN DIRECTIONAL EDGE

## Phase E — Economic backtest (fixed registered geometry, per window)
- A1: per-window net PnL = [1900.0, 1600.0, 1900.0, 1300.0, 500.0, 3500.0]
  aggregate: trades=970 net=$10700.00 expectancy=$11.03 | OOS fold-positions positive 5/5 | windows positive 6/6 | mean ROI 35.67%
- A2: per-window net PnL = [2800.0, 3800.0, -500.0, 0.0, 1700.0, 900.0]
  aggregate: trades=816 net=$8700.00 expectancy=$10.66 | OOS fold-positions positive 3/5 | windows positive 4/6 | mean ROI 29.00%

## Phase F — Cost / execution assumptions (explicit limitations)
- entry price = same-bar close of the signal bar (registered control convention; optimistic vs live [-2] discipline — CP3 divergence documented)
- same-candle TP/SL ambiguity resolves TP-FIRST (optimistic; CP2 S3)
- no spread/commission/slippage/swap in the base engine -> ALL CP5.5 economics are C0 (gross). LIMITATION: absolute expectancy is optimistic by the full cost load. Pre-registered C1 (3.5 pips) / C2 (6 pips) are computed ONLY for strategies passing the statistical gate (registered §13 anti-metric-shopping rule).
- gap-through exits fill at SL/TP price, not open (optimistic; CP2 S4/S5)
- position sizing constant $100 risk (2% of INITIAL balance, 0.1 lot) — matches control
- end-of-data open position silently dropped (engine behavior, CP2 S7)
- candle-close convention: signals/entries use bar close; no forming candle in data (CP5.2 probe)

## Cost gate (only for statistical-gate passers, registered §13)
- A1: statistical gate NOT passed -> C1/C2 not computed (anti-metric-shopping rule)
- A2: statistical gate NOT passed -> C1/C2 not computed (anti-metric-shopping rule)

## Phase G — Window stability
- A1 net-PnL signs across windows 1..6: [++++++] | windows positive: 6/6
  largest single positive-window share of total profit: window 6 = 32.7% (no single-window dominance)
  hit-rate direction sign per window (h5): ['56.2', '59.8', '56.6', '55.0', '51.1', '54.9']
- A2 net-PnL signs across windows 1..6: [++--++] | windows positive: 4/6
  largest single positive-window share of total profit: window 2 = 41.3% (no single-window dominance)
  hit-rate direction sign per window (h5): ['54.3', '52.2', '47.4', '51.3', '52.7', '49.7']

## Phase H — Minimum sample
- No per-cell minimum-N was pre-registered (documented limitation). Cells with zero events are INCONCLUSIVE; all other cells are judged by the registered CI rule only. Economic min rules applied as registered: >=3/5 OOS fold positions, >=3/6 windows.

## Phase I — Multiple testing
- tested: 2 hypotheses x 2 horizons = 4 primary cells; 4 aggregate tests; 6 windows each (reported, not selected). Exploratory cells (A2-M15/H1): NOT computable on the frozen M3 dataset — deferred; would require a new registered freeze. No multiplicity correction across the 4 primary cells was pre-registered -> LIMITATION recorded; per §14, a single passing cell among several requires independent confirmation (CP6) before any stronger claim. No correction was invented post-hoc.

## Phase J — Leakage / look-ahead recheck (audit statements)
- signals computed only from each window's frozen df (no cross-window reads; CP5.4 isolation proof); forming candle absent (CP5.2 probe); indicators trailing-only (CP5.1 static audit); OR built from completed bars with registered eligibility (Amendment 1); normalization alters nothing (CP5.4 raw-value assertion); signal timestamp = bar close, outcome = close[i+h] (future only as the prediction target); economics enter at the signal bar's close with exits evaluated from the NEXT bar (frozen harness semantics).

## Phase K — Primary decisions
- A1: cells={'h5': 'CANDIDATE DIRECTIONAL EDGE', 'h20': 'NO PROVEN DIRECTIONAL EDGE'} | stat_gate(both)=False | econ_gate=True | cost_gate=None => NO PROVEN EDGE
- A2: cells={'h5': 'CANDIDATE DIRECTIONAL EDGE', 'h20': 'NO PROVEN DIRECTIONAL EDGE'} | stat_gate(both)=False | econ_gate=True | cost_gate=None => NO PROVEN EDGE

## Phase L — Exploratory results
- none computed (A2-M15/H1 not frozen) — nothing to label; no primary/exploratory mixing occurred.

## Phase M — Robustness preview (plan for the NEXT stage only — nothing executed)
- parameter perturbation (RSI 14->10/20, 30/70->25/75, BB 20/2->15/3; OR 120->90/150min, 1.5x->1.2/2.0x)
- SL/TP geometry sensitivity; entry-timing sensitivity (next-bar-open variant)
- cost sensitivity C1/C2 with per-trade records; spread-widening stress
- window perturbation (±k bars), regime split (trend/range/vol buckets), long/short split
- rolling performance and outlier-trade impact (top-3 trade removal)
