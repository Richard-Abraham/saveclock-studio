"""The automatic draft in-process: real Postgres, Redis and FFmpeg, generated clips for stock, the
click picker for Beat This. The actors are bypassed (`run_draft` is called directly) so a test can
look between stages; `test_draft_e2e.py` runs the real worker subprocess."""

import asyncio
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import UUID

import asyncpg
from redis import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.domain.edit_plan import EditPlan
from saveclock.domain.events import Event
from saveclock.domain.ids import derive_job_id
from saveclock.services.analysis import analyze_project
from saveclock.services.context import WorkerContext
from saveclock.services.draft import run_draft
from saveclock.services.ingest import validate_song
from tests.conftest import ENV
from tests.factories.audio import click_track
from tests.integration.conftest import REDIS_URL, ApiEnv

OWNER = UUID("00000000-0000-4000-8000-000000000001")


class Recorder(EventPublisher):
    """Keeps every event instead of sending it (thread safe: the ticker publishes from one)."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[Event] = []
        self._lock = threading.Lock()

    def publish_sync(self, project_id: UUID, event: Event) -> None:
        with self._lock:
            self.sent.append(event)

    async def publish(self, project_id: UUID, event: Event) -> None:
        self.publish_sync(project_id, event)

    def kinds(self) -> list[str]:
        return [e.type for e in self.sent]


@dataclass
class Draft:
    env: ApiEnv
    ctx: WorkerContext
    tmp_path: Path
    recorder: Recorder
    redis: Redis
    jobs: list[UUID] = field(default_factory=list)

    @property
    def client(self) -> Any:
        return self.env.client

    @property
    def sent(self) -> list[tuple[str, tuple[str, ...]]]:
        enqueuer = self.ctx.enqueuer
        assert isinstance(enqueuer, FakeEnqueuer)
        return enqueuer.sent

    async def sql(self, query: str, *args: object) -> list[asyncpg.Record]:
        conn = await asyncpg.connect(self.env.db.raw("postgres"))
        try:
            rows: list[asyncpg.Record] = await conn.fetch(query, *args)
            return rows
        finally:
            await conn.close()

    async def upload(self, bpm: float = 128.0, seconds: float = 30.0, **options: Any) -> UUID:
        """A project with a click track uploaded (the validate job is queued)."""
        body = {"options": options} if options else {}
        pid = UUID((await self.client.post("/api/v1/projects", json=body)).json()["id"])
        wav = self.tmp_path / f"click-{pid}.wav"
        click_track(wav, bpm=bpm, duration=seconds)
        data = await asyncio.to_thread(wav.read_bytes)
        r = await self.client.post(
            f"/api/v1/projects/{pid}/song",
            content=data,
            headers={"content-type": "audio/wav", "x-filename": quote("Click.wav")},
        )
        assert r.status_code == 202, r.text
        return pid

    async def analysed(self, pid: UUID | None = None, **kw: Any) -> tuple[UUID, UUID]:
        """Upload, validate and analyze: the project is `planning`, the draft job queued."""
        pid = pid or await self.upload(**kw)
        vjob = UUID(
            str(
                (
                    await self.sql(
                        "SELECT id FROM jobs WHERE project_id = $1 AND stage = 'validate'", pid
                    )
                )[-1][0]
            )
        )
        await validate_song(self.ctx, vjob, OWNER)
        ajob = derive_job_id(vjob, "analyze")
        await analyze_project(self.ctx, ajob, OWNER)
        return pid, derive_job_id(ajob, "draft")

    async def drafted(self, **kw: Any) -> UUID:
        """A project with its first draft stored (`draft_ready`)."""
        pid, djob = await self.analysed(**kw)
        await run_draft(self.ctx, djob, OWNER, mode="draft")
        assert await self.status(pid) == ("draft_ready", None)
        return pid

    async def status(self, pid: UUID) -> tuple[str, str | None]:
        row = (await self.sql("SELECT status, status_reason FROM projects WHERE id = $1", pid))[0]
        return str(row[0]), row[1]

    async def job(self, job_id: UUID) -> tuple[str, str | None]:
        row = (await self.sql("SELECT state, error_code FROM jobs WHERE id = $1", job_id))[0]
        return str(row[0]), row[1]

    async def plan(self, pid: UUID, version: int | None = None) -> EditPlan:
        rows = await self.sql(
            "SELECT plan FROM edit_plans WHERE project_id = $1 ORDER BY version DESC", pid
        )
        import json

        data = [json.loads(r[0]) for r in rows]
        chosen = next(d for d in data if version is None or d["version"] == version)
        return EditPlan.model_validate(chosen)

    async def freeze(self, pid: UUID) -> None:
        await self.sql(
            "UPDATE edit_plans SET frozen_at = now() WHERE project_id = $1 AND frozen_at IS NULL",
            pid,
        )


async def build_draft_env(
    env: ApiEnv, tools: Tools, clips_dir: Path, tmp_path: Path, **overrides: object
) -> tuple[Draft, Any]:
    settings = Settings(
        _env_file=None,
        **{  # type: ignore[arg-type]
            **ENV,
            "blob_root": str(env.blob_root),
            "scratch_root": str(tmp_path / "scratch"),
            "redis_url": REDIS_URL,
            "database_url": env.db.url("app_rw"),
            "fake_ml": True,
            "fake_stock": True,
            "fake_stock_dir": str(clips_dir),
            "worker_heavy_concurrency": 1,
            **overrides,
        },
    )
    engine = create_async_engine(env.db.url("app_rw"), poolclass=NullPool)
    recorder = Recorder()
    ctx = WorkerContext(
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
        blobs=FilesystemBlobStore(env.blob_root, 0),
        tools=tools,
        enqueuer=FakeEnqueuer(),
        settings=settings,
        publisher=recorder,
    )
    redis: Redis = Redis.from_url(REDIS_URL)
    redis.flushdb()
    return Draft(env, ctx, tmp_path, recorder, redis), engine
