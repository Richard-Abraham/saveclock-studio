"""Live tests talk to real services: the outbound-connection guard is off here, and a live file
whose key is not set is not collected at all (the run says so plainly)."""

import os
from pathlib import Path

import pytest

KEYS = {"test_pexels_smoke.py": "PEXELS_API_KEY"}


@pytest.fixture(autouse=True)
def _no_outbound_connections() -> None:
    """Overrides the guard of tests/conftest.py: these tests are meant to reach the internet."""


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    variable = KEYS.get(collection_path.name)
    if variable is not None and not os.environ.get(variable):
        print(f"SKIPPED (no {variable})")
        return True
    return None
