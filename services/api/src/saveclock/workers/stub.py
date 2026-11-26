"""The four stub actors, one per queue. Phase 2 deletes this file with services/stub.py.

Messages carry ids only (job_id, user_id). Delivery is at-least-once, so every step is
idempotent: `begin` refuses a finished job, the next hop is an ON CONFLICT insert, the blob
write replaces. Order of the finishing steps is deliberate: create the next row, send the next
message, mark this job ok. A crash in between re-runs this hop and re-sends (harmless).
"""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import dramatiq
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.blob_keys import stub_key
from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.config import Settings
from saveclock.models import JobQueue
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.services.stub import HOPS, next_job_id

log = structlog.get_logger()

# Explicit on every actor: nothing relies on Dramatiq's defaults (20 retries, 10 min).
MAX_RETRIES = 2
MIN_BACKOFF_MS = 5_000
MAX_BACKOFF_MS = 30_000
TIME_LIMIT_MS = {
    JobQueue.ANALYSIS: 120_000,
    JobQueue.FETCH: 120_000,
    JobQueue.RENDER: 120_000,
    JobQueue.MAINTENANCE: 60_000,
}


@dataclass(frozen=True)
class StubActors:
    by_queue: dict[JobQueue, "dramatiq.Actor[..., None]"]
    failed: "dramatiq.Actor[..., None]"

    def send_first(self, job_id: UUID, user_id: UUID) -> None:
        self.by_queue[HOPS[0][0]].send(str(job_id), str(user_id))


@asynccontextmanager
async def _session(settings: Settings) -> AsyncIterator[AsyncSession]:
    # shortcut: one NullPool engine per call, fine at stub volumes; upgrade to a worker-owned
    # event loop with a shared pool when real jobs run often.
    engine = create_async_engine(settings.database_url.get_secret_value(), poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
            await session.commit()
    finally:
        await engine.dispose()


def register_stub_actors(broker: dramatiq.Broker, settings: Settings) -> StubActors:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)
    by_queue: dict[JobQueue, dramatiq.Actor[..., None]] = {}

    async def begin(user_id: UUID, job_id: UUID) -> dict[str, Any] | None:
        async with _session(settings) as session:
            job = await JobRepository(session).begin(user_id=user_id, job_id=job_id)
            if job is None or job.project_id is None:
                # Not the user's job (SEC-020) or already finished.
                await JobRepository(session).reject_foreign(user_id=user_id, job_id=job_id)
                return None
            project = await ProjectRepository(session).get(
                user_id=user_id, project_id=job.project_id
            )
            if project is None:
                return None
            return {
                "project_id": project.id,
                "sleep_s": int(project.options.get("stub_sleep_s", 0)),
                "root": UUID(project.options["stub_job_id"]),
            }

    async def enqueue_next(
        user_id: UUID, job_id: UUID, project_id: UUID, next_queue: JobQueue
    ) -> UUID:
        next_id = next_job_id(job_id, next_queue)
        stage = dict(HOPS)[next_queue]
        async with _session(settings) as session:
            await JobRepository(session).create(
                user_id=user_id,
                project_id=project_id,
                job_id=next_id,
                stage=stage.value,
                queue=next_queue.value,
            )
        return next_id

    async def finish(user_id: UUID, job_id: UUID, run_ms: int) -> None:
        async with _session(settings) as session:
            await JobRepository(session).finish(user_id=user_id, job_id=job_id, run_ms=run_ms)

    def make_body(queue: JobQueue, next_queue: JobQueue | None) -> Any:  # noqa: ANN401
        def body(job_id: str, user_id: str) -> None:
            jid, uid = UUID(job_id), UUID(user_id)
            started = time.monotonic()
            begun = asyncio.run(begin(uid, jid))
            if begun is None:
                return
            if begun["sleep_s"]:
                time.sleep(begun["sleep_s"])
            if queue is JobQueue.RENDER:
                root = begun["root"]
                blobs.put(stub_key(root), iter([f"stub job {root}\n".encode()]), max_bytes=1024)
            if next_queue is not None:
                next_id = asyncio.run(enqueue_next(uid, jid, begun["project_id"], next_queue))
                by_queue[next_queue].send(str(next_id), user_id)
            asyncio.run(finish(uid, jid, int((time.monotonic() - started) * 1000)))

        body.__name__ = f"stub_{queue.value}"
        return body

    def mark_dead(message_data: dict[str, Any], _exception_data: dict[str, Any]) -> None:
        job_id, user_id = message_data["args"]

        async def run() -> None:
            async with _session(settings) as session:
                await JobRepository(session).mark_dead(user_id=UUID(user_id), job_id=UUID(job_id))

        asyncio.run(run())
        log.error("job.dead", job_id=job_id)

    failed = dramatiq.actor(
        broker=broker,
        actor_name="stub_failed",
        queue_name=JobQueue.MAINTENANCE.value,
        max_retries=MAX_RETRIES,
        min_backoff=MIN_BACKOFF_MS,
        max_backoff=MAX_BACKOFF_MS,
        time_limit=TIME_LIMIT_MS[JobQueue.MAINTENANCE],
    )(mark_dead)
    queues = [q for q, _ in HOPS]
    for i, queue in enumerate(queues):
        nxt = queues[i + 1] if i + 1 < len(queues) else None
        by_queue[queue] = dramatiq.actor(
            broker=broker,
            actor_name=f"stub_{queue.value}",
            queue_name=queue.value,
            max_retries=MAX_RETRIES,
            min_backoff=MIN_BACKOFF_MS,
            max_backoff=MAX_BACKOFF_MS,
            time_limit=TIME_LIMIT_MS[queue],
            on_retry_exhausted="stub_failed",
        )(make_body(queue, nxt))
    return StubActors(by_queue=by_queue, failed=failed)
