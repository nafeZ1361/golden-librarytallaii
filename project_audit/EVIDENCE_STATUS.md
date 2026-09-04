# EVIDENCE STATUS — Golden Library Research Project

Purpose: provenance and audit record only. This file preserves the audited
status of research evidence as of the Evidence Preservation step.
It produces NO new results and runs NO experiments.

Recorded: 2026-09-04

---

## 1. Repository State at Evidence Preservation (2026-09-04)

- Branch: `code-refactoring-guide-41a87`
- HEAD: `6f0cab5fcdb24378f71d077149f8ee62bd745610` (`6f0cab5`, CP4d commit)
- Upstream: `origin/code-refactoring-guide-41a87` — local equal to upstream
- Working tree: tracked files CLEAN (no modifications, no deletions)
- Staged files: NONE at the start of this phase
- Untracked scientific evidence existed on disk at audit time
  (CP4b/CP4c scripts + results, CP2/CP3 narrative reports,
  research harness, strategies A1/A2, CP4e script)

---

## 2. Experiment Evidence Status

### CP4 — Walk-Forward (coherent df= pipeline)

Evidence preserved. Script + results committed at `a7944c8`.
- 5 folds; IS-only parameter selection (11-combo grid, min 10 IS trades)
- OOS: 2/5 profitable folds
- Average OOS ROI: -3.60%
- Expected value: -$4.12 per trade
- Verdict: NO PROVEN EDGE.

### CP4b — ATR Exits (SL=2×ATR14, TP=3×ATR14)

Evidence preserved on disk (script + results; uncommitted at recording time).
- Same coherent pipeline, same 5 folds, same IS-only selection;
  only exit geometry changed; harness equivalence (fixed mode): True
- OOS: 2/5 profitable folds
- Average OOS ROI: -7.78%
- Expected value: -$5.26 per trade
- The result file's own closing line, recorded verbatim:
  `BRANCH VERDICT: EXIT-GEOMETRY WAS THE PROBLEM -> rerun CP4 with ATR exits + fuller grid`
- This line is recorded AS EVIDENCE of what the file states. It must NOT be
  generalized beyond what the result file itself establishes.

### CP4c — Directional Hit-Rate (M3)

Evidence preserved on disk (script + results; uncommitted at recording time).
- No positive directional edge.
- Every aggregate's Wald95 CI includes or lies below 50%.
- supertrend_h5 = 47.33%, Wald95 CI [44.81%, 49.84%].
- This CI lies entirely below 50% and therefore:
  evidence AGAINST direction, not merely indeterminate.

### CP4d — Timeframe Hit-Rate (M15 / H1)

Evidence preserved. Script + results committed at `6f0cab5`.
- No positive directional edge established.
- No Wald95 CI above 50% was reported for any M15/H1 cell.

### CP4e — A1/A2 Hit-Rate

```
CP4e:
attempted 2026-09-04;
result evidence not preserved;
no scientific conclusion may be attributed to CP4e.
```

- `cp4e_a1a2_hitrate.py` exists on disk
  (4,324 bytes; LastWriteTime 2026-09-04 13:13:42 +0330).
- Result artifacts (`cp4e_a1a2_hitrate.json`, `cp4e_a1a2_hitrate.md`)
  do NOT exist — checked in the project root AND in
  `project_audit/stability_windows_cache/`.
- Import evidence for `strategy_a1_meanrev` / `research_harness`
  (`__pycache__` .pyc artifacts, 16:55 / 16:56) is recorded as an
  INFERRED attempt only: cp4e is the only repo file importing both,
  but an interactive import cannot be excluded.
- The cause of failure/termination is UNKNOWN and must not be guessed.
- CP4e must NOT be used in the baseline as an experiment WITH a result.

---

## 3. Edge Status

CURRENT CONTROL/BASELINE CONCLUSION:

NO PROVEN EDGE.

No claim of a positive edge is recorded from CP4 through CP4e.

---

## 4. CP4c Precision Note (verbatim)

```
No positive directional edge:
every aggregate's Wald95 CI includes or lies below 50%.

supertrend_h5 CI [44.81%, 49.84%] excludes 50% on the downside —
evidence AGAINST direction, not merely indeterminate.
```

---

## 5. Purpose of Evidence Preservation

This file exists to preserve provenance and to prevent future misquotation.
It produces no new results and runs no experiments.
Evidence preservation ≠ any claim about strategy performance.

---

## 6. CP5 — Strategies A1 / A2

- `strategy_a1_meanrev.py` and `strategy_a2_breakout.py` are, at recording
  time, research artifacts ONLY.
- The question of whether A1/A2 have an edge must be examined in a NEW,
  PRE-REGISTERED experiment (hypothesis, metric, horizon, pass/fail
  thresholds, and minimum sample size specified BEFORE any run).
- No CP4e result is carried into CP5 — none exists to carry.

---

## 7. Baseline Lock

BASELINE LOCK NOT YET PERFORMED.

EVIDENCE PRESERVATION ≠ BASELINE LOCK.

> ADDENDUM 2026-09-04 (post-lock): Baseline Lock has now been performed —
> see `BASELINE_LOCK.md` and tag `baseline-lock-v1`. The statement above was
> true at recording time and is superseded by the lock. The distinction
> EVIDENCE PRESERVATION ≠ BASELINE LOCK remains valid.

---

Audit trail of this record: read-only inspection only. No source code was
changed, no backtest/optimization/CP4e was run, no MT5 or broker contact
occurred, and no git add/commit/push was performed to create this file.
