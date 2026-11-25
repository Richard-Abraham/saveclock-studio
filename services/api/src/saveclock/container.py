"""Wiring: builds the real dependencies once per process. Not part of any layer."""

import asyncio
from dataclasses import dataclass, field
from functools import partial

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.db import create_engine, create_sessionmaker, ping_db
from saveclock.config import Settings
from saveclock.services.health import Check
from saveclock.services.settings import UsageCache


@dataclass(frozen=True)
class Deps:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    blobs: BlobStore
    checks: dict[str, Check]
    usage_cache: UsageCache = field(default_factory=UsageCache)

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def build_deps(settings: Settings) -> Deps:
    """Nothing connects here: engines and clients are lazy."""
    engine = create_engine(settings.database_url.get_secret_value())
    sessionmaker = create_sessionmaker(engine)
    redis = Redis.from_url(settings.redis_url.get_secret_value())
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    async def ping_redis() -> None:
        await redis.ping()

    async def blob_volume() -> None:
        await asyncio.to_thread(blobs.probe)

    return Deps(
        engine=engine,
        sessionmaker=sessionmaker,
        redis=redis,
        blobs=blobs,
        checks={
            "postgres": partial(ping_db, sessionmaker),
            "redis": ping_redis,
            "blob_volume": blob_volume,
        },
    )
