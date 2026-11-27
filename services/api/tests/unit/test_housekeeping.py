"""Pieces of the housekeeping wiring that need no database (the sweeper itself is exercised in
tests/integration/test_housekeeping.py and test_maintenance_worker.py)."""

from pathlib import Path

import pytest

from saveclock.workers.maintenance import WHAT
from tests.unit.test_registry import registered


@pytest.mark.unit
def test_the_reap_targets_are_the_documented_ones() -> None:
    assert {"uploads", "stuck_jobs", "orphans"} == WHAT


@pytest.mark.unit
def test_an_unknown_reap_target_is_refused_before_any_io(tmp_path: Path) -> None:
    actor = registered(tmp_path).actors["reap_orphans"]
    with pytest.raises(ValueError, match="unknown reap target"):
        actor.fn("00000000-0000-4000-8000-000000000001", "everything")


@pytest.mark.unit
def test_the_maintenance_actors_take_the_user_first_and_ids_or_literals_only(
    tmp_path: Path,
) -> None:
    broker = registered(tmp_path)
    expected = {
        "sweep_intermediates": ["user_id", "project_id"],
        "reap_orphans": ["user_id", "what"],
        "purge_project": ["user_id", "project_id"],
        "prune_jobs": ["user_id"],
    }
    for name, params in expected.items():
        code = broker.actors[name].fn.__code__
        assert list(code.co_varnames[: code.co_argcount]) == params
