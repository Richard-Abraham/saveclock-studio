"""Retention and housekeeping (ARCH §4, §9; plan 008): the single owner of what is swept.

Sweeps are maintenance actors, not job rows (P8-1): they log, take a Redis lock and never touch a
project that has a queued or running job. What is kept for good: `songs/`, plans, analyses and
`renders/` (with Mode A). What is intermediate: all of `work/{pid}/`. Everything of a `deleted`
project goes through `purge_project`, which deletes nothing for any other status.

`dry_run=True` reports what would go and deletes nothing (the first run on a real volume).
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import structlog
from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.queue import STAGE_ACTOR, Enqueuer
from saveclock.config import STUCK_QUEUED_S, STUCK_RUNNING_S
from saveclock.errors import Conflict, ConflictReason, NotFound, ValidationFailed
from saveclock.models import JobStage, Project, ProjectStatus
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.renders import RenderRepository
from saveclock.services.context import WorkerContext
from saveclock.services.pipeline_failure import job_died

log = structlog.get_logger()

LOCK_KEY = "housekeeping:lock"
LOCK_TTL_S = 600
ORPHANS_SEEN_KEY = "orphans:seen"
ORPHANS_SEEN_TTL_S = 10 * 86400
REAPED_TTL_S = 86400
MAX_RESENDS = 2
KEY_PARTS = 3  # songs/{pid}/{name}
DIR_DEPTH = 2  # a blob key under a project or render directory has at least two slashes
ABANDONED_UPLOAD_H = 24
JOB_RETENTION_DAYS = 90
AUDIT_GRACE = timedelta(hours=1)
# a project in one of these has no upload in flight, so its `incoming.bin` is leftover
_NO_UPLOAD = (
    ProjectStatus.CREATED.value,
    ProjectStatus.REJECTED.value,
    ProjectStatus.CANCELED.value,
)

Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


class PurgeBusy(Exception):
    """A job of the deleted project is still queued or running: the purge actor retries."""


@dataclass
class SweepReport:
    freed_bytes: int = 0
    projects: list[UUID] = field(default_factory=list)
    purged: list[UUID] = field(default_factory=list)
    dry_run: bool = False


async def sweep_intermediates(
    ctx: WorkerContext,
    user_id: UUID,
    *,
    project_id: UUID | None = None,
    dry_run: bool = False,
    clock: Clock = utcnow,
) -> SweepReport:
    """Remove `work/{pid}` of every project idle for more than the TTL and without an active job
    (or of `project_id` right now, ignoring the TTL), then purge every project in `deleted`."""
    report = SweepReport(dry_run=dry_run)
    cutoff = clock() - timedelta(days=ctx.settings.intermediate_ttl_days)
    async with ctx.sessionmaker() as session:
        projects = ProjectRepository(session)
        if project_id is not None:
            one = await projects.get(user_id=user_id, project_id=project_id)
            live = one is not None and one.status != ProjectStatus.DELETED.value
            due: Sequence[Project] = [one] if one is not None and live else []
        else:
            due = await projects.sweep_candidates(user_id=user_id, cutoff=cutoff)
        for project in due:
            # re-check right before deleting: a job may have started since the query
            if await projects.has_active_job(user_id=user_id, project_id=project.id):
                continue
            prefix = f"work/{project.id}"
            if dry_run:
                report.freed_bytes += await asyncio.to_thread(ctx.blobs.usage, prefix)
            else:
                report.freed_bytes += await asyncio.to_thread(ctx.blobs.delete_prefix, prefix)
                await projects.mark_intermediates_purged(user_id=user_id, project_id=project.id)
                await session.commit()
            report.projects.append(project.id)
        deleted = await projects.list_deleted(user_id=user_id)
    for project in deleted:
        if dry_run:
            report.purged.append(project.id)
            continue
        try:
            await purge_project(ctx, user_id, project.id)
        except PurgeBusy:
            log.info("purge.waiting", project_id=str(project.id))
        except Exception:
            log.exception("housekeeping.purge_failed", project_id=str(project.id))
        else:
            report.purged.append(project.id)
    log.info(
        "housekeeping.swept",
        freed_bytes=report.freed_bytes,
        projects=len(report.projects),
        purged=len(report.purged),
        dry_run=dry_run,
    )
    return report


async def purge_project(ctx: WorkerContext, user_id: UUID, project_id: UUID) -> None:
    """A `deleted` project: render ids from the database first, then every blob prefix, then the
    row (children cascade). Idempotent. A live project (any other status) is never touched."""
    async with ctx.sessionmaker() as session:
        projects = ProjectRepository(session)
        project = await projects.get(user_id=user_id, project_id=project_id)
        if project is None or project.status != ProjectStatus.DELETED.value:
            return
        if await projects.has_active_job(user_id=user_id, project_id=project_id):
            raise PurgeBusy(str(project_id))
        render_ids = await RenderRepository(session).ids_of_project(
            user_id=user_id, project_id=project_id
        )
        prefixes = [f"songs/{project_id}", f"work/{project_id}"]
        prefixes += [f"renders/{rid}" for rid in render_ids]
        for prefix in prefixes:
            await asyncio.to_thread(ctx.blobs.delete_prefix, prefix)
        await projects.hard_delete(user_id=user_id, project_id=project_id)
        await session.commit()
    log.info("project.purged", project_id=str(project_id), renders=len(render_ids))


async def reap_abandoned_uploads(
    ctx: WorkerContext, user_id: UUID, *, dry_run: bool = False, clock: Clock = utcnow
) -> int:
    """`songs/*/incoming.bin.part` older than 24 h, and an `incoming.bin` older than 24 h whose
    project has no upload in flight (created, rejected, canceled). Returns the bytes freed."""
    limit = (clock() - timedelta(hours=ABANDONED_UPLOAD_H)).timestamp()
    freed = 0
    keys = await asyncio.to_thread(ctx.blobs.list, "songs")
    async with ctx.sessionmaker() as session:
        idle = {
            str(p.id)
            for p in await ProjectRepository(session).list_with_status(
                user_id=user_id, statuses=_NO_UPLOAD
            )
        }
    for key in keys:
        parts = key.split("/")
        if len(parts) != KEY_PARTS:
            continue
        name = parts[2]
        if name != "incoming.bin.part" and not (name == "incoming.bin" and parts[1] in idle):
            continue
        info = await asyncio.to_thread(ctx.blobs.stat, key)
        if info.mtime >= limit:
            continue
        freed += info.size
        if not dry_run:
            await asyncio.to_thread(ctx.blobs.delete, key)
    log.info("housekeeping.uploads_reaped", freed_bytes=freed, dry_run=dry_run)
    return freed


async def reap_stuck_jobs(
    ctx: WorkerContext, user_id: UUID, redis: Redis, *, clock: Clock = utcnow
) -> list[UUID]:
    """Re-send a job that sat `queued` or `running` past its threshold (the broker lost it).
    At most two re-sends per job (Redis counter, one day); after that the job is dead and its
    project fails (`job_died`). Postgres is the record (ARCH §8).

    shortcut: a legitimate backlog older than STUCK_QUEUED_S can produce one duplicate message; the
    actors' `begin()` guards make a duplicate of a finished job a no-op and the actors are
    idempotent, upgrade to a broker-side queue-length check if duplicates are ever seen.
    """
    now = clock()
    touched: list[UUID] = []
    async with ctx.sessionmaker() as session:
        jobs = await JobRepository(session).stuck(
            user_id=user_id,
            queued_before=now - timedelta(seconds=STUCK_QUEUED_S),
            running_before=now - timedelta(seconds=STUCK_RUNNING_S),
        )
    for job in jobs:
        actor = STAGE_ACTOR.get(JobStage(job.stage))
        key = f"reaped:{job.id}"
        count = int(await asyncio.to_thread(redis.incr, key))
        await asyncio.to_thread(redis.expire, key, REAPED_TTL_S)
        async with ctx.sessionmaker() as session:
            if actor is None or count > MAX_RESENDS:
                await job_died(session, ctx.publisher, user_id, job.id)
                log.error("job.reaped_dead", job_id=str(job.id), stage=job.stage)
            else:
                await JobRepository(session).touch_resent(user_id=user_id, job_id=job.id)
                await session.commit()
                await asyncio.to_thread(ctx.enqueuer.send, actor, str(job.id), str(user_id))
                log.warning("job.resent", job_id=str(job.id), stage=job.stage, resend=count)
        touched.append(job.id)
    return touched


async def reconcile_orphans(
    ctx: WorkerContext, user_id: UUID, redis: Redis, *, dry_run: bool = False
) -> dict[str, list[str]]:
    """Blob directories whose project (or render) row does not exist. Found, reported, and
    removed only on the second consecutive sighting (Redis set, 10 days). Ids of every user count
    as known: the blob root is shared, so `user_id` only names who asked."""
    async with ctx.sessionmaker() as session:
        project_ids = {str(i) for i in await ProjectRepository(session).list_all_ids()}
        render_ids = {str(i) for i in await RenderRepository(session).list_all_ids()}
    known = {"songs": project_ids, "work": project_ids, "renders": render_ids}
    report: dict[str, list[str]] = {"seen": [], "removed": []}
    for top, ids in known.items():
        keys = await asyncio.to_thread(ctx.blobs.list, top)
        dirs = {k.split("/")[1] for k in keys if k.count("/") >= DIR_DEPTH}
        for name in sorted(dirs - ids):
            prefix = f"{top}/{name}"
            seen = await asyncio.to_thread(redis.sismember, ORPHANS_SEEN_KEY, prefix)
            if seen and not dry_run:
                await asyncio.to_thread(ctx.blobs.delete_prefix, prefix)
                await asyncio.to_thread(redis.srem, ORPHANS_SEEN_KEY, prefix)
                report["removed"].append(prefix)
            else:
                if not dry_run:
                    await asyncio.to_thread(redis.sadd, ORPHANS_SEEN_KEY, prefix)
                    await asyncio.to_thread(redis.expire, ORPHANS_SEEN_KEY, ORPHANS_SEEN_TTL_S)
                report["seen"].append(prefix)
    log.info("housekeeping.orphans", seen=len(report["seen"]), removed=len(report["removed"]))
    return report


async def prune_jobs(ctx: WorkerContext, user_id: UUID, *, clock: Clock = utcnow) -> int:
    """Delete terminal `jobs` rows that finished more than 90 days ago."""
    older_than = clock() - timedelta(days=JOB_RETENTION_DAYS)
    async with ctx.sessionmaker() as session:
        deleted = await JobRepository(session).prune_finished(
            user_id=user_id, older_than=older_than
        )
        await session.commit()
    log.info("housekeeping.jobs_pruned", deleted=deleted)
    return deleted


async def audit_stale(ctx: WorkerContext, user_id: UUID, *, clock: Clock = utcnow) -> list[str]:
    """The ROADMAP audit: `work/` prefixes of projects that should already have been swept (idle
    more than the TTL plus an hour, no active job, not purged). Empty after a sweep."""
    cutoff = clock() - timedelta(days=ctx.settings.intermediate_ttl_days) - AUDIT_GRACE
    async with ctx.sessionmaker() as session:
        stale = await ProjectRepository(session).sweep_candidates(user_id=user_id, cutoff=cutoff)
    return [f"work/{p.id}" for p in stale]


Scope = Literal["intermediates", "abandoned_uploads", "all"]


async def request_run(
    session: AsyncSession,
    redis: AsyncRedis,
    enqueuer: Enqueuer,
    user_id: UUID,
    *,
    scope: Scope,
    project_id: UUID | None,
) -> list[str]:
    """`POST /housekeeping/run` (#23): checks, then sends the actors; returns the actor names.

    409 `job_active` while a sweep holds the lock, or when `project_id` has a queued or running
    job (its intermediates are in use); 404 for a project that is not the user's; 422 for a
    `project_id` with any scope but `intermediates`."""
    if project_id is not None and scope != "intermediates":
        raise ValidationFailed("project_id_needs_intermediates")
    if project_id is not None:
        projects = ProjectRepository(session)
        project = await projects.get(user_id=user_id, project_id=project_id)
        if project is None or project.status == ProjectStatus.DELETED.value:
            raise NotFound
        if await projects.has_active_job(user_id=user_id, project_id=project_id):
            raise Conflict(ConflictReason.JOB_ACTIVE)
    if await redis.exists(LOCK_KEY):
        raise Conflict(ConflictReason.JOB_ACTIVE)
    sent: list[str] = []
    if scope in {"intermediates", "all"}:
        args = (str(user_id), str(project_id) if project_id else "")
        await asyncio.to_thread(enqueuer.send, "sweep_intermediates", *args)
        sent.append("sweep_intermediates")
    if scope in {"abandoned_uploads", "all"}:
        await asyncio.to_thread(enqueuer.send, "reap_orphans", str(user_id), "uploads")
        sent.append("reap_orphans")
    return sent
