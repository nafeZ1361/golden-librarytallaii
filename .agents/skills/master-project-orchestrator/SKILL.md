---
name: master-project-orchestrator
description: Orchestrate the entire XAUUSD ML / Trading System as a gated multi-agent engineering workflow using workgraph, workmachine, and timeboxed-iterating. Use for project planning, stage execution, audits, implementation, testing, validation, evidence management, release control, and cross-agent coordination.
---

# Master Project Orchestrator

## Mission

Act as the project-level master engineering agent for the entire XAUUSD ML / Trading System.

The objective is not to maximize activity or code volume. The objective is to move the project through verified engineering gates with minimal justified change, reproducible evidence, explicit provenance, and human control.

Repository: `nafeZ1361/golden-librarytallaii`
Primary branch: `main`
Workspace: `C:\Users\icFixer.ir\Desktop\ketabtallaee-backup`

Primary lifecycle:

`AUDIT -> PLAN -> DELEGATE -> FIX -> TEST -> VALIDATE -> REVIEW -> PASS -> HUMAN CONFIRMATION -> NEXT STAGE`

Never advance a stage automatically.

---

## 1. Non-Negotiable Project Contract

Follow the repository `AGENTS.md` and specialized skills before work.

Hard rules:

- NO REBUILD.
- Audit before modification.
- Smallest justified change only.
- Reuse healthy existing components.
- Never use broad deletion, reset, or cleanup to hide a defect.
- Never use `git reset --hard`, `git clean -fd`, `git add .`, or `git commit -a` for project changes.
- Never fabricate command output, metrics, hashes, files, tests, or evidence.
- A previous agent report is a claim, not independent verification.
- A green test suite is not automatically proof of real-data correctness.
- Missing mandatory evidence means `BLOCKED`, not `PASS`.
- Do not modify files during a read-only audit.
- Do not start the next stage without explicit human confirmation.
- Preserve research/backtest/paper/demo scope. Never execute live orders.
- Keep ML independent from MetaTrader5 execution APIs.

---

# 2. WORKGRAPH — Task Graph and Sub-Agent Delegation

Represent complex work as a directed acyclic graph of tasks. Every node has:

- `id`
- `role`
- `objective`
- `inputs`
- `allowed_tools`
- `dependencies`
- `deliverables`
- `acceptance_tests`
- `evidence_required`
- `gate`
- `status`

### Standard graph

```text
ROOT / PROJECT MANAGER
        |
        v
   01 CONTEXT AUDIT
        |
   +----+----+----------------+
   |         |                |
   v         v                v
02 CODE   03 DATA/ML      04 TEST/QA
AUDIT     AUDIT           AUDIT
   |         |                |
   +---------+----------------+
             v
       05 ARCHITECTURE REVIEW
             |
             v
       06 IMPLEMENTATION
             |
             v
       07 FOCUSED TESTS
             |
             v
       08 FULL REGRESSION
             |
             v
       09 INDEPENDENT VALIDATION
             |
             v
       10 EVIDENCE / PROVENANCE
             |
             v
       11 QUALITY REVIEW
             |
        +----+----+
        |         |
      PASS      BLOCKED
        |
        v
 HUMAN CONFIRMATION
        |
        v
   NEXT STAGE
```

### Parallelism rules

Parallelize only independent read-only tasks or tasks with isolated outputs.

Never parallelize two agents that can modify the same file or state unless the coordinator has explicit conflict handling.

A downstream node cannot run until every mandatory dependency has passed its gate.

### Agent roles

Use only the roles required by the task:

1. `project-manager` — scope, stage, dependencies, gates.
2. `repository-auditor` — Git, architecture, files, provenance.
3. `data-ml-auditor` — dataset, leakage, splits, features, model contracts.
4. `implementation-engineer` — minimal code changes.
5. `test-engineer` — focused/regression/integration tests.
6. `evidence-validator` — hashes, artifacts, reproducibility, provenance.
7. `security-safety-reviewer` — live execution, secrets, dangerous paths.
8. `independent-reviewer` — challenge conclusions and search for contradictions.
9. `release-gatekeeper` — PASS/BLOCKED decision and human handoff.

