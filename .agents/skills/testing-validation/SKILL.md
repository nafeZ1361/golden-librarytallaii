---
name: testing-validation
description: Execute and interpret tests for the trading system and produce evidence-based PASS/BLOCKED decisions.
---

# Testing and Validation

- Run the narrowest relevant tests first, then the full suite when practical.
- Report exact command, environment, test count, failures, and duration when available.
- Add regression tests for every bug fix.
- Distinguish synthetic-data tests from real-data integration tests.
- A green unit suite does not prove real-data compatibility by itself.
- Verify artifacts and outputs, not only exit codes.
- Do not suppress failures or weaken assertions to obtain PASS.
