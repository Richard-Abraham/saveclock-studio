"""Convention guards: introspection of our own code, because these protect a rule, not behaviour."""

import importlib
import inspect
import pkgutil
from collections.abc import Iterator

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

import saveclock.api.v1 as v1_pkg
import saveclock.repositories as repositories_pkg
from saveclock.api.deps import current_user
from saveclock.main import API_PREFIX
from saveclock.models import ProjectStatus
from saveclock.services.projects import UiStatus, ui_status
from tests.conftest import make_app


def repository_methods() -> Iterator[tuple[str, str, inspect.Signature]]:
    for mod_info in pkgutil.iter_modules(repositories_pkg.__path__):
        module = __import__(f"saveclock.repositories.{mod_info.name}", fromlist=["x"])
        for cls_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            for name, fn in inspect.getmembers(cls, inspect.isfunction):
                if not name.startswith("_"):
                    yield cls_name, name, inspect.signature(fn)


@pytest.mark.unit
def test_every_repository_method_takes_user_id() -> None:
    seen = list(repository_methods())
    assert seen, "no repository methods found: the introspection is broken"
    missing = [f"{c}.{m}" for c, m, sig in seen if "user_id" not in sig.parameters]
    assert missing == []  # the documented exception list is empty


def _depends_on_current_user(dependant: Dependant) -> bool:
    return dependant.call is current_user or any(
        _depends_on_current_user(d) for d in dependant.dependencies
    )


def v1_routes() -> Iterator[APIRoute]:
    """Every route of every router module in saveclock.api.v1 (FastAPI hides its own tree)."""
    for mod_info in pkgutil.iter_modules(v1_pkg.__path__):
        module = importlib.import_module(f"saveclock.api.v1.{mod_info.name}")
        router = getattr(module, "router", None)
        if router is not None:
            yield from (r for r in router.routes if isinstance(r, APIRoute))


@pytest.mark.unit
def test_unauthenticated_route_inventory() -> None:
    open_routes = {
        f"{m} {API_PREFIX}{r.path}"
        for r in v1_routes()
        if not _depends_on_current_user(r.dependant)
        for m in (r.methods or set())
    }
    assert open_routes == {"GET /api/v1/health/live", "GET /api/v1/health/ready"}


@pytest.mark.unit
def test_inventory_walks_every_route_the_app_serves() -> None:
    walked = {f"{API_PREFIX}{r.path}" for r in v1_routes()}
    assert walked == set(make_app(checks={}).openapi()["paths"])


# ARCHITECTURE §4, written by hand.
UI_TABLE = {
    "created": "uploading",
    "uploading": "uploading",
    "validating": "analysing",
    "analyzing": "analysing",
    "planning": "analysing",
    "draft_ready": "draft",
    "rendering": "rendering",
    "ready": "ready",
    "failed_analysis": "failed",
    "failed_plan": "failed",
    "failed_render": "failed",
    "rejected": "failed",
    "canceled": "canceled",
}


@pytest.mark.unit
def test_ui_status_mapping_covers_all_states_except_deleted() -> None:
    assert {s.value for s in ProjectStatus} == set(UI_TABLE) | {"deleted"}
    for status, expected in UI_TABLE.items():
        assert ui_status(status) is UiStatus(expected)
    with pytest.raises(KeyError):
        ui_status("deleted")
