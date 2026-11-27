"""A real database and blob root with hand-made projects, for the retention tests (plan 008).

Projects, plans and renders are inserted with SQL and their files with `FilesystemBlobStore`, so a
test controls time (`last_activity_at`, `finished_at`) and sees exactly which bytes survive.
"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.ids import new_id
from saveclock.services.context import WorkerContext
from saveclock.services.identity import OWNER_USER_ID
from tests.conftest import ENV
from tests.integration.conftest import REDIS_URL, Db

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
DAY = timedelta(days=1)


def clock() -> datetime:
    return NOW


@dataclass
class Hk:
    db: Db
    ctx: WorkerContext
    blobs: FilesystemBlobStore
    enqueuer: FakeEnqueuer
    redis: Redis
    engine: AsyncEngine
    user: UUID = OWNER_USER_ID

    async def sql(self, query: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self.db.raw("postgres"))
        try:
            rows: list[asyncpg.Record] = await conn.fetch(query, *args)
            return rows
        finally:
            await conn.close()

    def put(self, key: str, data: bytes = b"x" * 100) -> None:
        self.blobs.put(key, iter([data]), max_bytes=10**9)

    async def project(
        self,
        *,
        status: str = "draft_ready",
        idle: timedelta = timedelta(0),
        purged: bool = False,
        files: bool = True,
        user: UUID | None = None,
    ) -> UUID:
        """A project idle for `idle` (counted from NOW) with a song and intermediates on disk."""
        pid = new_id()
        owner = user or self.user
        await self.sql(
            "INSERT INTO projects (id, user_id, title, status, last_activity_at,"
            " intermediates_purged_at) VALUES ($1,$2,'t',$3,$4,$5)",
            pid,
            owner,
            status,
            NOW - idle,
            NOW if purged else None,
        )
        if files:
            self.put(f"songs/{pid}/source.wav", b"song" * 50)
            for sub in (
                "raw/pexels_1.mp4",
                "mezz/pexels_1.mp4",
                "emb/pexels_1.npy",
                "canonical.flac",
            ):
                self.put(f"work/{pid}/{sub}")
        return pid

    async def plan(self, pid: UUID) -> UUID:
        plan_id = new_id()
        await self.sql(
            "INSERT INTO edit_plans (id, project_id, version, schema_version, plan, content_hash,"
            " created_by) VALUES ($1,$2,1,'1',$3,$4,'planner')",
            plan_id,
            pid,
            json.dumps({}),
            b"h" * 32,
        )
        return plan_id

    async def render(self, pid: UUID, plan_id: UUID, *, mode_a: bool = False) -> UUID:
        rid = new_id()
        await self.sql(
            "INSERT INTO renders (id, project_id, edit_plan_id, user_id, job_hash, state)"
            " VALUES ($1,$2,$3,$4,$5,'ready')",
            rid,
            pid,
            plan_id,
            self.user,
            bytes([rid.bytes[0]]) * 32,
        )
        self.put(f"renders/{rid}/master.mp4", b"m" * 200)
        if mode_a:
            self.put(f"renders/{rid}/with_song.mp4", b"w" * 300)
        return rid

    async def job(
        self,
        pid: UUID,
        *,
        stage: str = "validate",
        state: str = "queued",
        age: timedelta = timedelta(0),
        finished_age: timedelta | None = None,
    ) -> UUID:
        jid = new_id()
        queue = {"validate": "analysis", "analyze": "analysis", "render": "render"}.get(
            stage, "fetch"
        )
        await self.sql(
            "INSERT INTO jobs (id, project_id, stage, queue, state, created_at, updated_at,"
            " finished_at) VALUES ($1,$2,$3,$4,$5,$6,$6,$7)",
            jid,
            pid,
            stage,
            queue,
            state,
            NOW - age,
            None if finished_age is None else NOW - finished_age,
        )
        return jid

    def has(self, prefix: str) -> bool:
        return bool(self.blobs.list(prefix))


async def build_hk(db: Db, blob_root: object, **overrides: object) -> Hk:
    settings = Settings(
        _env_file=None,
        **{  # type: ignore[arg-type]
            **ENV,
            "database_url": db.url("app_rw"),
            "redis_url": REDIS_URL,
            "blob_root": str(blob_root),
            "disk_low_watermark_gb": 0,
            **overrides,
        },
    )
    engine = create_async_engine(db.url("app_rw"), poolclass=NullPool)
    blobs = FilesystemBlobStore(settings.blob_root, 0)
    enqueuer = FakeEnqueuer()
    ctx = WorkerContext(
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
        blobs=blobs,
        tools=Tools("/nonexistent/ffmpeg", "/nonexistent/ffprobe"),
        enqueuer=enqueuer,
        settings=settings,
    )
    redis: Redis = Redis.from_url(REDIS_URL)
    redis.flushdb()
    return Hk(db, ctx, blobs, enqueuer, redis, engine)
