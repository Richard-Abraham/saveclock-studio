from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import httpx
import pytest

from saveclock.adapters.db import create_engine, create_sessionmaker
from saveclock.ids import new_id
from saveclock.repositories.projects import ProjectRepository
from saveclock.services.identity import OWNER_USER_ID
from tests.integration.conftest import Db

pytestmark = pytest.mark.integration

BASE = datetime(2026, 1, 1, tzinfo=UTC)


async def insert_user(db: Db, user_id: UUID, email: str) -> None:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        await conn.execute("INSERT INTO users (id, email) VALUES ($1, $2)", user_id, email)
    finally:
        await conn.close()


async def insert_project(
    db: Db, user_id: UUID, title: str, created_at: datetime, status: str = "created"
) -> UUID:
    pid = new_id()
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        await conn.execute(
            "INSERT INTO projects (id, user_id, title, status, created_at) VALUES ($1,$2,$3,$4,$5)",
            pid,
            user_id,
            title,
            status,
            created_at,
        )
    finally:
        await conn.close()
    return pid


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
