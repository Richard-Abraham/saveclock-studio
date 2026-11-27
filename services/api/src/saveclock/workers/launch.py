"""Worker launcher: `python -m saveclock.workers.launch --queues analysis fetch render`.

The one place that turns the tuning into a Dramatiq command line (P8-3): the thread count and the
library thread variables come from `get_tuning`, not from a constant written in compose.
"""

import argparse
import os
import sys

import structlog

from saveclock.config import Settings
from saveclock.models import JobQueue
from saveclock.observability.logging import configure_logging
from saveclock.services.tuning import get_tuning

log = structlog.get_logger()
_TORCH_QUEUES = {JobQueue.ANALYSIS.value, JobQueue.FETCH.value, JobQueue.RENDER.value}


def build_command(queues: list[str], threads: int) -> list[str]:
    return [
        "dramatiq",
        "saveclock.workers.main",
        "--processes",
        "1",
        "--threads",
        str(threads),
        "--queues",
        *queues,
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="saveclock.workers.launch")
    parser.add_argument("--queues", nargs="+", required=True)
    parser.add_argument("--threads", type=int, default=None)
    args = parser.parse_args(argv)
    known = {q.value for q in JobQueue}
    unknown = [q for q in args.queues if q not in known]
    if unknown:
        print(f"unknown queue(s): {', '.join(unknown)}", file=sys.stderr)
        sys.exit(2)
    settings = Settings()
    configure_logging(
        level=settings.log_level,
        env=settings.app_env,
        version=settings.app_version,
        service="launcher",
    )
    tuning = get_tuning(settings)
    # libraries read these two directly; TORCH_THREADS / FFMPEG_THREADS are left alone because the
    # child would read them back as overrides (GET /settings would show source=override)
    if _TORCH_QUEUES & set(args.queues) and tuning.torch_threads > 0:
        os.environ["OMP_NUM_THREADS"] = str(tuning.torch_threads)
        os.environ["MKL_NUM_THREADS"] = str(tuning.torch_threads)
    threads = args.threads if args.threads is not None else tuning.fetch_concurrency
    log.info("tuning.chosen", queues=args.queues, threads=threads, heavy=tuning.heavy)
    cmd = build_command(args.queues, threads)
    os.execvp(cmd[0], cmd)  # noqa: S606 - argument list, no shell


if __name__ == "__main__":
    main()
