"""Only the process that serves the heavy queues publishes the tuning key."""

import os
import subprocess
import sys

import pytest

from tests.integration.conftest import API_DIR, REDIS_URL

pytestmark = pytest.mark.integration

CODE = (
    "import saveclock.workers.main as m;"
    "print(any(type(x).__name__ == 'TuningHeartbeat' for x in m.broker.middleware))"
)


def has_heartbeat(**extra: str) -> bool:
    env = {k: v for k, v in os.environ.items() if k != "TUNING_PUBLISHER"}
    env.update(
        APP_ENV="ci",
        APP_ORIGIN="http://localhost:3000",
        DATABASE_URL="postgresql+asyncpg://u:p@localhost:1/x",
        REDIS_URL=REDIS_URL,
        BLOB_ROOT="/tmp",  # noqa: S108
        **extra,
    )
    out = subprocess.run(  # noqa: S603 - fixed argument list
        [sys.executable, "-c", CODE],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return out.stdout.strip().splitlines()[-1] == "True"


def test_maintenance_worker_does_not_publish_tuning() -> None:
    assert has_heartbeat() is False


def test_heavy_worker_publishes_tuning() -> None:
    assert has_heartbeat(TUNING_PUBLISHER="true") is True
