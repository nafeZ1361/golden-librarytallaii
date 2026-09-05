# RESEARCH CONTRACT TEMPLATE (R2) — fill ONE per experiment, BEFORE any run

```markdown
# RESEARCH CONTRACT — <EXPERIMENT_ID>

Date registered: <YYYY-MM-DD> | Variant: <N of max 10> | Parent diagnosis: <file>

## Hypothesis (falsifiable)
IF <condition on observable data up to bar i>, THEN <predicted direction/event>
in MORE THAN 50% of events for horizon(s) <h>, with dependence+Bonferroni-
corrected 95% CI lower bounds above 50% on BOTH <IS dataset> AND <OOS dataset>.

## Economic rationale
<WHY should this edge exist? who is on the other side? why does it persist?>

## Regime assumption
<under what market condition is this hypothesis expected to hold?>

## Specification (frozen at registration)
- Instrument: XAUUSD. | Timeframe: M3 | Candles: plain
- Features: <exact indicators/inputs — no future data>
- Entry rule: <exact>
- Exit rule: <exact>
- Risk rule: <= HARD_RISK_CAP_PERCENT (2.0) per trade; SL/TP geometry <exact>
- Parameters: <exact values — NO grid>

## Data & periods
- IS dataset: <registry ID + identity hash>
- OOS dataset: <registry ID + identity hash> (unseen reserve, consumed ONCE)

## Costs
C0=0 | C1=3.5 pips | C2=6.0 pips (per trade, $1/pip at 0.1 lot)

## Statistical tests (registered constants)
Wald95 + HAC(L=h) + MBB(N=10000, seed=55056, block=h); Bonferroni over the
registered cell family; family size fixed HERE: m=<m>

## Acceptance criteria (ALL required)
1. Corrected LBs (HAC-Bonf AND MBB-Bonf) > 50% on IS, same horizon(s).
2. Same on OOS (one-shot).
3. OOS gross expectancy > 0 AND survives C1.
4. >= 3/6 windows positive; no single-window dominance > 50%.
5. Determinism PASS; provenance CONFIRMED CLEAN; no leakage finding.

## Rejection criteria (ANY one)
Any corrected LB <= 50% on IS or OOS | OOS gross expectancy <= 0 |
determinism/leakage finding | family size changed post-hoc.

## Complexity budget
MAX_FEATURES=<n> | MAX_PARAMETERS=<n> | MAX_SEARCH_SPACE=<0 grids allowed> |
MAX_TECHNICAL_REPAIR_LOOPS=5 | this is variant <k> of max 10
```

Rules: the contract is COMMITTED before the first result exists; the OOS
dataset is consumed exactly once; no field may be edited after results are
seen (a change = new contract + new experiment ID + new OOS).
