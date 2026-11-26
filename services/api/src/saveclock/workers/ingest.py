"""The `validate_audio` actor: a thin wrapper around `services.ingest.validate_song`."""

from uuid import UUID

import dramatiq

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import CANONICALIZE_TIMEOUT_S, PROBE_TIMEOUT_S
from saveclock.adapters.queue import ACTORS
from saveclock.config import Settings
from saveclock.services.context import WorkerContext
from saveclock.services.ingest import validate_song
from saveclock.workers.pipeline import actor_options, run_with_context

# probe + the attached-picture probe + canonicalize, plus hashing and copying
TIME_LIMIT_MS = (2 * PROBE_TIMEOUT_S + CANONICALIZE_TIMEOUT_S + 60) * 1000


def register_validate_actor(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def validate_audio(job_id: str, user_id: str) -> None:
        async def body(ctx: WorkerContext) -> None:
            await validate_song(ctx, UUID(job_id), UUID(user_id))

        run_with_context(settings, broker, blobs, body)

    dramatiq.actor(
        broker=broker,
        actor_name="validate_audio",
        **actor_options(ACTORS["validate_audio"], TIME_LIMIT_MS),
    )(validate_audio)
