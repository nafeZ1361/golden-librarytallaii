---
name: stage-7-qwen-orchestrator
description: Orchestrate Stage 7 of the XAUUSD ML / Trading System with GitHub as the source of truth and Qwen as the execution/independent-validation worker. Use for Stage 7.0 through 7.4 audits, minimal fixes, real-data tests, evidence validation, reproducibility, regression, and gated human approval.
---

# Stage 7 Qwen Orchestrator

## Mission

Execute the complete Stage 7 path without rebuilding healthy work.

Roles are deliberately separated:

- **Master/Coordinator:** repository audit, contract design, GitHub changes, dependency management, gate control, evidence review.
- **Qwen:** direct workspace execution, real-data testing, E2E runs, artifact inspection, independent validation.
- **Human:** final approval before every next-stage transition.

Primary workflow:

`AUDIT -> PLAN -> FIX -> TEST(QWEN) -> VALIDATE(QWEN) -> REVIEW -> PASS_PENDING_HUMAN -> HUMAN_CONFIRMATION -> NEXT`

No automatic stage advancement.

## 1. Stage 7 Map

Stage 7 is a gated sequence:

```text
7.0 Baseline / Evidence Registry
        |
        v
7.1 Real-Data ML E2E
        |
        v
7.2 Reproducibility / Repeatability
        |
        v
7.3 Regression / Full Validation
        |
        v
7.4 Final Stage-7 Gate
```

Each sub-stage independently follows:

`AUDIT -> FIX(if needed) -> TEST -> VALIDATE -> REVIEW -> PASS/BLOCKED`

A later sub-stage is forbidden until the current sub-stage is PASS and the human explicitly confirms continuation.

## 2. Current Known State

The existing Stage 7.1 implementation on `stage-7.1-rebuild` is preserved.

Known audit facts must be rechecked before relying on them:

- GitHub `main` currently identified as `ea3ed2461f593664a48da9664746d9d94e22478a`.
- The previously claimed `...478d` SHA is invalid and must never be used as evidence.
- Stage 7.1 real-data harness exists on `stage-7.1-rebuild`.
- Current Stage 7.1 harness/manifest contract expects dataset SHA `0d8857fbe384b9c0abf767e8144c46abfa48be55032599ef7b26407f5ba93493`.
- A Qwen workspace previously reported a local dataset SHA `92a84f92ab4e06625a2d977f5acaeecb6d553ffd1c110b2ed9f1571c541a562a`; this is a provenance discrepancy, not permission to change the expected hash.
- No execution evidence has been accepted as verified until Qwen produces it from the exact evaluated repository/data state.

These are starting hypotheses. Every execution must verify the actual state again.

## 3. WorkGraph

Represent Stage 7 as this dependency graph:

```text
S7-ROOT
  |
  +--> A7.0 Repository/Git Audit
  |
  +--> A7.1 Contract Audit
  |       |
  |       +--> A7.1 Dataset Provenance
  |       +--> A7.1 ML/Leakage Audit
  |       +--> A7.1 Replay/Execution Audit
  |       +--> A7.1 Evidence Contract Audit
  |
  +--> F7.1 Minimal Fix (only if A7.1 proves a defect)
  |
  +--> T7.1 Qwen Focused Tests
  |
  +--> E7.1 Qwen Real-Data E2E
  |
  +--> V7.1 Independent Evidence Validation
  |
  +--> R7.1 Review
  |
  +--> G7.1 PASS/BLOCKED
  |
  +--> [human approval]
  |
  +--> T7.2 Qwen Repeat Run
  +--> V7.2 Hash/Output Reconciliation
  +--> G7.2 PASS/BLOCKED
  |
  +--> [human approval]
  |
  +--> T7.3 Focused + Full Regression
  +--> V7.3 Regression Review
  +--> G7.3 PASS/BLOCKED
  |
  +--> [human approval]
  |
  +--> V7.4 Final Evidence/Provenance/Safety Review
  +--> G7.4 FINAL PASS/BLOCKED
```

