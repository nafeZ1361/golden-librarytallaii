---
name: time-series-validation
description: Design and verify chronological splits, purge, embargo, holdout, OOS, and look-ahead protection for financial time series.
---

# Time-Series Validation

- Never shuffle chronological financial data unless explicitly required by a documented contract.
- Verify train < validation < test chronology.
- Preserve horizon-aware purge and embargo.
- Holdout boundaries must be explicit, immutable, and reproducible.
- Never invent HOLDOUT_START_DATE.
- Verify timestamps, timezone semantics, dataset hash, and split identity.
- Test that no training row crosses the holdout boundary.
- Test that features available at decision time do not include future bars.
- Report exact boundary evidence.
