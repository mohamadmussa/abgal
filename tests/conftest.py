"""Loads abgal, which has no .py suffix, once as the module every test imports."""

import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

loader = SourceFileLoader("abgal", str(ROOT / "abgal"))
spec = importlib.util.spec_from_loader("abgal", loader)
abgal = importlib.util.module_from_spec(spec)
sys.modules["abgal"] = abgal
loader.exec_module(abgal)