Parallel work is allowed only for independent read-only audits. Shared-file modifications must be serialized.

## 4. WorkMachine

Use these states:

```text
S7_INIT
 -> S7_AUDIT
 -> S7_PLANNED
 -> S7_FIXING
 -> S7_TESTING
 -> S7_VALIDATING
 -> S7_REVIEWING
 -> S7_PASS_PENDING_HUMAN
 -> S7_HUMAN_APPROVED
 -> S7_NEXT_SUBSTAGE

Any state -> S7_BLOCKED
S7_BLOCKED -> S7_AUDIT_RETRY
```

Required transition evidence:

- Audit: exact branch, SHA, status, contracts, blockers.
- Fix: exact changed files and reason.
- Test: exact Qwen command, environment, counts.
- Validation: actual artifacts, hashes, chronology, provenance, reconciliation.
- Review: contradictions and unresolved risks.
- Pass: every mandatory criterion VERIFIED.
- Human approval: explicit user instruction.
- Next: only after approval.

## 5. Qwen Execution Protocol

Qwen is the execution authority for tests that require the actual workspace/data.

For every Qwen run require:

1. repository/branch/HEAD verification;
2. clean or explicitly documented working tree;
3. exact dataset path and SHA;
4. exact command;
5. environment/interpreter/dependencies;
6. focused tests before expensive E2E where possible;
7. real-data execution when required;
8. artifact listing;
9. artifact hashes;
10. independent checks of critical metrics and chronology;
11. safety confirmation;
12. final PASS/BLOCKED report.

Qwen must not silently modify the repository during an audit or validation-only task.

If Qwen needs a code fix, it must report the exact defect first. The Master/Coordinator then performs the GitHub change unless an explicitly authorized workflow assigns implementation to Qwen.

A Qwen report is evidence only when the underlying command/output/artifact can be inspected or independently reproduced.

## 6. Stage 7.1 Acceptance Contract

Stage 7.1 cannot PASS until all applicable items are VERIFIED:

### Repository
- exact repository and branch known;
- exact evaluated HEAD SHA recorded;
- no stale/unknown modifications affecting the result.

### Dataset
- exact file path;
- exact SHA-256;
- row count;
- first/last timestamp;
- monotonic timestamps;
- duplicate policy;
- dataset identity matches the code/manifest contract;
- if SHA differs, STOP: do not silently update the expected hash.

### ML
- exact feature count and order;
- target definition/version;
- chronological train/holdout split;
- holdout boundary;
- purge/embargo where required;
- leakage checks;
- decision lag;
- model identity/version;
- deterministic seed/configuration.

### Replay
- signal generation verified;
- signal-to-execution timing verified;
- paper/backtest engine identified;
- no live order path;
- trade ledger reconciles;
- PnL reconciles;
- equity/drawdown reconciles;
- open positions closed/reconciled at end.

### Evidence
Evidence must be produced by the actual run, not reconstructed from filenames.

At minimum record the artifacts the implementation contract actually promises, including where applicable:

- run manifest;
- execution log;
- evidence hash manifest;
- model artifact and metadata;
- final paper state;
- dataset identity;
- metrics and reconciliation data.

If a separate artifact is claimed to be mandatory, first identify its authoritative contract source. Do not invent a requirement merely because an older report listed a filename.

### Reproducibility
- same input/configuration can be rerun;
- critical hashes/outputs are compared;
- nondeterminism is explained or fails the gate.

## 7. Stage 7.2 Reproducibility

Do not change code merely to make two runs look identical.

Qwen must perform a second controlled run using the same immutable input/configuration.

Compare:

- dataset SHA;
- source/code SHA;
- configuration;
- model artifact identity;
- predictions/signals where deterministic;
- trade ledger;
- PnL;
- equity;
- evidence hashes.

