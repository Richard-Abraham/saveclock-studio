"""The named stub job: one run through all four queues. Phase 2 deletes this file.

Greppable marker: every use of the word "stub" is a site Phase 2 removes.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.blobstore.blob_keys import stub_key
from saveclock.errors import NotFound
from saveclock.ids import new_id
from saveclock.models import Job, JobQueue, JobStage
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository

NAMESPACE = UUID("5a5e0000-0000-4000-8000-5ab000000001")
# hop order and stage values (plan 001 Step 8)
HOPS: tuple[tuple[JobQueue, JobStage], ...] = (
    (JobQueue.ANALYSIS, JobStage.ANALYZE),
    # not `draft`: uq_jobs_active (0002) allows one active draft/render per project, and hop 3 is
    # enqueued while hop 2 still runs (P4-14)
    (JobQueue.FETCH, JobStage.SWAP_NORMALIZE),
    (JobQueue.RENDER, JobStage.RENDER),
    (JobQueue.MAINTENANCE, JobStage.SWEEP),
)
MAX_SLEEP_S = 30

Enqueue = Callable[[UUID, UUID], None]


def next_job_id(job_id: UUID, next_queue: JobQueue) -> UUID:
    return uuid5(NAMESPACE, f"{job_id}:{next_queue.value}")


def chain_ids(root: UUID) -> list[UUID]:
    ids = [root]
    for queue, _ in HOPS[1:]:
        ids.append(next_job_id(ids[-1], queue))
    return ids


@dataclass(frozen=True)
class HopView:
    job_id: UUID
    queue: str
    stage: str
    state: str
    attempt: int
    run_ms: int | None


@dataclass(frozen=True)
class ChainView:
    job_id: UUID
    project_id: UUID
    hops: list[HopView]


async def create_stub_job(
    session: AsyncSession, user_id: UUID, sleep_s: int, enqueue: Enqueue
) -> tuple[UUID, UUID]:
    root = new_id()
    project = await ProjectRepository(session).create(
        user_id=user_id,
        title="stub",
        options={"stub_sleep_s": min(max(sleep_s, 0), MAX_SLEEP_S), "stub_job_id": str(root)},
    )
    queue, stage = HOPS[0]
    await JobRepository(session).create(
        user_id=user_id,
        project_id=project.id,
        job_id=root,
        stage=stage.value,
        queue=queue.value,
    )
    await session.commit()  # the worker must be able to see the rows before the message exists
    await asyncio.to_thread(enqueue, root, user_id)
    return root, project.id


async def get_chain(session: AsyncSession, user_id: UUID, root: UUID) -> ChainView:
    jobs = JobRepository(session)
    first: Job | None = await jobs.get(user_id=user_id, job_id=root)
    if first is None or first.project_id is None:
        raise NotFound
    ids = chain_ids(root)
    by_id = {j.id: j for j in await jobs.list_by_ids(user_id=user_id, job_ids=ids)}
    hops = []
    for job_id, (queue, stage) in zip(ids, HOPS, strict=True):
        j = by_id.get(job_id)
        hops.append(
            HopView(
                job_id=job_id,
                queue=queue.value,
                stage=stage.value,
                state=j.state if j else "pending",
                attempt=j.attempt if j else 0,
                run_ms=j.timings.get("run_ms") if j else None,
            )
        )
    return ChainView(job_id=root, project_id=first.project_id, hops=hops)


async def download_key(session: AsyncSession, user_id: UUID, root: UUID) -> str:
    """Owner-scoped: only the job's owner learns the blob key exists."""
    if await JobRepository(session).get(user_id=user_id, job_id=root) is None:
        raise NotFound
    return stub_key(root)
