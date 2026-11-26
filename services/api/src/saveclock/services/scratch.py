"""Per-job scratch directories (SEC-023): `SCRATCH_ROOT/{job_id}`, 0700, removed in `finally`."""

import shutil
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

STALE_AFTER_S = 3600


@contextmanager
def scratch_dir(root: str | Path, job_id: UUID) -> Iterator[Path]:
    path = Path(root) / str(job_id)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def sweep_stale(root: str | Path, max_age_s: float = STALE_AFTER_S) -> int:
    """Remove job directories a killed worker left behind (run at worker start)."""
    base = Path(root)
    if not base.is_dir():
        return 0
    removed = 0
    for child in base.iterdir():
        if (
            child.is_dir()
            and not child.is_symlink()
            and time.time() - child.stat().st_mtime > max_age_s
        ):
            shutil.rmtree(child, ignore_errors=True)
            removed += 1
    return removed
