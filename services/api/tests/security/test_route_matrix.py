"""The route matrix (plan 008, T-2.14 and the Host/Origin half of T-2.18).

The routes are enumerated from `v1_routes()`, never listed twice: a path parameter other than
`project_id` or `render_id` fails the test ("add a fixture for it"), so a future route with a new
id cannot be forgotten. A second user must get 404 from every route that names the owner's
project or render, and a foreign Host, a cross-site Origin or `Sec-Fetch-Site: cross-site` is 403
everywhere.
"""

import inspect
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from fastapi.routing import APIRoute
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import saveclock.repositories as repositories_pkg
from saveclock.api.deps import current_user
from saveclock.models import ModeAState
from saveclock.services.identity import OWNER_USER_ID, CurrentUser
from tests.integration.conftest import ApiEnv, insert_user
from tests.integration.housekeeping_harness import Hk
from tests.unit.test_conventions import v1_routes

pytestmark = [pytest.mark.security, pytest.mark.integration]
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")
ID_PARAMS = {"project_id", "render_id"}
STATE_CHANGING = {"POST", "PUT", "PATCH", "DELETE"}
SONG = b"RIFF" + bytes(40)
# minimal valid bodies for the routes that need one, keyed by operation_id
BODIES: dict[str, Any] = {
    "patch_project": {"title": "x"},
    "patch_plan": {"base_version": 1, "ops": [{"op": "lock_clip", "cut_index": 0, "locked": True}]},
    "create_project": {},
    "put_settings": {"pixabay_enabled": False},
    "run_housekeeping": {"scope": "intermediates"},
    "create_render": {},
}
QUERIES: dict[str, dict[str, str]] = {"download_render": {"kind": "silent_video"}}
HEADERS: dict[str, dict[str, str]] = {
    "upload_song": {"content-type": "audio/wav", "x-filename": "a.wav", "content-length": "44"}
}


def fill(route: APIRoute, ids: dict[str, str]) -> str:
    unknown = {p.name for p in route.dependant.path_params} - set(ids)
    assert not unknown, f"{route.operation_id}: add a fixture for the path parameter(s) {unknown}"
    return re.sub(r"\{(\w+)(:\w+)?\}", lambda m: ids[m.group(1)], "/api/v1" + route.path)


def methods(route: APIRoute) -> list[str]:
    return sorted((route.methods or set()) - {"HEAD", "OPTIONS"})


def call_args(route: APIRoute, method: str) -> dict[str, Any]:
    op = route.operation_id or ""
    args: dict[str, Any] = {"params": QUERIES.get(op, {}), "headers": dict(HEADERS.get(op, {}))}
    if op == "upload_song":
        args["content"] = SONG
    elif method in {"POST", "PUT", "PATCH"} and op in BODIES:
        args["json"] = BODIES[op]
    return args


@pytest.fixture
async def world(hk: Hk, api: ApiEnv) -> dict[str, str]:
    """The owner's project and render, and a second user."""
    pid = await hk.project(status="ready")
    rid = await hk.render(pid, await hk.plan(pid), mode_a=True)
    await insert_user(api.db, OTHER, "b@example.test")
    assert api.app is not None
    return {"project_id": str(pid), "render_id": str(rid)}


