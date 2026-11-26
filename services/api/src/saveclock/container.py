"""Wiring: builds the real dependencies once per process (not a layer; only main imports it)."""

import asyncio
from functools import partial
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.db import create_engine, create_sessionmaker, ping_db
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.queue import DramatiqEnqueuer
from saveclock.config import Settings
from saveclock.deps import Deps
from saveclock.workers.broker import build_broker
from saveclock.workers.stub import register_stub_actors

if TYPE_CHECKING:
    from saveclock.services.stub import Enqueue

STUB_ENVS = frozenset({"local", "ci"})


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

    broker = build_broker(settings)  # no connection until the first send
    enqueue_stub: Enqueue | None = None
    if settings.app_env in STUB_ENVS:
        enqueue_stub = register_stub_actors(broker, settings).send_first

    return Deps(
        engine=engine,
        sessionmaker=sessionmaker,
        redis=redis,
        blobs=blobs,
        enqueuer=DramatiqEnqueuer(broker),
        enqueue_stub=enqueue_stub,
        publisher=EventPublisher(aio=redis),
        checks={
            "postgres": partial(ping_db, sessionmaker),
            "redis": ping_redis,
            "blob_volume": blob_volume,
        },
    )
