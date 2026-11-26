"""The `remux_with_song` actor (Mode A): a thin wrapper around `services.render_job`.

Shares the worker's threads with the render, analysis and fetch actors (P7-5): a remux can queue
behind a render, which is accepted.
"""

from uuid import UUID

import dramatiq

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.queue import ACTORS
from saveclock.config import REMUX_LIMIT_S, Settings
from saveclock.services.context import WorkerContext
from saveclock.services.render_job import remux_with_song
from saveclock.workers.pipeline import actor_options, run_with_context

TIME_LIMIT_MS = REMUX_LIMIT_S * 1000
REMUX_RETRIES = 1


def register_remux_actor(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def actor(job_id: str, user_id: str) -> None:
        async def body(ctx: WorkerContext) -> None:
            await remux_with_song(ctx, UUID(user_id), UUID(job_id))

        run_with_context(settings, broker, blobs, body)

    dramatiq.actor(
        broker=broker,
        actor_name="remux_with_song",
        **actor_options(ACTORS["remux_with_song"], TIME_LIMIT_MS, max_retries=REMUX_RETRIES),
    )(actor)
