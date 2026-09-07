# CP5 PRE-REGISTRATION — Strategies A1 & A2

Experiment ID: **CP5** | Status: **REGISTERED, NOT EXECUTED**
Written: 2026-09-04 | Registering commit: see git log (this file is committed
BEFORE any CP5 result exists — that is the point of pre-registration).

Baseline verification at registration time (per BASELINE_LOCK.md rule):
tag `baseline-lock-v1` → commit `dd526e5` = HEAD; working tree clean.
Control conclusion: **NO PROVEN EDGE** (immutable, see BASELINE_LOCK.md).

Unseen-data statement (verified from evidence): **no A1/A2 result artifact
exists anywhere** (CP4e: `attempted 2026-09-04; result evidence not preserved;
no scientific conclusion may be attributed to CP4e.`). No CP5 candidate
result has been inspected before this registration. The strategies below have
never produced a preserved measurement.

CP4c precision note carried verbatim (must not be softened in any future report):

```
No positive directional edge:
every aggregate's Wald95 CI includes or lies below 50%.

supertrend_h5 CI [44.81%, 49.84%] excludes 50% on the downside —
evidence AGAINST direction, not merely indeterminate.
```

---

## A. Hypotheses (falsifiable)

### H-A1 (Mean Reversion)
IF the mean-reversion hypothesis is true on XAUUSD M3, THEN bars where RSI(14)
freshly crosses down through 30 while close ≤ BB(20,2)-lower (buy events), or
freshly crosses up through 70 while close ≥ BB(20,2)-upper (sell events), are
followed by a counter-move: close[i+h] reverts in the direction opposite the
extreme in MORE THAN 50% of events, for h = 5 and h = 20, with the 95% Wald
CI lower bound above 50%.
Falsification: CI includes or lies below 50% for a cell → H-A1 rejected for
that cell; no cell passing → strategy dead.

### H-A2 (Breakout)
IF the breakout-continuation hypothesis is true on XAUUSD M3, THEN the first
bars after the broker-day opening range (first 120 minutes) where close breaks
above OR-high (or below OR-low) with tick_volume ≥ 1.5 × mean(OR bar volumes)
are followed by continuation: close[i+h] continues in the break direction in
MORE THAN 50% of run-start events, for h = 5 and h = 20, with the 95% Wald CI
lower bound above 50%.
Falsification: same rule as H-A1.

### H-ECO (Economic companion hypothesis — evaluated only if a statistical cell passes)
IF a directional edge is statistically confirmed, THEN the fixed geometry
inherited from the control (SL 100 / TP 200 pips, 2% initial risk) yields
aggregate OOS expectancy > 0 that SURVIVES cost scenario C1 (§13).

A hypothesis is accepted only with ALL gates of §12. Everything else is
NO PROVEN EDGE for that strategy.

---

## B. Data Specification

