# CP5.8 — FORENSIC AUDIT: 950 vs 2040 TRADES

Generated: 2026-09-05 | Evidence-based; NO guessing; all searches reproduced below.

## 1. Claim under investigation

Historical claim: two different trade counts, **950** and **2040**, for the
project's strategy runs. Objective: reconcile `2040 → X`, `950 → Y`,
`Difference → ROOT CAUSE` — or document, with evidence, why reconciliation is
impossible.

## 2. Repository-wide search (fresh, this stage)

Command pattern: `grep -rn "950" / "2040" --include=*.py --include=*.md
--include=*.json --include=*.txt --include=*.ipynb --include=*.csv` (workspace,
excluding .git). Results:

- "950": ONLY substring/value coincidences —
  (a) tick_volume=950/1950 rows in frozen CSVs (market data values, not counts);
  (b) substrings inside larger numbers (bar_index 9505/3950/…, gross_loss
  9500.0, winrate 44.26…/PF 1.2099… in cp4b results JSON);
  (c) "indicators.py ~950 خط" mentioned in audit-session notes (a LINE COUNT of
  a file, not a trade count).
- "2040": ONLY tick_volume=2040 rows in determinism_cache/df.csv (market data).
- **NO artifact anywhere contains 950 or 2040 as a trade count.**

This fresh search CONFIRMS the earlier session investigation (memory
2026-09-03): the two numbers are documented NOWHERE in the project — not in
code, reports, logs, notebook outputs (bot.ipynb holds only the 2026-08-10
Hedge-Grid live log), agent-session transcripts, or opencode state.

## 3. Inventory of every DOCUMENTED trade count in the repository

| Source pipeline | Period/scope | Trades | Evidence artifact |
|---|---|---|---|
| Determinism baseline replay (ST+trend_ali, coherent df=) | window 1, ~30 days | **75** | determinism_cache/result.md (75/32/43/42.67/2100/7100) |
| CP2 synthetic engine checks | synthetic scenarios | 1 per scenario | cp2_verification.json |
| CP4 walk-forward OOS folds (11-combo grid, IS-selected) | per ~30d fold | 64–103 | cp4_walkforward_results.md |
| CP4b ATR-exit WFO | per fold | 76–103 | cp4b_atr_results.md |
| CP5.5 A1 (mean-reversion, frozen data) | 6 windows ≈ 9 months | **970** | CP5_PERFORMANCE_RESULTS.json |
| CP5.5 A2 (OR breakout, frozen data) | 6 windows ≈ 9 months | **816** | CP5_PERFORMANCE_RESULTS.json |

## 4. Reconciliation table (per required format)

```text
Source A : claimed "950 trades"
Source B : claimed "2040 trades"
Difference : 1090
Root Cause : NOT REPRODUCIBLE — neither number exists in any repository
             artifact; their origin lies outside the evidence chain (most
             plausibly the pre-coherent-pipeline era or the missing
             "stg peleh.py" strategy generation, but this is inference and is
             explicitly NOT asserted as fact).
Impact on Trades : unknowable without the original source
Impact on PnL : unknowable without the original source
Evidence : §2 search results + §3 inventory (complete)
```

## 5. What CAN be said with evidence (and only this)

1. The coherent, frozen, deterministic pipeline produces these counts: **75
   trades/30 days** (baseline ST+trend_ali) and **970 / 816 trades / ~9 months**
   (A1 / A2). These are the only reproducible anchors in the project.
2. The historical pre-fix pipeline was PROVEN (Phase-1 audit) to produce
   window- and wall-clock-dependent outputs (self-fetch signals + positional
   alignment) — i.e., a mechanism by which two runs of the "same" strategy
   could legitimately disagree on trade counts. This explains the *possibility*
   of divergent historical numbers; it does NOT identify 950/2040 specifically.
3. Neither 950 nor 2040 can be mapped to X or Y: **the claim is unverifiable
   against repository evidence.** Per project law, no number is invented.

## 6. Verdict

- FORENSIC STATUS: **COMPLETE — DISCREPANCY UNVERIFIABLE (sources absent)**
- The "950 vs 2040" discrepancy CANNOT be reconciled from the repository; the
  project's reproducible record is the §3 inventory.
- CONDITION for full closure: if the user can provide the origin of 950/2040
  (file, log, screenshot, or the environment that produced them), a targeted
  reconciliation run can be executed. Until then this stage's finding stands.

## 7. Required user input (optional, only for full numeric closure)

- Any artifact/screenshot/log showing where 950 and 2040 were produced.
