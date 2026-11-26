"""Fake stock clips for tests: the generator lives in eval/scripts (one owner), loaded here."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[4] / "eval" / "scripts" / "make_fake_stock.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_fake_stock", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_fake_stock"] = module
    spec.loader.exec_module(module)
    return module


fake_stock = _load()