| Item | Registration |
|---|---|
| Symbol | `XAUUSD.` (broker symbol, trailing dot) |
| Primary timeframe | M3 (locked methodology) |
| Secondary (exploratory, A2 only) | M15, H1 — reported, never used for selection |
| Candle type | **PLAIN candles** for strategies (registered deviation D2 from control's HA — A1/A2 are defined on plain candles; harness supplies plain windows) |
| Source | MetaTrader 5 via `research_harness.load_windows` / `window_bounds_from_m3` (same method as CP4c/CP4d) |
| Window definition | 6 windows × 14,400 M3 bars, fetched with `start_pos=1` (forming M3 candle excluded — CP1 proof); M15/H1 fetched by `copy_rates_range` over the identical M3 boundaries |
| Freeze rule (D3) | At CP5 execution start, windows are fetched ONCE and frozen to `project_audit/stability_windows_cache/cp5_window_{i}_df.csv`; ALL subsequent steps read the frozen CSVs. Run date recorded in the result header. |
| Start/end rules | Bar-count boundaries (latest 86,400 closed M3 bars); boundary timestamps recorded in the result artifact |
| Current candle | Forming M3 candle never enters data (start_pos=1). Signal bar = last CLOSED bar of any live-side use (not part of CP5 measurement) |
| Missing bars / gaps | Broker history as-is; gaps are market-closure events (CP1: 192/192 verified); no gap filling, no synthetic bars |
| Duplicate bars | None observed (CP1); loader sorts by time defensively |
| Timezone | Naive broker-server time, never converted (documented CP1); OR day boundaries therefore = broker dates |

## C. Signal Definition (exactly as coded — parameters FIXED, no grid)

### A1 — `strategy_a1_meanrev.py::signal_fn(wdf, tf_name)` (pinned: commit `d3524bb`)
- Features (computed on the supplied window df only): `pandas_ta.rsi(close, length=14)`,
  `pandas_ta.bbands(close, length=20, std=2)` (SMA bands, BBL/BBU columns)
- BUY event at bar i ⟺ `rsi[i] < 30 AND rsi[i-1] >= 30 AND close[i] <= BBL[i]`
- SELL event at bar i ⟺ `rsi[i] > 70 AND rsi[i-1] <= 70 AND close[i] >= BBU[i]`
- All other bars: `hold`. Only the cross bar fires (fresh extreme).
- Parameters FIXED a priori: RSI 14/30/70, BB 20/2 — textbook defaults chosen by
  the strategy author before any data inspection; NOT tuned on any project data.
- Candle type: plain. tf_name accepted but unused (TF-agnostic by construction).

### A2 — `strategy_a2_breakout.py::signal_fn(wdf, tf_name)` (pinned: commit `d3524bb`)
- Opening Range: per naive broker date present in the window; OR = bars
  `[day_start, day_start + OR_BARS[tf])` with OR_BARS = {3m: 40, 15m: 8, 1h: 2}
  (= 120 minutes); OR-high/low/mean-volume from those bars only
- OR completeness rule (as coded): a day is usable iff
  `or_bars_present >= max(2, int(or_bars × 0.6))`
- BUY state at bar k (k after OR close, same day) ⟺ `vol[k] >= 1.5 × avg_or_vol`
  AND `close[k] > OR_high`; SELL mirrored below OR-low
- A2 emits STATE runs, not single events; `research_harness.hit_rate` counts
  only run-STARTS as events (run = consecutive same-direction bars) — registered
  semantics, identical to the generalized CP4c metric
- Parameters FIXED a priori: OR 120 min, VOL_MULT 1.5× — not tuned on project data.

### Execution / measurement convention (inherited from locked control)
- Signal at bar i uses information up to and including close[i]; measurement
  entry = close[i]; hit-rate outcome = close[i+h] vs close[i] (h ∈ {5, 20}).
  This is the SAME same-bar-close convention as the locked control (CP2-documented
  optimistic bias inherited, not hidden).
- Backtest track (economic): `research_harness.harness_backtest` in FIXED mode,
  SL 100 / TP 200 pips, 2% initial risk, $5,000 initial balance — engine
  equivalence to project `run_backtest()` already proven (CP4b: True).
- Exits: TP-first on same candle; no costs in the base engine (cost gate §13).

## D. Metrics (registered — no post-hoc additions)

Per cell (strategy × TF × horizon) and per window:
`events, hits, rate_pct, wald95` (hit-rate track); `total_trades, winrate,
roi, profit_factor, max_drawdown, total_profit, expectancy = total_profit /
total_trades` (economic track). Aggregate + per-window tables. Artifacts:
`project_audit/CP5_{A1,A2}_{M3,M15,H1}_hitrate.{json,md}` and
`project_audit/CP5_{A1,A2}_{M3}_econ.{json,md}`. Nothing else is added later
without a new registration (CP5b).

## 12. Acceptance Criteria (registered BEFORE any result)

A strategy reaches **PROVISIONAL EDGE** only if ALL hold:
1. Statistical: aggregate hit-rate 95% Wald CI lower bound **> 50%** for the cell.
2. Economic: aggregate OOS expectancy **> 0** AND ≥ **3 of 5** fold-pairs
   (window i → i+1) positive, on the M3 economic track.
3. Not single-window: the positive expectancy is not produced by one window
   (≥ 3 of 6 windows positive individually).
4. Economic survival: expectancy remains **> 0** under cost scenario C1 (§13).
5. Integrity: determinism checks pass (§16), leakage audit clean (§15),
   no methodology violation during execution.
Failure of ANY item → **NO PROVEN EDGE** for that strategy (recorded, kept as
evidence; next hypothesis per the decision tree).

## 13. Economic Edge — cost scenarios (registered)

Pip = $0.1 (digits=2). Cost scenarios subtracted per round trip from each
trade's pip P&L:
- C0 = 0 pips (control comparability)
- C1 = 3.5 pips (upper documented XAUUSD spread range, CP2 §8)
- C2 = 6.0 pips (stress: wide spread + slippage)
Implementation: a NEW file (`cp5_cost_sensitivity.py`) post-processing recorded
trades — NO modification of existing source (§34). Cost analysis runs only for
strategies that pass the statistical gate (avoids metric-shopping on failures).

## 14. Multiple Testing Register (mandatory disclosure)

| Item | Registration |
|---|---|
| Hypotheses tested | 2 (A1, A2) |
| Primary cells | A1-M3×{h5,h20}, A2-M3×{h5,h20} = **4** |
| Secondary exploratory cells | A2-M15×{h5,h20}, A2-H1×{h5,h20} = 4 — reported, labeled exploratory, NEVER used for selection |
| Parameter variants | **0** (no grid, no IS selection — see D1) |
| Selection rule | NONE — every registered cell is reported regardless of outcome |
| Results inspected before this registration | NONE (evidence-verified) |
| Future additions | Any new cell/variant requires a new registration (CP5b) with explicit corrected α (e.g., Bonferroni over cumulative cell count) |
| Interpretation rule | A single passing cell among many tested cells is treated with selection-bias suspicion and must be independently confirmed (CP6) before any stronger claim |

## 15. Data Leakage Audit — static results (no execution)

Checked per directive §10/§15: future data — none (all features use bars ≤ i);
forming candle — excluded by fetch (start_pos=1); centered rolling — none
(RSI RMA + SMA bands are trailing); negative shift — none; future high/low —
none (A2 OR uses only bars before k); future volume — none (vol[k] is the
decision bar's own volume, known at its close); future normalization/scaling —
none; cross-window contamination — none (each window signals independently from
its own df); train/test contamination — none (no training, no grid); parameter
selection leakage — none (fixed a-priori params, no IS search).
**Conclusion: no leakage detected at static level. Runtime re-checks: §16 + CP5.3.**

## 16. Determinism Test Design (to run in CP5.2, after freeze)

- D1 signals: for each frozen window CSV, run `signal_fn` twice →
  SHA-256 of the serialized states list must be identical (both strategies).
- D2 engine: run `harness_backtest` twice per window → byte-identical metrics dict.
- D3 environment: recorded Python/pandas/pandas_ta versions in every artifact header.
- ANY failure → STOP, root-cause, no scientific reading of results (per §21/§33).

## 17/18. Registered Deviations from the Locked Methodology (formal, per §18)

| ID | Deviation | Justification |
|---|---|---|
| D1 | NO parameter grid, NO IS selection; params fixed a priori; fold structure (window i → i+1) retained for reporting | Eliminates selection bias entirely — stronger than the control's 11-combo IS-only grid |
| D2 | Plain candles for strategies (control used HA) | A1/A2 are defined on plain candles; pipeline/window method unchanged |
| D3 | Windows frozen to CSV at execution start | Reproducibility + determinism; control methodology fetched live per run |
| D4 | Cost scenarios C0/C1/C2 added as a post-processing gate | Implements the locked BASELINE_LOCK.md §4-3 economic requirement; no source modified |

Everything else (symbol, window method, WFO fold structure, hit-rate metric +
Wald CI, fixed 100/200 geometry, 2% initial risk) = the locked methodology,
unchanged.

---

## Static Audit Findings (CP5.1 — recorded BEFORE any execution; NO source changed)

### A1
- **F1 (MINOR, no signal impact): ineffective NaN guard.**
  BUG: `if r[i] is None or lo[i] is None or r[i-1] is None` never triggers
  because pandas `tolist()` yields float `nan`, not `None`.
  ROOT CAUSE: NaN-vs-None confusion.
  IMPACT: none on signals — NaN comparisons evaluate False → warm-up rows stay
  `hold` (net behavior identical to intended guard).
  PROPOSED FIX: `pd.isna(...)` checks. VALIDATION PLAN: static assert that the
  first max(14,20) rows are `hold` on a frozen window.
  **AWAITING USER APPROVAL — source untouched.**
- **F2 (NOTE): header comment says "Bollinger re-entry" but the code requires
  close BEYOND the band (penetration at the cross bar).** Code and its inline
  docstring agree with each other; this registration adopts the CODE semantics
  (§C above). Comment-only discrepancy; fix optional, not required.
- **F3 (NOTE): `tf_name` accepted but unused** — A1 is TF-agnostic by design.

### A2
- **F4 (MEDIUM, boundary artifact): partial first day.** Window boundaries are
  bar-count based, not day-aligned → the FIRST calendar day of each window may
  start mid-day; its "OR" is then built from partial data (and the coded 60%
  completeness rule, F5, lets it through).
  ROOT CAUSE: bar-count window boundaries.
  IMPACT: ≤ 1 day per window (≤ 6 days of ~180) can carry a non-true OR;
  deterministic but a boundary artifact.
  PROPOSED FIX (awaiting approval): skip signaling on the first day of each
  window (or require the day's first bar to be the window's first bar AND
  full OR bar count). VALIDATION PLAN: diff signals with/without the skip on
  frozen windows before any scientific run.
- **F5 (NOTE, registered as-is): OR completeness rule accepts ≥ 60% of OR bars**
  (`max(2, int(or_bars*0.6))`) — short/partial sessions produce reduced ORs by design.
- **F6 (NOTE): A2 emits state runs; `hit_rate` counts run-starts only** — registered (§C).
- **F7 (NOTE): dead else-branch for non-datetime `time`** — unreachable in this pipeline.
- **F8 (NOTE, secondary TFs only): possible partial final M15/H1 bar** —
  `copy_rates_range` over M3 boundaries can include a higher-TF bar still forming
  at fetch time. Affects ONLY exploratory A2-M15/H1 cells. Mitigation (if those
  cells run): trim the last higher-TF bar whose close time exceeds the last M3
  timestamp — requires approval before the secondary run.

### Shared
- **S1 (NOTE): same-bar-close convention** (signal uses close[i], entry at close[i]) —
  identical to the locked control's documented optimistic bias; inherited, not hidden.
- **S2 (CONFIRMED clean): no MT5 access inside either strategy; both are pure
  functions of the supplied window df; deterministic; coherent pipeline by construction.**

### §10 checklist verdicts (static)
features: trailing-only ✓ | timestamps: naive broker, documented ✓ | current
candle: signal bar's own close used, entry at that close (control convention) ✓ |
future candle: none ✓ | rolling: trailing ✓ | shifts: only [i-1] past ✓ |
volume filter: decision-bar volume + past OR mean ✓ | OR definition: broker-day
120-min, 60% completeness rule, first-day artifact flagged (F4) ✓ | execution
timing: same-bar close, TP-priority (inherited biases documented) ✓ |
reproducibility: params fixed + code pinned + freeze rule D3 ✓

## 24. CP5 Execution Sequence (gated — each step needs its own authorization)

```
CP5.0  Pre-registration (THIS document) + CP5.1 static audit  → this turn
CP5.2  Freeze windows + determinism (D1/D2)                   → gate
CP5.3  Runtime leakage re-check + freeze manifest             → gate
CP5.4  Control sanity: locked-baseline numbers reproduced on frozen data (optional)
CP5.5  A1/A2 primary cells (M3 hit-rate, h5/h20)              → gate
CP5.6  Statistical evaluation vs §12-1                         → gate
CP5.7  Economic track (fixed geometry, per §C)                 → gate
CP5.8  OOS/fold validation vs §12-2/3                          → gate
CP5.9  Robustness (only if prior gates passed)                 → gate
CP5.10 Cost sensitivity C1/C2 (only if statistical gate passed) → gate
CP5.11 Final Edge Verdict per decision tree                    → gate
```

## 22/23. Provenance commitments

Code pinned at preservation commit `d3524bb` (A1/A2/harness); lock at `dd526e5`;
this registration committed before any run. Every CP5 artifact header records:
experiment ID, date, code commit, frozen-window filenames + row counts, library
versions, and the registration file it executes. No result is valid without
its artifact file on disk (terminal output alone is not evidence).

---

FINAL OBJECTIVE REMINDER: the deliverable is TRUTH. If A1/A2 fail any gate,
the recorded outcome is NO PROVEN EDGE — a valid scientific result — and the
control remains the reference. NO LIVE TRADING at any point of CP5.

---

# AMENDMENT 1 — 2026-09-04 (Methodology Finalization — registered BEFORE any CP5 result)

Gate: CP5 Methodology Review. User-approved decisions: F1 (fix) and F4 (exact
OR definition to be registered pre-results). At the time of this amendment NO
CP5 performance number exists anywhere (no CP5.5+ step has run) — this
amendment cannot be result-driven by construction.

## A1. What changed and why

| ID | Change | Reason | Hypothesis impact |
|---|---|---|---|
| F1 | `strategy_a1_meanrev.py`: NaN guard `is None` checks → `pd.isna(...)` (now also covering `up[i]`) | Defensive correctness only: float NaN never equals None, so the old guard never fired | NONE — bit-identical outputs proven on all 6 fixtures (§A4) |
| F4 | `strategy_a2_breakout.py`: OR eligibility registered AND implemented — (a) interior days only, (b) verified session open (previous bar = previous calendar day AND session break ≥ 30 min), (c) complete gap-free OR (exactly OR_BARS bars AND exact (OR_BARS−1)×tf-min span); the former 60% completeness rule (old F5) is REMOVED | A bar-count window boundary can fall mid-session; a partial first-day OR is not a true Opening Range. Incomplete ORs must not generate signals | H-A2 event population redefined structurally (STRICTER); registered before results |

## A2. Final definitions (binding — supersedes §C where they differ)

**A1 (final):** unchanged — RSI(14) fresh cross 30/70 AND close beyond the
BB(20,2) band on the cross bar; params fixed a priori (14/30/70, 20/2); plain
candles; NaN-aware warm-up guard (proven behavior-preserving).

**A2 (final):** §C as amended by the OR-eligibility rule (a)(b)(c) above.
Signals only on interior days with a verified session open and a complete
gap-free OR; days failing any condition produce NO signals. Volume filter
1.5×, breakout direction, run semantics, fixed params (120 min, 1.5×) — all
unchanged. Session-break threshold registered at 30 min (empirical minimum
interior day-start gap ≥ 60 min — §A3).

**Data / metrics / acceptance / failure criteria:** unchanged from §B, §D,
§12, §13. Registered deviations D1–D4 remain as registered.

## A3. Empirical session facts behind the F4 rule (structural survey of the frozen Sep-3 fixtures — timestamps only, no strategy output touched)

- Trading day ≈ 459–460 M3 bars (~23 h). NO day has < 40 bars (0 of 195).
- Interior day-start gap ~63 min; weekend ~2949 min; holiday variants ≥ 213 min;
  minimum observed interior day-start gap ≥ 60 min → `SESSION_BREAK_MIN = 30`.
- First bar of day: 01:00/01:03 on ~90% of days, 00:00/00:03 on DST-shifted
  days → the rule is STRUCTURAL (no session-clock constant needed).
- Every window's first day starts mid-session (20:39, 11:03, 20:09, 06:09,
  16:27, 08:57) → excluded by rule (a). ≤ 1 day per window affected.

## A4. Fix validation (script `cp5_source_validation.py`; artifacts `CP5_source_validation_PRE.md` / `_POST.md`)

- **F1:** A1 state hashes bit-identical PRE→POST on all 6 windows; event counts
  unchanged (226/227/227/225/228/246). NaN synthetic (close rows 0–24 = NaN):
  no crash, rows < 30 all `hold`, identical hash `44fc7284074b9231` PRE→POST.
  ⇒ valid input gives identical output; NaN handled correctly; NO new signals
  from the fix; no look-ahead (guard is past-only); no parameter changed.
- **F4:** A2 hashes unchanged on windows 1/3/5/6; window 2: 2955→2865 event
  bars (−90, 1 event day removed); window 4: 351→331 (−20, 1 event day removed).
  POST: `ineligible_event_days = 0` on all 6 windows against an INDEPENDENT
  re-implementation of the eligibility rule. The change only REMOVED events
  (POST ⊆ PRE); none added.
- Validation fixtures = the frozen Sep-3 control windows used as regression
  fixtures ONLY — they are NOT the CP5 dataset (CP5 data freeze happens at the
  data-freeze gate per §B/D3).

## A5. Source Freeze (binding from the commit containing this amendment)

Tag: `cp5-source-freeze-v1`. From this commit, experiment code is immutable
without a registered amendment. Frozen versions (sha256):

```
strategy_a1_meanrev.py  85c1781a700dde5ed0015fc64841f99a4c0263b6913b9b3afc5a77765e4105a6
strategy_a2_breakout.py 732d1eaad9517e2c4b4bbe1d0fc82a1fc8a0a9c79fd8a8aa9898ab72d279dd5b
research_harness.py     c5e7844a27d9c4a6d08a0221d7a42580e9750cb45f410672589e21f2ddc49216
cp5_source_validation.py 36b12b30b7780db4f93c89cb08130d093e4771991cb9eb0bb6a0df1a04db8c9a
```

Roadmap position after this amendment: Methodology Finalization COMPLETE →
next gate = **Data Freeze + Provenance** (CP5.2), which requires MT5 contact
and explicit user authorization.
