"""What a worker job needs, handed to the services as one object (no globals)."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saveclock.adapters.blobstore.port import BlobStore
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import Enqueuer
from saveclock.config import Settings
from saveclock.domain.ids import derive_job_id
from saveclock.models import JobQueue, JobStage
from saveclock.repositories.jobs import JobRepository

CANCEL_CHECK_TIMEOUT_S = 10


@dataclass(frozen=True)
class WorkerContext:
    sessionmaker: async_sessionmaker[AsyncSession]
    blobs: BlobStore
    tools: Tools
    enqueuer: Enqueuer
    settings: Settings


async def hand_off(
    ctx: WorkerContext,
    user_id: UUID,
    job_id: UUID,
    *,
    project_id: UUID,
    next_stage: JobStage,
    next_queue: JobQueue,
    actor: str,
    timings: dict[str, Any],
) -> None:
    """Create the next job, send its message, then mark this job ok (in that order).

    Every step is idempotent (ON CONFLICT insert, a derived id), so a crash anywhere in here is
    repaired by the redelivery of this job's own message.
    """
    next_id = derive_job_id(job_id, next_stage.value)
    async with ctx.sessionmaker() as session:
        jobs = JobRepository(session)
        await jobs.create(
            user_id=user_id,
            project_id=project_id,
            job_id=next_id,
            stage=next_stage.value,
            queue=next_queue.value,
        )
        await session.commit()  # the next worker must see the row before the message exists
        await asyncio.to_thread(ctx.enqueuer.send, actor, str(next_id), str(user_id))
        await jobs.finish_with(user_id=user_id, job_id=job_id, timings=timings)
        await session.commit()


async def end_unwanted(ctx: WorkerContext, user_id: UUID, job_id: UUID) -> None:
    """The project is gone or was canceled: nothing to do, the job just ends."""
    async with ctx.sessionmaker() as session:
        await JobRepository(session).fail(user_id=user_id, job_id=job_id, error_code="canceled")
        await session.commit()


def cancel_probe(ctx: WorkerContext, user_id: UUID, job_id: UUID) -> Callable[[], bool]:
    """A synchronous `cancel()` for worker threads: asks the database on the running event loop.

    Call it only from a thread started with `asyncio.to_thread` while the loop is awaiting it.
    """
    loop = asyncio.get_running_loop()

    async def check() -> bool:
        async with ctx.sessionmaker() as session:
            return await JobRepository(session).cancel_requested(user_id=user_id, job_id=job_id)

    def probe() -> bool:
        return asyncio.run_coroutine_threadsafe(check(), loop).result(CANCEL_CHECK_TIMEOUT_S)

    return probe
