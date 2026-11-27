"""The maintenance actors as a real worker subprocess against real Postgres, Redis and files."""

import asyncio
import time
from collections.abc import Callable

import pytest

from saveclock.adapters.queue import DramatiqEnqueuer
from saveclock.config import Settings
from saveclock.housekeeping_cli import main as cli_main
from saveclock.services import housekeeping as hkp
from saveclock.workers.broker import build_broker
from tests.conftest import ENV
from tests.integration.conftest import REDIS_URL, Harness
from tests.integration.housekeeping_harness import DAY, Hk

pytestmark = pytest.mark.integration


def sender(harness: Harness) -> DramatiqEnqueuer:
    settings = Settings(
        _env_file=None,
        **{**ENV, "redis_url": REDIS_URL, "database_url": harness.db.url("app_rw")},  # type: ignore[arg-type]
    )
    return DramatiqEnqueuer(build_broker(settings))


async def eventually(check: Callable[[], object], within_s: float = 90) -> None:
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        result = check()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        await asyncio.sleep(0.3)
    msg = "condition not reached in time"
    raise AssertionError(msg)


async def test_a_sent_sweep_removes_intermediates_and_keeps_the_song(
    hk: Hk, harness: Harness
) -> None:
    old = await hk.project(idle=8 * DAY)
    fresh = await hk.project()
    await hk.sql("UPDATE projects SET last_activity_at = now() WHERE id=$1", fresh)
    harness.start_worker(["maintenance"])
    sender(harness).send("sweep_intermediates", str(hk.user))

    await eventually(lambda: not hk.has(f"work/{old}"))
    assert hk.has(f"songs/{old}/source.wav")
    assert len(hk.blobs.list(f"work/{fresh}")) == 4  # recent activity: untouched
    assert hk.redis.get(hkp.LOCK_KEY) is None  # the lock is released


async def test_a_held_lock_makes_the_actor_return_without_work(hk: Hk, harness: Harness) -> None:
    old = await hk.project(idle=8 * DAY)
    hk.redis.set(hkp.LOCK_KEY, "someone else", ex=60)
    proc = harness.start_worker(["maintenance"])
    sender(harness).send("sweep_intermediates", str(hk.user))
    log = harness.tmp_path / "worker0.log"

    await eventually(lambda: log.exists() and "housekeeping.locked" in log.read_text())
    assert len(hk.blobs.list(f"work/{old}")) == 4
    assert proc.poll() is None
    hk.redis.delete(hkp.LOCK_KEY)
    sender(harness).send("sweep_intermediates", str(hk.user))
    await eventually(lambda: not hk.has(f"work/{old}"))


async def test_a_purge_message_removes_files_and_rows(hk: Hk, harness: Harness) -> None:
    pid = await hk.project(status="deleted")
    rid = await hk.render(pid, await hk.plan(pid), mode_a=True)
    harness.start_worker(["maintenance"])
    sender(harness).send("purge_project", str(hk.user), str(pid))

    async def gone() -> bool:
        return not (await hk.sql("SELECT 1 FROM projects WHERE id=$1", pid))

    await eventually(gone)
    for prefix in (f"songs/{pid}", f"work/{pid}", f"renders/{rid}"):
        assert not hk.has(prefix)


async def test_the_scheduler_sweeps_without_a_message(hk: Hk, harness: Harness) -> None:
    old = await hk.project(idle=8 * DAY)
    harness.start_worker(["maintenance"], MAINTENANCE_SCHEDULER="true")
    await eventually(lambda: not hk.has(f"work/{old}"))
    assert hk.redis.exists("periodic:sweep")  # the guard that stops a second sender


async def test_the_dry_run_cli_reports_and_deletes_nothing(
    hk: Hk, harness: Harness, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    old = await hk.project(idle=8 * DAY)
    for name, value in harness.env().items():
        monkeypatch.setenv(name, value)
    before = {k: b"".join(hk.blobs.open(k)) for k in hk.blobs.list("")}

    code = await asyncio.to_thread(cli_main, ["--dry-run"])

    out = capsys.readouterr().out
    assert code == 0
    assert "1 project(s) would lose intermediates, 400 bytes" in out
    assert f"work/{old}" in out
    assert {k: b"".join(hk.blobs.open(k)) for k in hk.blobs.list("")} == before
    row = await hk.sql("SELECT intermediates_purged_at FROM projects WHERE id=$1", old)
    assert row[0][0] is None
