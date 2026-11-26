"""The `render_master` actor: a thin wrapper around `services.render_job.render_master`.

One retry (ARCH §8 render queue): a failed verification gets one more try with a fresh scratch
directory, then the shared failure hook ends the render. The render is found through
`jobs.render_id`, never through a render id in the message.
"""

from uuid import UUID

import dramatiq

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.queue import ACTORS
from saveclock.config import RENDER_LIMIT_S, Settings
from saveclock.services.context import WorkerContext
from saveclock.services.render_job import render_master
from saveclock.workers.pipeline import actor_options, run_with_context

TIME_LIMIT_MS = RENDER_LIMIT_S * 1000
RENDER_RETRIES = 1


def register_render_actors(broker: dramatiq.Broker, settings: Settings) -> None:
    blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)

    def actor(job_id: str, user_id: str) -> None:
        async def body(ctx: WorkerContext) -> None:
            await render_master(ctx, UUID(user_id), UUID(job_id))

        run_with_context(settings, broker, blobs, body)

    dramatiq.actor(
        broker=broker,
        actor_name="render_master",
        **actor_options(ACTORS["render_master"], TIME_LIMIT_MS, max_retries=RENDER_RETRIES),
    )(actor)
