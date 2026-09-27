"""Loads abgal, which has no .py suffix, once as the module every test imports.

Also holds the gate for tests that need real guests. Everything under e2e/
is marked e2e, and e2e or load tests are skipped unless ABGAL_E2E=1 is set,
so a plain pytest on a laptop never touches a real guest.
"""

import importlib.util
import os
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
E2E = Path(__file__).resolve().parent / "e2e"

loader = SourceFileLoader("abgal", str(ROOT / "abgal"))
spec = importlib.util.spec_from_loader("abgal", loader)
abgal = importlib.util.module_from_spec(spec)
sys.modules["abgal"] = abgal
loader.exec_module(abgal)


def pytest_collection_modifyitems(config, items):
    skip = pytest.mark.skip(reason="needs real guests, set ABGAL_E2E=1")
    for item in items:
        if E2E in item.path.parents:
            item.add_marker(pytest.mark.e2e)
        real = item.get_closest_marker("e2e") or item.get_closest_marker("load")
        if real and os.environ.get("ABGAL_E2E") != "1":
            item.add_marker(skip)