async def test_a_second_user_gets_404_from_every_route_that_names_the_owners_ids(
    hk: Hk, api: ApiEnv, world: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert api.app is not None
    api.app.dependency_overrides[current_user] = lambda: CurrentUser(OTHER, "other")
    checked: list[str] = []
    unprocessable: list[str] = []
    try:
        for route in v1_routes():
            names = {p.name for p in route.dependant.path_params}
            assert names <= ID_PARAMS, (
                f"{route.operation_id}: add a fixture for {names - ID_PARAMS}"
            )
            if not names:
                continue
            url = fill(route, world)
            for method in methods(route):
                response = await api.client.request(method, url, **call_args(route, method))
                checked.append(f"{method} {route.path}")
                if response.status_code == 422:
                    unprocessable.append(f"{route.operation_id} ({method} {route.path})")
                    continue
                assert response.status_code == 404, (route.operation_id, response.status_code)
                assert world["project_id"] not in response.text.replace(url, "")
    finally:
        api.app.dependency_overrides.clear()
    assert unprocessable == [], f"the matrix needs a body or query for: {unprocessable}"
    assert api.enqueuer.sent == []  # nothing was enqueued for the owner's work
    row = await hk.sql("SELECT status FROM projects WHERE id=$1", UUID(world["project_id"]))
    assert row[0][0] == "ready"
    with capsys.disabled():
        print(f"\nroutes: {len(checked)}")


async def test_list_routes_show_the_second_user_nothing(api: ApiEnv, world: dict[str, str]) -> None:
    assert api.app is not None
    api.app.dependency_overrides[current_user] = lambda: CurrentUser(OTHER, "other")
    try:
        listed = (await api.client.get("/api/v1/projects")).json()
        settings = (await api.client.get("/api/v1/settings")).json()
    finally:
        api.app.dependency_overrides.clear()
    assert listed == {"items": [], "next_cursor": None}
    assert settings["disk"]["projects"] == []


async def test_a_foreign_host_is_403_on_every_route(
    api: ApiEnv, world: dict[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    count = 0
    for route in v1_routes():
        url = _any_url(route, world)
        for method in methods(route):
            response = await api.client.request(
                method, url, headers={"host": "evil.example"}, **_plain(route, method)
            )
            assert response.status_code == 403, (route.operation_id, method, response.status_code)
            count += 1
    with capsys.disabled():
        print(f"\nroutes (foreign Host): {count}")


async def test_a_cross_site_origin_or_fetch_site_is_403_on_every_state_changing_route(
    api: ApiEnv, world: dict[str, str]
) -> None:
    for route in v1_routes():
        url = _any_url(route, world)
        for method in methods(route):
            if method not in STATE_CHANGING:
                continue
            origin = await api.client.request(
                method, url, headers={"origin": "http://evil.example"}, **_plain(route, method)
            )
            assert origin.status_code == 403, (route.operation_id, "Origin", origin.status_code)
            site = await api.client.request(
                method, url, headers={"sec-fetch-site": "cross-site"}, **_plain(route, method)
            )
            assert site.status_code == 403, (route.operation_id, "Sec-Fetch-Site")


def _any_url(route: APIRoute, world: dict[str, str]) -> str:
    """The route's path with any id (the guard answers before a handler looks at it)."""
    ids = {p.name: world.get(p.name, str(OTHER)) for p in route.dependant.path_params}
    return fill(route, ids)


def _plain(route: APIRoute, method: str) -> dict[str, Any]:
    op = route.operation_id or ""
    out: dict[str, Any] = {"params": QUERIES.get(op, {})}
    if method in {"POST", "PUT", "PATCH"}:
        out["json"] = BODIES.get(op, {})
    return out


async def test_the_matrix_refuses_a_path_parameter_it_has_no_fixture_for() -> None:
    """The inventory guard itself: an unknown id name must fail loudly, not be skipped."""
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/jobs/{job_id}", operation_id="made_up")
    async def made_up(job_id: UUID) -> dict[str, str]:
        return {"job": str(job_id)}

    route = next(r for r in router.routes if isinstance(r, APIRoute))
    with pytest.raises(AssertionError, match="add a fixture for the path parameter"):
        fill(route, {"project_id": "x", "render_id": "y"})


# --- every public repository method filters by user ----------------------------------------------


def repository_methods() -> list[tuple[str, str, Any]]:
    import importlib
    import pkgutil

    found = []
    for info in pkgutil.iter_modules(repositories_pkg.__path__):
        module = importlib.import_module(f"saveclock.repositories.{info.name}")
        for class_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            for name, fn in inspect.getmembers(cls, inspect.isfunction):
                if not name.startswith("_"):
                    found.append((class_name, name, fn))
    return found


# methods whose result for the second user is legitimately their own (they create or read the
# user's own row); every other method must return nothing for the owner's ids
OWN_ROW = {"ProjectRepository.create", "UserRepository.get", "UserRepository.update_settings"}


async def test_every_repository_method_filters_by_user(hk: Hk, world: dict[str, str]) -> None:
    owner_project, owner_render = UUID(world["project_id"]), UUID(world["render_id"])
    job = await hk.job(owner_project, stage="draft", state="ok", finished_age=timedelta(0))
    engine = create_async_engine(hk.db.url("app_rw"), poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    needles = (str(owner_project), str(OWNER_USER_ID))
    owner_ids = {owner_project, owner_render, job, OWNER_USER_ID}

    async def snapshot() -> list[str]:
        tables = await hk.sql(
            "SELECT table_name FROM information_schema.tables"
            " WHERE table_schema='public' ORDER BY 1"
        )
        rows: list[str] = []
        for (table,) in tables:
            query = f'SELECT t::text FROM "{table}" t ORDER BY 1'  # noqa: S608 - catalogue names
            rows += [r[0] for r in await hk.sql(query) if any(n in r[0] for n in needles)]
        return rows

    before = await snapshot()
    non_empty: list[str] = []
    try:
        async with sessions() as reader:  # loaded once; a later rollback cannot expire it
            render = await _render_of(reader, owner_render)
        async with sessions() as session:
            values: dict[str, Any] = {
                "user_id": OTHER, "project_id": owner_project, "render_id": owner_render,
                "job_id": job, "job_ids": [job], "plan_id": UUID(int=7),
                "edit_plan_id": UUID(int=8),
                "render": render, "limit": 5, "after": None, "version": 1, "title": "hacked",
                "options": {}, "values": {}, "patch": {"stock": {}},
                "reason": None, "stage": "draft", "queue": "fetch", "error_code": "x",
                "detail": None, "timings": {}, "older_than": datetime(2100, 1, 1, tzinfo=UTC),
                "older_than_s": 0, "cutoff": datetime(2100, 1, 1, tzinfo=UTC),
                "queued_before": datetime(2100, 1, 1, tzinfo=UTC),
                "running_before": datetime(2100, 1, 1, tzinfo=UTC),
                "statuses": ["ready"], "from_": ("ready",), "to": "draft_ready",
                "job_hash": b"h" * 32, "expected_hash": b"h" * 32, "content_hash": b"h" * 32,
                "schema_version": "1", "plan": {}, "created_by": "planner", "verify": {},
                "size_bytes": 1, "duration_frames": 1, "render_ms": 1, "provider": "pexels",
                "provider_id": "1", "keys": [("pexels", "1")], "found": [], "tempo_bpm": Decimal(1),
                "duration_s": Decimal(1), "codec": "x", "sample_rate": 1, "channels": 1,
                "sha256": b"h" * 32, "source_ext": "wav", "original_filename": "a.wav",
                "content_type": "audio/wav",
            }  # fmt: skip
            for class_name, name, fn in repository_methods():
                key = f"{class_name}.{name}"
                params = [p for p in inspect.signature(fn).parameters.values() if p.name != "self"]
                unknown = [p.name for p in params if p.name not in values]
                assert not unknown, f"{key}: add a value for {unknown} to this test"
                kwargs = {p.name: values[p.name] for p in params}
                kwargs["user_id"] = OTHER
                if key == "ProjectRepository.update_fields":
                    kwargs["values"] = {"title": "hacked"}
                if key == "RenderRepository.insert_or_existing":
                    kwargs["render_id"] = UUID(int=4242)  # a fresh id: a real insert would show
                if key == "RenderRepository.set_mode_a":
                    kwargs["from_"], kwargs["to"] = (None,), ModeAState.QUEUED
                if key == "RenderRepository.set_state":
                    kwargs["from_"], kwargs["to"] = ("ready",), "canceled"
                instance = getattr(__import__(fn.__module__, fromlist=["x"]), class_name)(session)
                try:
                    result = await getattr(instance, name)(**kwargs)
                except (ValueError, TypeError):
                    continue  # an undrawn edge or a shape the method refuses: it did nothing
                except IntegrityError:
                    await session.rollback()  # a key that exists already: nothing was written
                    continue
                if key not in OWN_ROW and shows_owner(result, owner_ids):
                    non_empty.append(f"{key} -> {type(result).__name__}")
            await session.commit()
    finally:
        await engine.dispose()
    assert non_empty == [], f"these methods returned the owner's data to another user: {non_empty}"
    assert await snapshot() == before, "a method changed the owner's rows for another user"


def shows_owner(result: Any, owner_ids: set[UUID]) -> bool:
    """Does a repository result hold the owner's data? A list, set or dict is searched for the
    owner's ids; any other non-empty result (a row, a True, a count) is a leak too."""
    if result in (None, False, 0):
        return False
    items = list(result) if isinstance(result, list | set | tuple | dict) else [result]
    for item in items:
        for attr in ("id", "user_id", "project_id", "render_id"):
            if getattr(item, attr, None) in owner_ids:
                return True
        if item in owner_ids:
            return True
    return not isinstance(result, list | set | tuple | dict)


async def _render_of(session: Any, render_id: UUID) -> Any:
    from saveclock.repositories.renders import RenderRepository

    return await RenderRepository(session).get(user_id=OWNER_USER_ID, render_id=render_id)
