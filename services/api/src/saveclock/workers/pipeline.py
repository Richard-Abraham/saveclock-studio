"""What the Phase 2 actors share: explicit limits, the context builder and the failure hook.

Actors are thin: resolve ids, call a service, nothing else. Messages carry ids only (job_id,
user_id); delivery is at-least-once, so every service step is idempotent.
"""

import asyncio
from typing import Any
from uuid import UUID

import dramatiq
import structlog
from redis import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.events import EventPublisher
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import DramatiqEnqueuer
from saveclock.config import Settings
from saveclock.models import JobQueue
from saveclock.services.context import WorkerContext
from saveclock.services.pipeline_failure import job_died

log = structlog.get_logger()

# Explicit on every actor: nothing relies on Dramatiq's defaults (20 retries, 10 min).
MAX_RETRIES = 2
MIN_BACKOFF_MS = 5_000
MAX_BACKOFF_MS = 30_000
FAILED_ACTOR = "pipeline_failed"


def actor_options(
    queue: JobQueue,
    time_limit_ms: int,
    *,
    max_retries: int = MAX_RETRIES,
    min_backoff_ms: int = MIN_BACKOFF_MS,
    max_backoff_ms: int = MAX_BACKOFF_MS,
    on_retry_exhausted: str | None = FAILED_ACTOR,
) -> dict[str, Any]:
    """`on_retry_exhausted=None` omits the hook: it unpacks `(job_id, user_id)`, which a
    maintenance message does not carry."""
    options: dict[str, Any] = {
        "queue_name": queue.value,
        "max_retries": max_retries,
        "min_backoff": min_backoff_ms,
        "max_backoff": max_backoff_ms,
        "time_limit": time_limit_ms,
    }
    if on_retry_exhausted is not None:
        options["on_retry_exhausted"] = on_retry_exhausted
    return options


def run_with_context(
    settings: Settings,
    broker: dramatiq.Broker,
    blobs: FilesystemBlobStore,
    body: Any,  # noqa: ANN401
) -> None:
    """One event loop and one NullPool engine per message (a shortcut: no shared loop or pool)."""

    async def go() -> None:
        engine = create_async_engine(settings.database_url.get_secret_value(), poolclass=NullPool)
        publisher = EventPublisher(sync=Redis.from_url(settings.redis_url.get_secret_value()))
        try:
            ctx = WorkerContext(
                sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
                blobs=blobs,
                tools=Tools(settings.ffmpeg_bin, settings.ffprobe_bin),
                enqueuer=DramatiqEnqueuer(broker),
                settings=settings,
                publisher=publisher,
            )
            await body(ctx)
        finally:
            publisher.close()
            await engine.dispose()

    asyncio.run(go())


def register_failure_hook(broker: dramatiq.Broker, settings: Settings) -> None:
    """Retries exhausted: `services.pipeline_failure.job_died` ends the job, fails the project."""

    def pipeline_failed(message_data: dict[str, Any], _exception_data: dict[str, Any]) -> None:
        job_id, user_id = (UUID(a) for a in message_data["args"])

        async def run() -> None:
            engine = create_async_engine(
                settings.database_url.get_secret_value(), poolclass=NullPool
            )
            publisher = EventPublisher(sync=Redis.from_url(settings.redis_url.get_secret_value()))
            try:
                async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                    await job_died(session, publisher, user_id, job_id)
            finally:
                publisher.close()
                await engine.dispose()

        asyncio.run(run())
        log.error("job.dead", job_id=str(job_id))

    dramatiq.actor(
        broker=broker,
        actor_name=FAILED_ACTOR,
        queue_name=JobQueue.MAINTENANCE.value,
        max_retries=MAX_RETRIES,
        min_backoff=MIN_BACKOFF_MS,
        max_backoff=MAX_BACKOFF_MS,
        time_limit=60_000,
    )(pipeline_failed)
