"""A named PLACEHOLDER for `build_draft`: plan 006 replaces the body and deletes this file.

It marks its job `ok` with `timings.placeholder = true` and leaves the project in `planning`.
"""

import time
from uuid import UUID

import dramatiq

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.queue import ACTORS
from saveclock.config import Settings
from saveclock.repositories.jobs import JobRepository
from saveclock.services.context import WorkerContext
from saveclock.workers.pipeline import actor_options, run_with_context

TIME_LIMIT_MS = 60_000


def register_draft_placeholder(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def build_draft(job_id: str, user_id: str) -> None:  # the placeholder body
        async def body(ctx: WorkerContext) -> None:
            started = time.monotonic()
            async with ctx.sessionmaker() as session:
                jobs = JobRepository(session)
                if await jobs.begin(user_id=UUID(user_id), job_id=UUID(job_id)) is None:
                    await jobs.reject_foreign(user_id=UUID(user_id), job_id=UUID(job_id))
                else:
                    await jobs.finish_with(
                        user_id=UUID(user_id),
                        job_id=UUID(job_id),
                        timings={
                            "placeholder": True,
                            "run_ms": int((time.monotonic() - started) * 1000),
                        },
                    )
                await session.commit()

        run_with_context(settings, broker, blobs, body)

    dramatiq.actor(
        broker=broker,
        actor_name="build_draft",
        **actor_options(ACTORS["build_draft"], TIME_LIMIT_MS),
    )(build_draft)
