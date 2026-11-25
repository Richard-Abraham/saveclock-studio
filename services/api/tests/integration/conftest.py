"""Integration fixtures: real Postgres and Redis from compose.test.yml (make test-deps-up)."""

import os
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import httpx
import pytest
from redis.asyncio import Redis

from tests.conftest import client_for, make_app

API_DIR = Path(__file__).resolve().parents[2]
PG_HOST, PG_PORT = "127.0.0.1", 55432
REDIS_URL = "redis://:test-redis-pw@127.0.0.1:56379/0"
PASSWORDS = {
    "postgres": "test-superuser-pw",
    "app_rw": "test-app-pw",
    "migrator": "test-migrator-pw",
}
OWNER_NAME = "Test Owner"


def dsn(role: str, db: str, *, driver: str = "postgresql") -> str:
    return f"{driver}://{role}:{PASSWORDS[role]}@{PG_HOST}:{PG_PORT}/{db}"


@dataclass(frozen=True)
class Db:
    name: str

    def url(self, role: str) -> str:
        return dsn(role, self.name, driver="postgresql+asyncpg")

    def raw(self, role: str) -> str:
        return dsn(role, self.name)

    def alembic(
        self, *args: str, owner: str | None = OWNER_NAME
    ) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k not in {"OWNER_DISPLAY_NAME"}}
        env["MIGRATOR_DATABASE_URL"] = self.url("migrator")
        if owner is not None:
            env["OWNER_DISPLAY_NAME"] = owner
        return subprocess.run(  # noqa: S603 - fixed argument list, no shell
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
            cwd=API_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )


async def _admin() -> asyncpg.Connection:
    return await asyncpg.connect(dsn("postgres", "postgres"))


@pytest.fixture
async def fresh_db() -> AsyncIterator[Db]:
    """An empty database cloned from `saveclock` (which carries the roles' grants)."""
    name = f"t_{uuid.uuid4().hex[:12]}"
    admin = await _admin()
    await admin.execute(f'CREATE DATABASE "{name}" TEMPLATE saveclock')
    try:
        yield Db(name)
    finally:
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.close()


@pytest.fixture
async def migrated_db(fresh_db: Db) -> Db:
    done = fresh_db.alembic("upgrade", "head")
    assert done.returncode == 0, done.stderr
    return fresh_db


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(REDIS_URL)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.fixture
def blob_root(tmp_path: Path) -> Path:
    root = tmp_path / "blobs"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture
async def api_client(migrated_db: Db, blob_root: Path) -> AsyncIterator[httpx.AsyncClient]:
    """The real app over ASGI, talking to the migrated test database as `app_rw`."""
    app = make_app(
        database_url=migrated_db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(blob_root),
        disk_low_watermark_gb=0,  # the host's free space must not decide test results
    )
    async with client_for(app) as client:
        yield client
    await app.state.deps.close()
