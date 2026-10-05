"""F-008/F-012 guard: every third-party top-level import used by the core
pipeline modules must be declared in requirements.txt.

Run: PYTHONPATH=. python tests/test_requirements_completeness.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Core modules whose runtime imports must be declared (Stage-7 + training path).
SCANNED_FILES = [
    "stage7/pipeline.py",
    "stage7/config.py",
    "feature_engineering.py",
    "target_generation.py",
    "dataset_pipeline.py",
    "model_training.py",
    "time_series_validation.py",
]

STDLIB = set(sys.stdlib_module_names)

LOCAL_MODULES = {
    "module", "agent", "backtest", "stage7", "scripts",
    "feature_engineering", "target_generation", "dataset_pipeline",
    "model_training", "time_series_validation", "state_io",
    "dashboard", "main", "research_harness", "tests",
}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


# Import name -> PyPI distribution name, where they differ.
ALIASES = {"sklearn": "scikit-learn"}


def _declared_packages() -> set[str]:
    packages = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        packages.add(_normalize(re.split(r"[=<>!;\[]", line)[0]))
    return packages


def _imported_top_levels(rel_path: str) -> set[str]:
    tree = ast.parse((ROOT / rel_path).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def test_requirements_declare_all_third_party_imports():
    declared = _declared_packages()
    missing = sorted(
        name
        for rel in SCANNED_FILES
        for name in _imported_top_levels(rel)
        if name not in STDLIB and name not in LOCAL_MODULES and _normalize(ALIASES.get(name, name)) not in declared
    )
    assert not missing, f"Undeclared third-party imports in requirements.txt: {missing}"


if __name__ == "__main__":
    test_requirements_declare_all_third_party_imports()
    print("OK: requirements.txt covers all third-party imports of scanned modules")
