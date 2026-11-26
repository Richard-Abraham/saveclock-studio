"""The `analyze_song` actor: a thin wrapper around `services.analysis.analyze_project`."""

from uuid import UUID

import dramatiq

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.queue import ACTORS
from saveclock.config import Settings
from saveclock.services.analysis import analyze_project
from saveclock.services.context import WorkerContext
from saveclock.workers.pipeline import actor_options, run_with_context

TIME_LIMIT_MS = 120_000


def register_analyze_actor(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def analyze_song(job_id: str, user_id: str) -> None:
        async def body(ctx: WorkerContext) -> None:
            await analyze_project(ctx, UUID(job_id), UUID(user_id))

        run_with_context(settings, broker, blobs, body)

    dramatiq.actor(
        broker=broker,
        actor_name="analyze_song",
        **actor_options(ACTORS["analyze_song"], TIME_LIMIT_MS),
    )(analyze_song)
