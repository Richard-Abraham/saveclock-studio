import os
import stat
import time
from pathlib import Path
from uuid import uuid4

import pytest

from saveclock.services.scratch import scratch_dir, sweep_stale


def test_the_directory_is_private_and_removed_afterwards(tmp_path: Path) -> None:
    job = uuid4()
    with scratch_dir(tmp_path / "s", job) as path:
        assert path == tmp_path / "s" / str(job)
        assert stat.S_IMODE(path.stat().st_mode) == 0o700
        (path / "x.flac").write_bytes(b"data")
    assert not path.exists()


def test_it_is_removed_when_the_job_fails(tmp_path: Path) -> None:
    holder: list[Path] = []

    def fail() -> None:
        with scratch_dir(tmp_path, uuid4()) as path:
            holder.append(path)
            raise RuntimeError

    with pytest.raises(RuntimeError):
        fail()
    assert not holder[0].exists()


def test_stale_directories_are_swept_and_fresh_ones_kept(tmp_path: Path) -> None:
    old, fresh = tmp_path / "old", tmp_path / "fresh"
    old.mkdir()
    fresh.mkdir()
    (tmp_path / "file.txt").write_text("not a directory")
    past = time.time() - 7200
    os.utime(old, (past, past))
    assert sweep_stale(tmp_path) == 1
    assert not old.exists()
    assert fresh.exists()
    assert sweep_stale(tmp_path / "missing") == 0
