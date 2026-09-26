---
name: ml-engineering
description: Work on dataset, features, targets, training, inference, artifacts, and model registry while preserving leakage-safe ML contracts.
---

# ML Engineering

- Preserve Phase 6 architecture unless a concrete defect is proven.
- Keep dataset preparation deterministic and MT5-free.
- Preserve feature versions and feature ordering.
- Keep target generation chronological and leakage-safe.
- Training must separate fit data from validation/test data.
- Artifacts must be loadable and accompanied by identity/metadata.
- Registry entries must identify model, target, features, dataset/split identity, and artifact.
- Add focused tests for every contract change.
- Never claim real-data validation when only synthetic tests were executed.