Any legitimate nondeterministic field must be explicitly identified and excluded only with documented justification.

Mismatch without an explained cause = BLOCKED.

## 8. Stage 7.3 Regression

Run:

1. Stage-specific focused tests.
2. Related ML/backtest tests.
3. Full repository test suite.

Record exact counts:

`PASS / FAIL / ERROR / SKIP`

A green exit code without count/output evidence is insufficient.

Do not weaken assertions or delete tests to obtain PASS.

Regression must confirm that Stage 7 fixes did not break Phase 6 or previously passed contracts.

## 9. Stage 7.4 Final Gate

Final review must independently verify:

- all Stage 7 sub-stage gates;
- Git provenance;
- dataset provenance;
- evidence hashes;
- reproducibility;
- regression results;
- safety boundary;
- no live trading;
- no unresolved blocker;
- no unsupported PASS claim.

Final state is:

`STAGE7_FINAL = PASS`

only when every mandatory criterion is VERIFIED.

Otherwise:

`STAGE7_FINAL = BLOCKED`

## 10. Minimal-Fix Rule

When a blocker is found:

1. preserve evidence;
2. identify root cause;
3. decide whether it is code/data/environment/evidence/provenance;
4. change the smallest necessary component;
5. add or update a focused regression test;
6. commit the exact change;
7. send the new exact SHA to Qwen;
8. Qwen reruns the relevant validation;
9. re-enter the gate.

Never fix a dataset SHA mismatch by editing the expected SHA until the actual dataset provenance is independently established.

Never rebuild the Stage 7 system because an E2E run failed.

## 11. Safety Boundary

Stage 7 is research/backtest/paper/demo only.

Forbidden:

- real order execution;
- live trading;
- live credentials;
- production broker connections;
- MT5 live order APIs in the ML/research execution path.

A successful Stage 7 backtest does not authorize live trading.

## 12. Evidence Status

Every result must use one of:

- VERIFIED
- PARTIALLY VERIFIED
- UNVERIFIED
- CONTRADICTED
- N/A

A missing artifact is not evidence that the artifact is empty or correct.

A test file is not evidence that the behavior passed.

A previous agent report is not independent validation.

## 13. Timeboxed Iteration

Default maximum: 3 corrective iterations per blocker.

Each iteration must contain:

- hypothesis;
- smallest action;
- resulting evidence;
- review;
- CONTINUE / STOP / BLOCKED.

If three iterations do not resolve the root cause, stop and report BLOCKED rather than making speculative changes.

## 14. GitHub Change Protocol

GitHub is the repository source of truth.

For repository modifications:

- create a dedicated branch;
- inspect existing implementation first;
- make only evidence-backed changes;
- commit with a precise message;
- inspect resulting SHA and changed files;
- do not merge to `main` automatically;
- do not force-push or rewrite history;
- do not use destructive cleanup.

Qwen workspace changes do not become repository truth until synchronized/committed to GitHub and independently inspected.

## 15. Stage Report

Every sub-stage must end with:

```text
STAGE: 7.x
STATUS: PASS | BLOCKED

REPOSITORY:
- branch:
- HEAD SHA:
- working tree:

WORKGRAPH:
- completed:
- blocked:
- pending:

WORKMACHINE:
- state:
- last valid transition:

QWEN EXECUTION:
- command:
- environment:
- result:

TESTS:
- PASS:
- FAIL:
- ERROR:
- SKIP:

EVIDENCE:
- artifacts:
- hashes:
- provenance:
- reproducibility:

FINDINGS:
- VERIFIED:
- PARTIALLY VERIFIED:
- UNVERIFIED:
- CONTRADICTED:

CHANGES:
- files:
- commit SHA:

GATE:
- exact PASS/BLOCKED reason:

NEXT:
- PASS -> STOP and request human confirmation.
- BLOCKED -> identify exact blocker and required evidence.
```

Never claim PASS from a report alone when the underlying evidence is unavailable.
