---
name: token-efficient
description: Reduce unnecessary context and output while preserving correctness, verification, and important warnings.
user-invocable: false
---

# Token-efficient work

Use this skill for every software-engineering task when context or response size matters.

## Rules

1. Inspect only the files and sections required for the current decision.
2. Prefer `rg`/`glob` to locate symbols, then read narrow ranges instead of whole files.
3. Batch independent reads and checks in one tool call.
4. Reuse existing helpers and tests; do not rediscover the same code.
5. Keep internal progress and final responses concise.
6. Report only actionable findings, changed files, verification results, and blockers.
7. Never omit security, correctness, compatibility, or test failures merely to save tokens.
8. Do not repeat user-provided context or unchanged code.
9. Use structured summaries and tables when they reduce repetition.
10. Before editing, form a minimal file set; after editing, run the smallest relevant validation.

## Output format

For completed code work, prefer:

- `نتیجه`: one sentence
- `تغییرات`: short bullets with linked files
- `اعتبارسنجی`: commands and pass/fail
- `محدودیت`: only if applicable

Token reduction must never mean skipping implementation, verification, or material risks.
