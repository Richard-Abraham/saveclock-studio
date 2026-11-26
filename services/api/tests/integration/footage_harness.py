"""The footage services against real Postgres, Redis, FFmpeg and a directory of generated clips."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

from PIL import Image
from redis import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.heavy_lock import HeavyLock
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.adapters.siglip import FakeRanker
from saveclock.adapters.stock.fake import FakeStockProvider
from saveclock.config import Settings
from saveclock.models import ClipCandidate
from saveclock.repositories.candidates import CandidateRepository, NewCandidate
from saveclock.services.context import WorkerContext
from saveclock.services.footage import FootageDeps, SearchResult, VetResult, search, vet_and_rank
from tests.conftest import ENV
from tests.integration.conftest import REDIS_URL, ApiEnv

OWNER = UUID("00000000-0000-4000-8000-000000000001")
PALETTE = {
    "red": (0xD0, 0x30, 0x30),  # the colours of `make fake-stock` (eval/scripts/make_fake_stock.py)
    "green": (0x30, 0xC0, 0x30),
    "blue": (0x30, 0x30, 0xD0),
    "yellow": (0xE0, 0xD0, 0x30),
}


def _unit(rgb: Sequence[float]) -> list[float]:
    n = sum(c * c for c in rgb) ** 0.5
    return [c / n for c in rgb]


class ColourRanker:
    """An independent oracle: a frame's vector is its dominant colour, a keyword's vector is the
    hand-written colour of that word (red, green, blue, yellow). No hashing, no model."""

    name = "colour-oracle"
    version = "1"

    def embed_images(self, paths: Sequence[Path]) -> list[list[float]]:
        out = []
        for path in paths:
            with Image.open(path) as img:
                small = img.convert("RGB").resize((8, 8))
                pixels = cast("list[tuple[int, int, int]]", list(small.get_flattened_data()))
            mean = [sum(p[i] for p in pixels) / len(pixels) for i in range(3)]
            out.append(_unit(mean))
        return out

    def embed_text(self, prompts: Sequence[str]) -> list[list[float]]:
        return [_unit(PALETTE[p]) for p in prompts]


@dataclass(frozen=True)
class Footage:
    env: ApiEnv
    ctx: WorkerContext
    deps: FootageDeps
    pid: UUID
    clips_dir: Path
    redis: Redis

    def with_ranker(self, ranker: object) -> "Footage":
        return replace(self, deps=replace(self.deps, ranker=ranker))  # type: ignore[arg-type]

    async def new_project(self) -> UUID:
        r = await self.env.client.post("/api/v1/projects", json={})
        return UUID(r.json()["id"])

    async def search(self, keywords: Sequence[str], **kw: object) -> SearchResult:
        return await search(
            self.deps,
            user_id=OWNER,
            project_id=self.pid,
            keywords=keywords,
            **kw,  # type: ignore[arg-type]
        )

    async def rows(
        self, statuses: Sequence[str] | None = None, *, pid: UUID | None = None
    ) -> list[ClipCandidate]:
        async with self.ctx.sessionmaker() as session:
            return await CandidateRepository(session).list_for_project(
                user_id=OWNER, project_id=pid or self.pid, statuses=statuses
            )

    async def by_id(self, name: str) -> ClipCandidate:
        async with self.ctx.sessionmaker() as session:
            row = await CandidateRepository(session).get_by_provider_id(
                user_id=OWNER, project_id=self.pid, provider="pexels", provider_id=f"fake-{name}"
            )
        assert row is not None, name
        return row

    async def add(
        self,
        name: str,
        *,
        width: int = 720,
        height: int = 1280,
        duration_s: float = 10.0,
        query: str = "red",
    ) -> None:
        """A candidate row whose provider metadata is better than the real file (to test the
        checks on the real file)."""
        async with self.ctx.sessionmaker() as session:
            await CandidateRepository(session).upsert_found(
                user_id=OWNER,
                project_id=self.pid,
                found=[
                    NewCandidate(
                        "pexels",
                        f"fake-{name}",
                        query,
                        "https://www.pexels.com/video/x/",
                        None,
                        None,
                        "Pexels License",
                        width,
                        height,
                        duration_s,
                        30.0,
                        f"fake://{name}.mp4",
                    )
                ],
            )
            await session.commit()

    async def vet(self, statuses: Sequence[str] | None = None) -> VetResult:
        return await vet_and_rank(
            self.deps, user_id=OWNER, project_id=self.pid, candidates=await self.rows(statuses)
        )


async def build_footage(
    api: ApiEnv, tools: Tools, clips_dir: Path, tmp_path: Path
) -> tuple[Footage, object]:
    settings = Settings(
        _env_file=None,
        **{  # type: ignore[arg-type]
            **ENV,
            "blob_root": str(api.blob_root),
            "scratch_root": str(tmp_path / "scratch"),
            "redis_url": REDIS_URL,
            "database_url": api.db.url("app_rw"),
            "fake_ml": True,
            "fake_stock": True,
            "fake_stock_dir": str(clips_dir),
            "worker_heavy_concurrency": 1,
        },
    )
    engine = create_async_engine(api.db.url("app_rw"), poolclass=NullPool)
    ctx = WorkerContext(
        sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
        blobs=FilesystemBlobStore(api.blob_root, 0),
        tools=tools,
        enqueuer=FakeEnqueuer(),
        settings=settings,
    )
    redis: Redis = Redis.from_url(REDIS_URL)
    redis.flushdb()
    deps = FootageDeps(
        ctx,
        (FakeStockProvider(clips_dir),),
        FakeRanker(),
        HeavyLock(redis, 1, settings.heavy_ttl_s),
        fetch_concurrency=3,
        seed=1,
    )
    pid = UUID((await api.client.post("/api/v1/projects", json={})).json()["id"])
    return Footage(api, ctx, deps, pid, clips_dir, redis), engine


def window_start(row: ClipCandidate) -> Decimal:
    assert row.window_start_s is not None
    return row.window_start_s
