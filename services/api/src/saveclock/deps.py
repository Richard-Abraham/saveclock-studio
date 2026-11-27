"""The dependency bundle handed to the api. Layer-neutral: it imports only lower layers."""

from dataclasses import dataclass, field

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.queue import Enqueuer
from saveclock.services.health import Check
from saveclock.services.settings import UsageCache


@dataclass(frozen=True)
class Deps:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    blobs: BlobStore
    checks: dict[str, Check]
    enqueuer: Enqueuer
    usage_cache: UsageCache = field(default_factory=UsageCache)
    publisher: EventPublisher | None = None

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()
