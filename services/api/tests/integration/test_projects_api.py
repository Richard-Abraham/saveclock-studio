from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import httpx
import pytest

from saveclock.adapters.db import create_engine, create_sessionmaker
from saveclock.ids import new_id
from saveclock.repositories.projects import ProjectRepository
from saveclock.services.identity import OWNER_USER_ID
from tests.integration.conftest import ApiEnv, Db, insert_project, insert_user

pytestmark = pytest.mark.integration

BASE = datetime(2026, 1, 1, tzinfo=UTC)


async def test_empty_list_body(api_client: httpx.AsyncClient) -> None:
    r = await api_client.get("/api/v1/projects")
    assert r.status_code == 200
    assert r.json() == {"items": [], "next_cursor": None}


async def test_repository_scoping_with_a_second_user(migrated_db: Db) -> None:
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await insert_user(migrated_db, other, "b@example.test")
    mine = await insert_project(migrated_db, OWNER_USER_ID, "mine", BASE)
    theirs = await insert_project(migrated_db, other, "theirs", BASE)

    engine = create_engine(migrated_db.url("app_rw"))
    try:
        async with create_sessionmaker(engine)() as session:
            repo = ProjectRepository(session)
            assert [p.id for p in await repo.list(user_id=OWNER_USER_ID, limit=10)] == [mine]
            assert [p.id for p in await repo.list(user_id=other, limit=10)] == [theirs]
            assert await repo.get(user_id=other, project_id=mine) is None
            assert (await repo.get(user_id=OWNER_USER_ID, project_id=mine)) is not None
    finally:
        await engine.dispose()


async def test_http_never_shows_another_users_project(
    migrated_db: Db, api_client: httpx.AsyncClient
) -> None:
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await insert_user(migrated_db, other, "b@example.test")
    await insert_project(migrated_db, other, "theirs", BASE)
    mine = await insert_project(migrated_db, OWNER_USER_ID, "mine", BASE)
    body = (await api_client.get("/api/v1/projects")).json()
    assert [i["id"] for i in body["items"]] == [str(mine)]