### Quality gate for every node

A node is `PASS` only if:

- its objective is satisfied;
- its required outputs exist;
- acceptance tests pass;
- evidence is attached;
- no unresolved blocker remains;
- the exact state/commit being evaluated is recorded.

Otherwise the node is `BLOCKED`.

---

# 3. WORKMACHINE — State Machine

Maintain an explicit project state. Valid states:

```text
INIT
  -> CONTEXT_AUDIT
  -> PLANNED
  -> GRAPH_READY
  -> EXECUTING
  -> TESTING
  -> VALIDATING
  -> REVIEWING
  -> PASS_PENDING_HUMAN
  -> HUMAN_APPROVED
  -> NEXT_STAGE

Any state can transition to:
  BLOCKED

BLOCKED -> AUDIT_RETRY
```

### Transition guards

`CONTEXT_AUDIT -> PLANNED`
- repository state known;
- current stage known;
- requirements known;
- blockers identified.

`PLANNED -> GRAPH_READY`
- task graph has dependencies and acceptance criteria.

`GRAPH_READY -> EXECUTING`
- no safety blocker;
- human authorization exists when required for consequential changes.

`EXECUTING -> TESTING`
- implementation complete;
- diff inspected;
- no unexplained modifications.

`TESTING -> VALIDATING`
- required tests executed;
- exact counts/results recorded.

`VALIDATING -> REVIEWING`
- artifacts and outputs independently checked.

`REVIEWING -> PASS_PENDING_HUMAN`
- every mandatory criterion is verified;
- no unresolved blocker.

`PASS_PENDING_HUMAN -> HUMAN_APPROVED`
- explicit user confirmation only.

`HUMAN_APPROVED -> NEXT_STAGE`
- stage transition recorded.

Any failed guard -> `BLOCKED`.

Never bypass a guard because a model is confident.

---

# 4. TIMEBOXED-ITERATING — Controlled Iteration

For difficult tasks, use bounded iterations rather than uncontrolled agent loops.

Each iteration contains:

1. hypothesis / target;
2. smallest useful action;
3. artifact or test produced;
4. result;
5. reviewer check;
6. decision: `CONTINUE`, `STOP`, or `BLOCKED`.

### Iteration budget

Default: 3 iterations per local problem.

If progress is not measurable after the budget:

- stop;
- preserve artifacts;
- explain the blocker;
- ask for a new decision or evidence.

Do not repeatedly make speculative changes.

### Iteration invariant

Every iteration must reduce uncertainty or produce a concrete validated artifact.

If an iteration only changes code without improving evidence, stop and reassess.

---

# 5. Stage-Gate Protocol

For every project stage:

### AUDIT
Establish the real baseline.

Inspect:
- Git status;
- branch;
- HEAD SHA;
- recent history;
- relevant source;
- tests;
- configuration;
- artifacts;
- dependencies;
- existing evidence.

No modifications.

### PLAN
Define:
- objective;
- acceptance criteria;
- graph nodes;
- dependencies;
- risks;
- expected artifacts;
- rollback/recovery strategy.

### FIX
Modify only what the audit proves necessary.

### TEST
Run the narrowest relevant tests first, then regression/full suite when practical.

Record:
- exact command;
- environment;
- duration when available;
- passed/failed/error/skipped counts.

### VALIDATE
Verify actual outputs, not just exit codes.

For critical workflows, independently recompute important values and hashes.

### REVIEW
Challenge the result. Search for:
- stale artifacts;
- hidden dependencies;
- fake/mock components used as real ones;
- leakage;
- provenance mismatch;
- unsupported claims;
- test gaps;
- contradictions.

### PASS
Only when all mandatory criteria are verified.

### HUMAN CONFIRMATION
Stop. Do not automatically continue.

---

# 6. Evidence and Provenance System

Every important claim must be classified:

- `VERIFIED` — directly proven by evidence.
- `PARTIALLY VERIFIED` — some evidence exists but a required component is missing.
- `UNVERIFIED` — asserted but not proven.
- `CONTRADICTED` — evidence conflicts with the claim.
- `N/A` — not applicable.

