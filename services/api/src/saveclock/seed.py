"""`python -m saveclock.seed /seed/click.wav`: one analysed click-track project for a dev stack.

Local and CI only (refuses otherwise, exit 2). Idempotent: prints `exists` when a live project with
the seed title is there, else runs the real services in-process (upload, validate, analyze, draft)
with FAKE_ML and FAKE_STOCK and prints `created <project id>`. It creates no user: the owner row
comes from the migration. The WAV is written on the host by `eval/scripts/make_click_track.py`
(`scripts/seed.sh`), because `eval/` is not in the worker image.
"""

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.repositories.projects import ProjectRepository
from saveclock.services.analysis import analyze_project
from saveclock.services.context import WorkerContext
from saveclock.services.draft import run_draft
from saveclock.services.identity import OWNER_USER_ID
from saveclock.services.ingest import receive_upload, validate_song
from saveclock.services.projects import create_project

TITLE = "Seed: click track 128"
LOCAL_ENVS = frozenset({"local", "ci"})
CHUNK = 1 << 16
MAX_STEPS = 10  # validate, analyze, draft, with room for a hand-off more


async def _body(path: Path) -> AsyncIterator[bytes]:
    with path.open("rb") as fh:
        while chunk := await asyncio.to_thread(fh.read, CHUNK):
            yield chunk


async def seed(wav: Path, settings: Settings) -> str:
    engine = create_async_engine(settings.database_url.get_secret_value(), poolclass=NullPool)
    try:
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        enqueuer = FakeEnqueuer()
        blobs = FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb)
        ctx = WorkerContext(
            sessionmaker=sessionmaker,
            blobs=blobs,
            tools=Tools(settings.ffmpeg_bin, settings.ffprobe_bin),
            enqueuer=enqueuer,
            settings=settings,
        )
        async with sessionmaker() as session:
            for project in await ProjectRepository(session).list_all(user_id=OWNER_USER_ID):
                if project.title == TITLE:
                    return "exists"
            project = await create_project(session, OWNER_USER_ID, TITLE, {})
            await receive_upload(
                session,
                user_id=OWNER_USER_ID,
                project_id=project.id,
                content_length=str(await asyncio.to_thread(lambda: wav.stat().st_size)),
                content_type="audio/wav",
                x_filename="click.wav",
                body=_body(wav),
                blobs=blobs,
                enqueuer=enqueuer,
                settings=settings,
            )
        steps = {"validate_audio": validate_song, "analyze_song": analyze_project}
        for _ in range(MAX_STEPS):
            if not enqueuer.sent:
                break
            actor, (job_id, user_id) = enqueuer.sent.pop(0)
            if actor == "build_draft":
                await run_draft(ctx, UUID(job_id), UUID(user_id), mode="draft")
            else:
                await steps[actor](ctx, UUID(job_id), UUID(user_id))
        async with sessionmaker() as session:
            done = await ProjectRepository(session).get(
                user_id=OWNER_USER_ID, project_id=project.id
            )
        status = done.status if done is not None else "missing"
        if status != "draft_ready":
            msg = f"the seed project ended in {status}, not draft_ready"
            raise RuntimeError(msg)
        return f"created {project.id}"
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m saveclock.seed <click.wav>", file=sys.stderr)
        return 2
    if os.environ.get("APP_ENV") not in LOCAL_ENVS:  # before any fake is forced on
        print("the seed runs only with APP_ENV=local or ci", file=sys.stderr)
        return 2
    os.environ["FAKE_ML"] = "true"
    os.environ["FAKE_STOCK"] = "true"
    settings = Settings()
    print(asyncio.run(seed(Path(args[0]), settings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
