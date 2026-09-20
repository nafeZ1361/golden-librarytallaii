# RESEARCH INFRASTRUCTURE GUIDE (R5) — the standard experiment pipeline

This is the operating manual for every future hypothesis. Reuse these exact
steps; deviating requires a registered amendment.

## The 12-step pipeline (per experiment)

1. **CONTRACT** — fill `RESEARCH_CONTRACT_TEMPLATE.md` (hypothesis, rationale,
   frozen parameters, datasets, family size m, acceptance/rejection criteria);
   commit BEFORE any run. Fill an OOS definition from an UNSEEN reserve
   (DATA_REGISTRY consumption ledger).
2. **FREEZE OOS** — adapt `cp5_9_oos_freeze.py` (TZ-corrected bounds +3:30!),
   integrity battery, manifest, identity hash. Abort on any anomaly.
3. **IMPLEMENT** — new strategy file (never modify frozen sources); pure
   `signal_fn(wdf) -> states`; no MT5 access; deterministic.
4. **STATIC AUDIT** — provenance trace (data-ingress lines), forbidden-token
   scan, two-sided purity test (pattern: `cp5_provenance_check.py`).
5. **DETERMINISM** — Execution A vs B byte-identical on every window +
   3-phase isolation (pattern: `cp5_determinism_audit.py`). FAIL = STOP.
6. **IS EVALUATION** — one-shot: hit-rate per registered family cells + Wald +
   HAC(L=h) + MBB(seed=55056, N=10000, block=h) + Bonferroni(m = family size
   fixed in the contract). Integrity gate: counts must reconcile.
7. **GATE IS** — CANDIDATE iff HAC-Bonf LB > 50% AND MBB-Bonf LB > 50%.
   Failure → RETIRED (record; OOS NOT consumed for this hypothesis family...
   unless the contract pre-declared IS-failure OOS consumption).
8. **ROBUSTNESS** — pre-registered perturbation grid (anchor-gated
   reimplementations; pattern: `cp5_7_robustness.py`). ROBUST/MIXED/FRAGILE.
9. **OOS ONE-SHOT** — same constants, fresh unseen dataset, no tuning.
   PASSED → REPLICATED; failed → RETIRED (period burned per DATA_REGISTRY).
10. **ECONOMICS** — C0/C1/C2 + break-even on BOTH datasets; per-trade cost
    ledger required before any DEMO claim.
11. **RISK** — drawdown/streak/clustering profile; uncompensated risk = no.
12. **LEDGER + REGISTRY update** — append experiment + hypothesis status;
    commit everything atomically.

## Registered statistical constants (never changed post-results)

`SEED=55056 | N_BOOT=10000 | BLOCK_LEN=h | NW_LAG=h | Wald z=1.959963984540054 |
Bonferroni z(m) | family size fixed in the contract`

## Standing rules

- TZ rule: MT5 date bounds = broker_naive + 3:30 (CP6 v2 lesson).
- No grid/optimizer in the registered pipeline (D1 deviation is the standard).
- HARD_RISK_CAP_PERCENT=2.0 binds sizing.
- Artifacts: append-only; superseded versions preserved with suffix.
- Failure taxonomy: use §29 labels in every retirement record.