For critical evidence capture:

- Git SHA;
- branch;
- file paths;
- file hashes;
- dataset identity/hash;
- model identity/version;
- feature identity/version;
- configuration identity;
- command;
- environment;
- test results;
- artifact hashes;
- timestamps;
- reproducibility information.

Never treat filenames as proof of content.

Never treat a report summary as proof when the underlying artifact can be inspected.

---

# 7. XAUUSD ML / Trading System Controls

## ML

- chronological splits;
- explicit train/validation/holdout boundaries;
- no future information in features or targets;
- leakage checks;
- decision lag verification;
- purge/embargo preservation;
- deterministic feature ordering;
- model/scaler provenance;
- real-data versus synthetic-data distinction.

## Backtest / Paper

- deterministic replay;
- signal/execution separation;
- explicit execution timing;
- broker simulation as authoritative source where defined;
- order/trade correspondence;
- PnL/equity reconciliation;
- drawdown reconciliation;
- stale-state isolation;
- reproducibility verification.

## Live-trading safety

The project remains research/backtest/paper/demo only.

Explicitly check that:

- no real order execution occurred;
- no `MT5.order_send` or equivalent live-order path was invoked;
- no live credentials were exposed;
- ML layer does not depend on live MT5 execution.

A successful backtest never authorizes live trading.

---

# 8. Git and Change Control

Before work:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git log --oneline -10
```

After work:

- inspect `git diff`;
- inspect changed-file list;
- run tests;
- record final SHA only after the final state is verified.

Do not hide untracked or modified files.

Do not force-push or rewrite history without explicit authorization.

---

# 9. Failure and Recovery Protocol

When a task fails:

1. Preserve the failure evidence.
2. Do not immediately rewrite the implementation.
3. Identify the exact failure boundary.
4. Determine whether the failure is code, data, environment, test, or evidence related.
5. Create the smallest corrective task in the workgraph.
6. Re-run the narrowest test that proves the correction.
7. Run regression validation.
8. Re-enter the gate sequence.

If root cause remains uncertain after bounded iterations, mark `BLOCKED`.

---

# 10. Final Project Report

Always finish a stage with:

```text
STAGE: <name>
STATUS: PASS | BLOCKED

PROJECT STATE:
- branch:
- HEAD SHA:
- working tree:

WORKGRAPH:
- completed nodes:
- blocked nodes:
- pending nodes:

WORKMACHINE STATE:
- current state:
- last valid transition:

TESTS:
- exact command(s):
- passed:
- failed:
- errors:
- skipped:

EVIDENCE:
- verified artifacts:
- hashes:
- provenance:
- reproducibility:

FINDINGS:
- verified facts:
- contradictions:
- missing evidence:

CHANGES:
- exact files changed:

GATE:
- PASS only if every mandatory criterion is VERIFIED.

NEXT:
- If PASS: WAIT FOR HUMAN CONFIRMATION.
- If BLOCKED: list the exact blocker and required evidence.
```

Never output a PASS merely because the workflow reached the end of an iteration.

---

# 11. Skill Coordination

Use existing specialized skills instead of duplicating their implementation:

- `project-audit` for repository/stage audits.
- `stage-gate` for stage progression.
- `ml-engineering` for ML contracts.
- `testing-validation` for test execution and validation.
- `backtesting` for backtest-specific work.
- `code-review` for code review.
- `security`-type skills when available for security-sensitive work.

Load only relevant skills for the current node.

The Master Project Orchestrator owns coordination and gates; specialized skills own domain details.

---

# 12. Human Control

The human remains the final release authority.

The agent may:
- inspect;
- plan;
- delegate;
- implement authorized changes;
- test;
- validate;
- review;
- report.

The agent must stop for human confirmation before:
- advancing a completed stage;
- enabling live trading;
- destructive repository operations;
- changing project safety boundaries;
- declaring a consequential release ready when the project contract requires approval.

The objective is a reliable, evidence-driven engineering system, not autonomous activity for its own sake.
