"""Integration fixtures: real Postgres and Redis from compose.test.yml (make test-deps-up)."""

import os
import signal
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
import httpx
import pytest
from fastapi import FastAPI
from redis.asyncio import Redis

from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.container import build_deps
from saveclock.ids import new_id
from saveclock.main import create_app
from tests.conftest import ENV, FFMPEG_DIR, client_for, make_app
from tests.factories.stock import fake_stock

if TYPE_CHECKING:
    from tests.integration.draft_harness import Draft
    from tests.integration.footage_harness import Footage
    from tests.integration.housekeeping_harness import Hk
    from tests.integration.render_harness import Renders

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


@dataclass(frozen=True)
class ApiEnv:
    client: httpx.AsyncClient
    enqueuer: FakeEnqueuer
    db: Db
    blob_root: Path
    app: FastAPI | None = None  # the app behind `client`, for dependency overrides


@asynccontextmanager
async def build_api(db: Db, blob_root: Path, **overrides: object) -> AsyncIterator[ApiEnv]:
    """The real app over ASGI with a recording enqueuer instead of the Redis broker."""
    settings_args: dict[str, object] = {
        "database_url": db.url("app_rw"),
        "redis_url": REDIS_URL,
        "blob_root": str(blob_root),
        "disk_low_watermark_gb": 0,
        **overrides,
    }
    settings = Settings(_env_file=None, **{**ENV, **settings_args})  # type: ignore[arg-type]
    enqueuer = FakeEnqueuer()
    deps = replace(build_deps(settings), enqueuer=enqueuer)
    app = create_app(settings, deps)
    async with client_for(app) as client:
        yield ApiEnv(client, enqueuer, db, blob_root, app)
    await deps.close()


@pytest.fixture
async def api(migrated_db: Db, blob_root: Path) -> AsyncIterator[ApiEnv]:
    async with build_api(migrated_db, blob_root) as env:
        yield env


class Harness:
    def __init__(self, db: Db, blob_root: Path, tmp_path: Path) -> None:
        self.db, self.blob_root, self.tmp_path = db, blob_root, tmp_path
        self.procs: list[subprocess.Popen[bytes]] = []

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"OWNER_DISPLAY_NAME", "FETCH_CONCURRENCY"}
        }
        env.update(
            APP_ENV="ci",
            APP_ORIGIN="http://localhost:3000",
            DATABASE_URL=self.db.url("app_rw"),
            REDIS_URL=REDIS_URL,
            BLOB_ROOT=str(self.blob_root),
            DISK_LOW_WATERMARK_GB="0",
            SCRATCH_ROOT=str(self.tmp_path / "scratch"),
            FFMPEG_BIN=str(FFMPEG_DIR / "ffmpeg"),
            FFPROBE_BIN=str(FFMPEG_DIR / "ffprobe"),
            FAKE_ML="true",  # the click picker stands in for Beat This (tests/ml: the real one)
            WORKER_HEAVY_CONCURRENCY="1",
        )
        env.update(extra)
        return env

    def start_worker(self, queues: list[str], **extra_env: str) -> subprocess.Popen[bytes]:
        log = (self.tmp_path / f"worker{len(self.procs)}.log").open("wb")
        proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
            [
                sys.executable,
                "-m",
                "dramatiq",
                "saveclock.workers.main",
                "--processes",
                "1",
                "--threads",
                "2",
                "--queues",
                *queues,
            ],
            cwd=API_DIR,
            env=self.env(**extra_env),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.procs.append(proc)
        return proc

    def kill_all(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)


class LiveApi:
    """The real API as a uvicorn subprocess on an ephemeral 127.0.0.1 port, with the harness's
    environment (plan 009): a CLI subprocess needs a listening server, and `ASGITransport` buffers
    streams. Use as a context manager; `url` is the base URL."""

    def __init__(self, harness: "Harness") -> None:
        self.harness = harness
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port: int = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.proc: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> "LiveApi":
        log = (self.harness.tmp_path / "api.log").open("wb")
        self.proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
            [sys.executable, "-m", "uvicorn", "saveclock.main:create_app", "--factory",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=API_DIR, env=self.harness.env(), stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )  # fmt: skip
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"{self.url}/api/v1/health/live", timeout=2).status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            if self.proc.poll() is not None:
                break
            time.sleep(0.2)
        self.__exit__()
        msg = f"the API did not start: {(self.harness.tmp_path / 'api.log').read_text()[-800:]}"
        raise RuntimeError(msg)

    def __exit__(self, *_exc: object) -> None:
        if self.proc is not None and self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait(timeout=10)


@pytest.fixture
def harness(
    migrated_db: Db, blob_root: Path, tmp_path: Path, redis_client: Redis
) -> Iterator[Harness]:
    h = Harness(migrated_db, blob_root, tmp_path)
    yield h
    h.kill_all()


# --- footage (plan 005): real database, FFmpeg and generated clips; the model is a double ---


@pytest.fixture(scope="session")
def fake_clips(ffmpeg_tools: Tools, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The 8 clips of `make fake-stock` plus the two extras, generated once per test session."""
    directory = tmp_path_factory.mktemp("fake-stock")
    fake_stock.make_all(ffmpeg_tools, directory, extra=fake_stock.EXTRA.values())
    return directory


@pytest.fixture
async def footage(
    api: ApiEnv, ffmpeg_tools: Tools, fake_clips: Path, tmp_path: Path
) -> AsyncIterator["Footage"]:
    from tests.integration.footage_harness import build_footage

    harness, engine = await build_footage(api, ffmpeg_tools, fake_clips, tmp_path)
    yield harness
    harness.redis.close()
    await engine.dispose()  # type: ignore[attr-defined]


@pytest.fixture
async def draft(
    api: ApiEnv, ffmpeg_tools: Tools, fake_clips: Path, tmp_path: Path
) -> AsyncIterator["Draft"]:
    """The automatic draft in-process (plan 006): fake stock, fake Beat This, real the rest."""
    from tests.integration.draft_harness import build_draft_env

    d, engine = await build_draft_env(api, ffmpeg_tools, fake_clips, tmp_path)
    yield d
    d.redis.close()
    await engine.dispose()


@pytest.fixture
async def renderer(draft: "Draft") -> "Renders":
    """Rendering in-process (plan 007) on top of the draft harness."""
    from tests.integration.render_harness import Renders

    return Renders(draft)


@pytest.fixture
async def hk(migrated_db: Db, blob_root: Path, redis_client: Redis) -> AsyncIterator["Hk"]:
    """Hand-made projects and files for the retention tests (plan 008)."""
    from tests.integration.housekeeping_harness import build_hk

    h = await build_hk(migrated_db, blob_root)
    yield h
    h.redis.close()
    await h.engine.dispose()
