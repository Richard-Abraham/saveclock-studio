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
from saveclock.models import JobQueue, JobStage, ProjectStatus
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.plans import PlanRepository
from saveclock.services import project_state
from saveclock.services.context import WorkerContext
from saveclock.services.plans import restore_keywords_override
from saveclock.services.render_job import render_job_died

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
) -> dict[str, Any]:
    return {
        "queue_name": queue.value,
        "max_retries": max_retries,
        "min_backoff": min_backoff_ms,
        "max_backoff": max_backoff_ms,
        "time_limit": time_limit_ms,
        "on_retry_exhausted": FAILED_ACTOR,
    }


def run_with_context(
    settings: Settings,
    broker: dramatiq.Broker,
    blobs: FilesystemBlobStore,
    body: Any,  # noqa: ANN401
) -> None:
    """One event loop and one NullPool engine per message (the stub's shortcut, kept)."""

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
    """Retries exhausted: the job is dead and the project failed (`validating|analyzing` only).
    A render or remux job also ends its render (`services.render_job.render_job_died`)."""

    def pipeline_failed(message_data: dict[str, Any], _exception_data: dict[str, Any]) -> None:
        job_id, user_id = (UUID(a) for a in message_data["args"])

        async def run() -> None:
            engine = create_async_engine(
                settings.database_url.get_secret_value(), poolclass=NullPool
            )
            publisher = EventPublisher(sync=Redis.from_url(settings.redis_url.get_secret_value()))
            try:
                async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                    jobs = JobRepository(session)
                    job = await jobs.get(user_id=user_id, job_id=job_id)
                    await jobs.mark_dead(user_id=user_id, job_id=job_id)
                    if job is not None and job.project_id is not None:
                        planned = (
                            await PlanRepository(session).latest(
                                user_id=user_id, project_id=job.project_id
                            )
                            is not None
                        )
                        # a replan that dies keeps the plan the owner had (and drops its keywords)
                        planning_to = (
                            ProjectStatus.DRAFT_READY if planned else ProjectStatus.FAILED_PLAN
                        )
                        for from_, to in (
                            (ProjectStatus.VALIDATING, ProjectStatus.FAILED_ANALYSIS),
                            (ProjectStatus.ANALYZING, ProjectStatus.FAILED_ANALYSIS),
                            (ProjectStatus.PLANNING, planning_to),  # the draft job
                        ):
                            moved = await project_state.transition(
                                session,
                                publisher,
                                user_id=user_id,
                                project_id=job.project_id,
                                from_=from_.value,
                                to=to.value,
                                reason="retries_exhausted",
                                commit=False,
                            )
                            if moved and planned and to is ProjectStatus.DRAFT_READY:
                                await restore_keywords_override(session, user_id, job.project_id)
                    if job is not None and job.stage in {
                        JobStage.RENDER.value,
                        JobStage.REMUX.value,
                    }:
                        await render_job_died(session, publisher, user_id, job)  # plan 007
                    await session.commit()
                    await project_state.announce_pending(session, publisher)
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
