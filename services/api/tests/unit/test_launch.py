"""The launcher's argv and environment, observed through a recording stand-in for `dramatiq`."""

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_config import BASE

# a /bin/sh shebang: the interpreter path of this checkout contains spaces, a shebang cannot
RECORDER = """#!/bin/sh
exec "{python}" -c '
import json, os, sys
env = {{k: v for k, v in os.environ.items() if k.endswith("_THREADS")}}
print(json.dumps({{"argv": sys.argv[1:], "env": env}}))
' "$@"
"""


def launch(tmp_path: Path, *args: str, **env: str) -> subprocess.CompletedProcess[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "dramatiq"
    fake.write_text(RECORDER.format(python=sys.executable))
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    clean = {
        k: v
        for k, v in os.environ.items()
        if not k.endswith("_THREADS") and k not in {"FETCH_CONCURRENCY", "WORKER_HEAVY_CONCURRENCY"}
    }
    merged = {**clean, **BASE, "PATH": f"{bindir}{os.pathsep}{clean['PATH']}", **env}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "saveclock.workers.launch", *args],
        env=merged,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def recorded(done: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    assert done.returncode == 0, done.stderr
    got: dict[str, Any] = json.loads(done.stdout.strip().splitlines()[-1])
    return got


def threads_of(got: dict[str, Any]) -> str:
    value: str = got["argv"][got["argv"].index("--threads") + 1]
    return value


@pytest.mark.unit
def test_default_threads_come_from_the_tuning(tmp_path: Path) -> None:
    got = recorded(launch(tmp_path, "--queues", "analysis", "fetch", "render"))
    assert got["argv"] == [
        "saveclock.workers.main", "--processes", "1", "--threads", "4",
        "--queues", "analysis", "fetch", "render",
    ]  # fmt: skip
    assert got["env"]["OMP_NUM_THREADS"].isdigit()
    assert got["env"]["MKL_NUM_THREADS"] == got["env"]["OMP_NUM_THREADS"]
    assert int(got["env"]["OMP_NUM_THREADS"]) > 0
    assert "TORCH_THREADS" not in got["env"]
    assert "FFMPEG_THREADS" not in got["env"]


@pytest.mark.unit
def test_the_fetch_override_sets_the_thread_count(tmp_path: Path) -> None:
    got = recorded(launch(tmp_path, "--queues", "analysis", FETCH_CONCURRENCY="7"))
    assert threads_of(got) == "7"


@pytest.mark.unit
def test_an_empty_override_is_auto_and_never_an_empty_thread_variable(tmp_path: Path) -> None:
    got = recorded(launch(tmp_path, "--queues", "analysis", FETCH_CONCURRENCY=""))
    assert threads_of(got) == "4"
    assert got["env"]["OMP_NUM_THREADS"].isdigit()


@pytest.mark.unit
def test_the_explicit_flag_wins(tmp_path: Path) -> None:
    got = recorded(launch(tmp_path, "--queues", "maintenance", "--threads", "2"))
    assert threads_of(got) == "2"


@pytest.mark.unit
def test_the_maintenance_queue_exports_no_library_threads(tmp_path: Path) -> None:
    got = recorded(launch(tmp_path, "--queues", "maintenance", "--threads", "2"))
    assert got["env"] == {}


@pytest.mark.unit
def test_an_unknown_queue_exits_non_zero(tmp_path: Path) -> None:
    done = launch(tmp_path, "--queues", "analysis", "bogus")
    assert done.returncode != 0
    assert "bogus" in done.stderr
