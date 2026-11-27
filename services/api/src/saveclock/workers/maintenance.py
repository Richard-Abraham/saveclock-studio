"""The maintenance actors (plan 008): thin wrappers around `services.housekeeping`.

Messages carry ids and literals only and every body re-checks ownership through the repositories.
`sweep_intermediates` and `reap_orphans` take the Redis lock `housekeeping:lock` (a second
concurrent run returns without work); `purge_project` and `prune_jobs` do not. These actors have
no `on_retry_exhausted` hook: that hook unpacks `(job_id, user_id)`, which these messages lack, and
the sweeper picks up whatever a purge left behind.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from uuid import UUID

import dramatiq
import structlog
from redis import Redis

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.queue import ACTORS
from saveclock.config import MAINT_LIMIT_S, PURGE_LIMIT_S, Settings
from saveclock.services import housekeeping
from saveclock.services.context import WorkerContext
from saveclock.workers.pipeline import actor_options, run_with_context

log = structlog.get_logger()

TIME_LIMIT_MS = MAINT_LIMIT_S * 1000
PURGE_TIME_LIMIT_MS = PURGE_LIMIT_S * 1000
MAINT_RETRIES = 5
LOCK_WAIT_S = 8  # shortcut: a fixed wait, upgrade to a queue of waiters if sweeps ever run long
LOCK_POLL_S = 0.25
WHAT = frozenset({"uploads", "stuck_jobs", "orphans", "all"})


async def _locked(redis: Redis, name: str, work: Callable[[], Awaitable[None]]) -> None:
    """Run `work()` under `housekeeping:lock`. Another sweep that is still running makes this one
    return without work, but a lock that is only briefly held (the periodic sender fires several
    actors at once) is waited for: LOCK_WAIT_S."""
    deadline = time.monotonic() + LOCK_WAIT_S
    while True:
        got = await asyncio.to_thread(
            redis.set, housekeeping.LOCK_KEY, name, nx=True, ex=housekeeping.LOCK_TTL_S
        )
        if got:
            break
        if time.monotonic() >= deadline:
            log.info("housekeeping.locked", actor=name)
            return
        await asyncio.sleep(LOCK_POLL_S)
    try:
        await work()
    finally:
        await asyncio.to_thread(redis.delete, housekeeping.LOCK_KEY)


def register_maintenance_actors(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def redis() -> Redis:
        return Redis.from_url(settings.redis_url.get_secret_value())

    def sweep_intermediates(user_id: str, project_id: str = "") -> None:
        async def body(ctx: WorkerContext) -> None:
            r = redis()
            try:

                async def work() -> None:
                    await housekeeping.sweep_intermediates(
                        ctx, UUID(user_id), project_id=UUID(project_id) if project_id else None
                    )

                await _locked(r, "sweep_intermediates", work)
            finally:
                r.close()

        run_with_context(settings, broker, blobs, body)

    def reap_orphans(user_id: str, what: str) -> None:
        if what not in WHAT:
            msg = f"unknown reap target {what!r}"
            raise ValueError(msg)

        async def body(ctx: WorkerContext) -> None:
            r = redis()
            uid = UUID(user_id)
            try:

                async def work() -> None:
                    if what in {"uploads", "all"}:
                        await housekeeping.reap_abandoned_uploads(ctx, uid)
                    if what in {"stuck_jobs", "all"}:
                        await housekeeping.reap_stuck_jobs(ctx, uid, r)
                    if what in {"orphans", "all"}:
                        await housekeeping.reconcile_orphans(ctx, uid, r)

                await _locked(r, f"reap_orphans:{what}", work)
            finally:
                r.close()

        run_with_context(settings, broker, blobs, body)

    def purge_project(user_id: str, project_id: str) -> None:
        async def body(ctx: WorkerContext) -> None:
            await housekeeping.purge_project(ctx, UUID(user_id), UUID(project_id))

        run_with_context(settings, broker, blobs, body)

    def prune_jobs(user_id: str) -> None:
        async def body(ctx: WorkerContext) -> None:
            await housekeeping.prune_jobs(ctx, UUID(user_id))

        run_with_context(settings, broker, blobs, body)

    for name, fn, limit in (
        ("sweep_intermediates", sweep_intermediates, TIME_LIMIT_MS),
        ("reap_orphans", reap_orphans, TIME_LIMIT_MS),
        ("purge_project", purge_project, PURGE_TIME_LIMIT_MS),
        ("prune_jobs", prune_jobs, TIME_LIMIT_MS),
    ):
        dramatiq.actor(
            broker=broker,
            actor_name=name,
            **actor_options(
                ACTORS[name], limit, max_retries=MAINT_RETRIES, on_retry_exhausted=None
            ),
        )(fn)
