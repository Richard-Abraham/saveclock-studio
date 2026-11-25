"""Wiring: builds the real dependencies once per process. Not part of any layer."""

from dataclasses import dataclass
from functools import partial

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from saveclock.adapters.db import create_engine, create_sessionmaker, ping_db
from saveclock.config import Settings
from saveclock.services.health import Check


@dataclass(frozen=True)
class Deps:
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    checks: dict[str, Check]

    async def close(self) -> None:
        await self.redis.aclose()
        await self.engine.dispose()


def build_deps(settings: Settings) -> Deps:
    """Nothing connects here: engines and clients are lazy."""
    engine = create_engine(settings.database_url.get_secret_value())
    sessionmaker = create_sessionmaker(engine)
    redis = Redis.from_url(settings.redis_url.get_secret_value())

    async def ping_redis() -> None:
        await redis.ping()

    return Deps(
        engine=engine,
        sessionmaker=sessionmaker,
        redis=redis,
        checks={"postgres": partial(ping_db, sessionmaker), "redis": ping_redis},
    )
