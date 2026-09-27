---
name: stage-executor
description: Execute a project stage end-to-end on the repository: audit, minimal fix, tests, validation, evidence, and stop at the human gate.
---

# Stage Executor

Use this skill for every project stage.

1. Read AGENTS.md and the stage-specific skills.
2. Inspect the actual GitHub repository and current branch before changing anything.
3. Establish a reproducible baseline.
4. Implement the smallest justified fix; never rebuild a working subsystem.
5. Add focused regression tests for changed behavior.
6. Run available automated tests. If a required environment is unavailable, report BLOCKED rather than fabricating PASS.
7. Validate artifacts, hashes, chronology, leakage boundaries, and interfaces.
8. Review the diff for unrelated changes.
9. Produce a stage evidence report with exact commit SHA and test results.
10. Stop at PASS/BLOCKED. Do not silently start the next stage.
11. Human confirmation is required before NEXT STAGE.
12. GitHub is the source of truth for repository state; do not treat an agent sandbox as the repository unless it is explicitly synchronized.