async def test_cursor_pagination_and_validation(
    migrated_db: Db, api_client: httpx.AsyncClient
) -> None:
    ids = [
        await insert_project(migrated_db, OWNER_USER_ID, f"p{i}", BASE + timedelta(minutes=i))
        for i in range(3)
    ]
    first = (await api_client.get("/api/v1/projects", params={"limit": 2})).json()
    assert [i["id"] for i in first["items"]] == [str(ids[2]), str(ids[1])]
    assert first["next_cursor"] is not None
    second = (
        await api_client.get(
            "/api/v1/projects", params={"limit": 2, "cursor": first["next_cursor"]}
        )
    ).json()
    assert [i["id"] for i in second["items"]] == [str(ids[0])]
    assert second["next_cursor"] is None

    bad = await api_client.get("/api/v1/projects", params={"cursor": "garbage"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "bad_request"
    too_big = await api_client.get("/api/v1/projects", params={"limit": 101})
    assert too_big.status_code == 422


async def test_item_shape_and_deleted_hidden(
    migrated_db: Db, api_client: httpx.AsyncClient
) -> None:
    await insert_project(migrated_db, OWNER_USER_ID, "gone", BASE, status="deleted")
    pid = await insert_project(migrated_db, OWNER_USER_ID, "x", BASE, status="analyzing")
    items = (await api_client.get("/api/v1/projects")).json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(pid)
    assert items[0]["ui_status"] == "analysing"
    assert items[0]["disk_bytes"] == 0
    assert set(items[0]) == {
        "id",
        "title",
        "ui_status",
        "disk_bytes",
        "last_activity_at",
        "created_at",
    }


# --- plan 004: create, get, patch, cancel, retry ---------------------------------------------


async def _set(env: ApiEnv, pid: str, **cols: object) -> None:
    conn = await asyncpg.connect(env.db.raw("postgres"))
    try:
        for col, value in cols.items():
            await conn.execute(f"UPDATE projects SET {col} = $2 WHERE id = $1", UUID(pid), value)  # noqa: S608
    finally:
        await conn.close()


async def test_create_get_and_default_options(api: ApiEnv) -> None:
    r = await api.client.post("/api/v1/projects", json={"title": "Demo"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Demo"
    assert body["ui_status"] == "uploading"
    assert body["options"] == {
        "duration": 30,
        "style": "default",
        "density": 0,
        "vibe": None,
        "keywords_override": None,
    }
    assert (body["song"], body["analysis"], body["plan"], body["render"]) == (
        None,
        None,
        None,
        None,
    )
    again = await api.client.get(f"/api/v1/projects/{body['id']}")
    assert again.status_code == 200
    assert again.json()["id"] == body["id"]


async def test_get_bumps_last_activity(api: ApiEnv) -> None:
    pid = (await api.client.post("/api/v1/projects", json={})).json()["id"]
    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        await conn.execute(
            "UPDATE projects SET last_activity_at = '2020-01-01' WHERE id = $1", UUID(pid)
        )
    finally:
        await conn.close()
    body = (await api.client.get(f"/api/v1/projects/{pid}")).json()
    assert body["last_activity_at"] > "2025"


@pytest.mark.parametrize(
    "options",
    [
        {"unknown": 1},
        {"duration": 20},
        {"density": 2},
        {"style": "Bad Style"},
        {"vibe": "x" * 201},
        {"keywords_override": ["a"] * 9},
        {"keywords_override": ["UPPER"]},
    ],
)
async def test_option_validation(api: ApiEnv, options: dict[str, object]) -> None:
    r = await api.client.post("/api/v1/projects", json={"options": options})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_unknown_top_level_keys_are_refused(api: ApiEnv) -> None:
    assert (await api.client.post("/api/v1/projects", json={"nope": 1})).status_code == 422


async def test_patch_only_before_the_upload(api: ApiEnv) -> None:
    pid = (await api.client.post("/api/v1/projects", json={})).json()["id"]
    ok = await api.client.patch(
        f"/api/v1/projects/{pid}", json={"title": "New", "options": {"duration": 60}}
    )
    assert ok.status_code == 200
    assert (ok.json()["title"], ok.json()["options"]["duration"]) == ("New", 60)
    await _set(api, pid, status="validating")
    late = await api.client.patch(f"/api/v1/projects/{pid}", json={"title": "Late"})
    assert late.status_code == 409
    assert late.json()["error"]["details"]["reason"] == "wrong_state"


async def test_cancel_and_the_cancel_flag(api: ApiEnv) -> None:
    pid = (await api.client.post("/api/v1/projects", json={})).json()["id"]
    assert (await api.client.post(f"/api/v1/projects/{pid}/cancel")).status_code == 409  # created
    await _set(api, pid, status="analyzing")
    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        job = new_id()
        await conn.execute(
            "INSERT INTO jobs (id, project_id, stage, queue, state)"
            " VALUES ($1, $2, 'analyze', 'analysis', 'running')",
            job,
            UUID(pid),
        )
    finally:
        await conn.close()
    r = await api.client.post(f"/api/v1/projects/{pid}/cancel")
    assert r.status_code == 202
    assert r.json()["ui_status"] == "canceled"
    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        assert await conn.fetchval("SELECT cancel_requested FROM jobs WHERE id = $1", job) is True
    finally:
        await conn.close()
    again = await api.client.post(f"/api/v1/projects/{pid}/cancel")
    assert again.status_code == 409


async def test_retry_flow_and_the_manual_cap(api: ApiEnv) -> None:
    pid = (await api.client.post("/api/v1/projects", json={})).json()["id"]
    wrong = await api.client.post(f"/api/v1/projects/{pid}/retry")
    assert wrong.status_code == 409  # created is not retryable
    for attempt in range(3):
        await _set(api, pid, status="failed_analysis")
        r = await api.client.post(f"/api/v1/projects/{pid}/retry")
        assert r.status_code == 202, (attempt, r.text)
        assert r.json()["ui_status"] == "analysing"
    assert [a for a, _ in api.enqueuer.sent] == ["validate_audio"] * 3
    await _set(api, pid, status="failed_analysis")
    fourth = await api.client.post(f"/api/v1/projects/{pid}/retry")
    assert fourth.status_code == 409
    assert fourth.json()["error"]["details"]["reason"] == "retry_limit"
    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        row = await conn.fetchrow(
            "SELECT status, manual_retries FROM projects WHERE id = $1", UUID(pid)
        )
    finally:
        await conn.close()
    assert tuple(row) == ("failed_analysis", 3)  # the refused retry changed nothing
    assert len(api.enqueuer.sent) == 3


async def test_cancel_ends_queued_jobs_and_flags_running_ones(api: ApiEnv) -> None:
    pid = (await api.client.post("/api/v1/projects", json={})).json()["id"]
    await _set(api, pid, status="planning")
    queued, running = new_id(), new_id()
    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        for job, stage, state in ((queued, "draft", "queued"), (running, "analyze", "running")):
            await conn.execute(
                "INSERT INTO jobs (id, project_id, stage, queue, state)"
                " VALUES ($1, $2, $3, 'fetch', $4)",
                job,
                UUID(pid),
                stage,
                state,
            )
        assert (await api.client.post(f"/api/v1/projects/{pid}/cancel")).status_code == 202
        rows = {r["id"]: r for r in await conn.fetch("SELECT * FROM jobs")}
    finally:
        await conn.close()
    assert (rows[queued]["state"], rows[queued]["error_code"]) == ("error", "canceled")
    assert (rows[running]["state"], rows[running]["cancel_requested"]) == ("running", True)


async def test_retry_from_canceled(api: ApiEnv) -> None:
    pid = (await api.client.post("/api/v1/projects", json={})).json()["id"]
    await _set(api, pid, status="canceled")
    assert (await api.client.post(f"/api/v1/projects/{pid}/retry")).status_code == 202


async def test_a_foreign_project_is_a_404_everywhere(migrated_db: Db, api: ApiEnv) -> None:
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await insert_user(migrated_db, other, "b@example.test")
    theirs = await insert_project(migrated_db, other, "theirs", BASE)
    for method, path in [
        ("GET", f"/api/v1/projects/{theirs}"),
        ("PATCH", f"/api/v1/projects/{theirs}"),
        ("POST", f"/api/v1/projects/{theirs}/cancel"),
        ("POST", f"/api/v1/projects/{theirs}/retry"),
        ("GET", f"/api/v1/projects/{theirs}/analysis"),
    ]:
        r = await api.client.request(method, path, json={} if method == "PATCH" else None)
        assert r.status_code == 404, (method, path)


async def test_transition_is_scoped_to_the_owner(migrated_db: Db) -> None:
    """The repository refuses a foreign user even when the id and the status match."""
    other = UUID("00000000-0000-4000-8000-0000000000bb")
    await insert_user(migrated_db, other, "b@example.test")
    mine = await insert_project(migrated_db, OWNER_USER_ID, "mine", BASE)
    engine = create_engine(migrated_db.url("app_rw"))
    try:
        async with create_sessionmaker(engine)() as session:
            repo = ProjectRepository(session)
            assert not await repo.transition(
                user_id=other, project_id=mine, from_="created", to="uploading"
            )
            assert await repo.transition(
                user_id=OWNER_USER_ID, project_id=mine, from_="created", to="uploading"
            )
            assert not await repo.transition(  # the status moved on: a lost race is 0 rows
                user_id=OWNER_USER_ID, project_id=mine, from_="created", to="uploading"
            )
            with pytest.raises(ValueError, match="undrawn"):
                await repo.transition(
                    user_id=OWNER_USER_ID, project_id=mine, from_="uploading", to="ready"
                )
    finally:
        await engine.dispose()
