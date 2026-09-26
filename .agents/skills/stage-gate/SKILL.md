---
name: stage-gate
description: Enforce AUDIT → FIX → TEST → VALIDATE → PASS gates and prevent unverified stage progression.
---

# Stage Gate

1. AUDIT — establish the real baseline.
2. FIX — make only justified changes.
3. TEST — execute focused and regression tests.
4. VALIDATE — verify artifacts, contracts, and real outputs.
5. PASS — only with complete evidence.
6. HUMAN CONFIRMATION — stop and wait.
7. NEXT STAGE — only after confirmation.

Required PASS evidence: relevant files inspected, exact changes, tests and counts, validation artifacts, no unresolved blocker, and commit SHA.

If required evidence is missing, status is BLOCKED, not PASS.
