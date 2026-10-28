"""Regression coverage for F-005 lazy singleton compatibility exports."""
import subprocess
import sys
from pathlib import Path


def test_legacy_singleton_exports_remain_lazy_and_importable():
    repo_root = Path(__file__).resolve().parents[1]
    probe = """
import module.mt5 as mt5_module

assert isinstance(mt5_module.paper_broker, mt5_module._LazySingletonProxy)
assert isinstance(mt5_module.execution_engine, mt5_module._LazySingletonProxy)
assert mt5_module._paper_broker is None
assert mt5_module._execution_engine is None

namespace = {}
exec("from module.mt5 import *", namespace)
assert "paper_broker" in namespace
assert "execution_engine" in namespace
assert mt5_module._paper_broker is None
assert mt5_module._execution_engine is None
"""
    subprocess.run(
        [sys.executable, "-c", probe],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
