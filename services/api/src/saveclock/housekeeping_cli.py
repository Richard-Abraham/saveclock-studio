"""`python -m saveclock.housekeeping_cli --dry-run`: what the sweeper would remove, nothing deleted.

The first run on a real volume is this, from the worker container, followed by the owner's go
(plan 008 Rollback). It builds a context the way `workers/pipeline.py::run_with_context` does and
calls `services/housekeeping.py` with `dry_run=True`. The API has no dry-run switch.
"""

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from saveclock.adapters.blobstore.filesystem import FilesystemBlobStore
from saveclock.adapters.ffmpeg import Tools
from saveclock.adapters.queue import FakeEnqueuer
from saveclock.config import Settings
from saveclock.services import housekeeping
from saveclock.services.context import WorkerContext
from saveclock.services.identity import OWNER_USER_ID


async def dry_run(settings: Settings) -> housekeeping.SweepReport:
    engine = create_async_engine(settings.database_url.get_secret_value(), poolclass=NullPool)
    try:
        ctx = WorkerContext(
            sessionmaker=async_sessionmaker(engine, expire_on_commit=False),
            blobs=FilesystemBlobStore(settings.blob_root, settings.disk_low_watermark_gb),
            tools=Tools(settings.ffmpeg_bin, settings.ffprobe_bin),
            enqueuer=FakeEnqueuer(),
            settings=settings,
        )
        return await housekeeping.sweep_intermediates(ctx, OWNER_USER_ID, dry_run=True)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="saveclock.housekeeping_cli")
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args(argv)
    report = asyncio.run(dry_run(Settings()))
    print(
        f"dry run: {len(report.projects)} project(s) would lose intermediates, "
        f"{report.freed_bytes} bytes; {len(report.purged)} deleted project(s) would be purged"
    )
    for project_id in report.projects:
        print(f"  work/{project_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
