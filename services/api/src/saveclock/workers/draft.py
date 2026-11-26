"""The `build_draft` and `replan` actors: thin wrappers around `services.draft.run_draft`.

Both run the same body (a replan only differs in what it starts from). Retries follow ARCH §8 for
the fetch queue: 3 retries, backoff 2 s to 60 s, because every stage is idempotent; an exhausted
job is ended by the shared failure hook.
"""

from uuid import UUID

import dramatiq

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.queue import ACTORS
from saveclock.config import DRAFT_LIMIT_S, Settings
from saveclock.services.context import WorkerContext
from saveclock.services.draft import Mode, run_draft
from saveclock.workers.pipeline import actor_options, run_with_context

TIME_LIMIT_MS = DRAFT_LIMIT_S * 1000
DRAFT_RETRIES = 3
DRAFT_MIN_BACKOFF_MS = 2_000
DRAFT_MAX_BACKOFF_MS = 60_000


def register_draft_actors(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def make(name: str, mode: Mode) -> None:
        def actor(job_id: str, user_id: str) -> None:
            async def body(ctx: WorkerContext) -> None:
                await run_draft(ctx, UUID(job_id), UUID(user_id), mode=mode)

            run_with_context(settings, broker, blobs, body)

        dramatiq.actor(
            broker=broker,
            actor_name=name,
            **actor_options(
                ACTORS[name],
                TIME_LIMIT_MS,
                max_retries=DRAFT_RETRIES,
                min_backoff_ms=DRAFT_MIN_BACKOFF_MS,
                max_backoff_ms=DRAFT_MAX_BACKOFF_MS,
            ),
        )(actor)

    make("build_draft", "draft")
    make("replan", "replan")
