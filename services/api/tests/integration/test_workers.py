"""Stub job through four queues: real worker subprocesses, Postgres and Redis, no broker mocks."""

import asyncio
import os
import signal
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
import httpx
import pytest
from redis.asyncio import Redis

from saveclock.config import Settings
from saveclock.models import JobQueue
from saveclock.services.stub import chain_ids
from saveclock.workers.broker import build_broker
from saveclock.workers.stub import StubActors, register_stub_actors
from tests.conftest import client_for, make_app
from tests.integration.conftest import API_DIR, REDIS_URL, Db

pytestmark = pytest.mark.integration

OWNER = UUID("00000000-0000-4000-8000-000000000001")
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")
MAIN_QUEUES = ["analysis", "fetch", "render"]


class Harness:
    def __init__(self, db: Db, blob_root: Path, tmp_path: Path) -> None:
        self.db, self.blob_root, self.tmp_path = db, blob_root, tmp_path
        self.procs: list[subprocess.Popen[bytes]] = []

    def env(self, **extra: str) -> dict[str, str]:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"OWNER_DISPLAY_NAME", "FETCH_CONCURRENCY"}
        }
        env.update(
            APP_ENV="ci",
            APP_ORIGIN="http://localhost:3000",
            DATABASE_URL=self.db.url("app_rw"),
            REDIS_URL=REDIS_URL,
            BLOB_ROOT=str(self.blob_root),
            DISK_LOW_WATERMARK_GB="0",
        )
        env.update(extra)
        return env

    def start_worker(self, queues: list[str], **extra_env: str) -> subprocess.Popen[bytes]:
        log = (self.tmp_path / f"worker{len(self.procs)}.log").open("wb")
        proc = subprocess.Popen(  # noqa: S603 - fixed argument list, no shell
            [
                sys.executable,
                "-m",
                "dramatiq",
                "saveclock.workers.main",
                "--processes",
                "1",
                "--threads",
                "2",
                "--queues",
                *queues,
            ],
            cwd=API_DIR,
            env=self.env(**extra_env),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.procs.append(proc)
        return proc

    def kill_all(self) -> None:
        for proc in self.procs:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)


@pytest.fixture
def harness(
    migrated_db: Db, blob_root: Path, tmp_path: Path, redis_client: Redis
) -> Iterator[Harness]:
    h = Harness(migrated_db, blob_root, tmp_path)
    yield h
    h.kill_all()


@pytest.fixture
async def api(harness: Harness) -> AsyncIterator[httpx.AsyncClient]:
    app = make_app(
        database_url=harness.db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(harness.blob_root),
        disk_low_watermark_gb=0,
    )
    async with client_for(app) as client:
        yield client
    await app.state.deps.close()


async def create_job(api: httpx.AsyncClient, sleep_s: int = 0) -> UUID:
    r = await api.post("/api/v1/_stub/jobs", json={"sleep_s": sleep_s})
    assert r.status_code == 202, r.text
    return UUID(r.json()["job_id"])


async def poll(
    api: httpx.AsyncClient,
    job_id: UUID,
    done: Callable[[list[dict[str, Any]]], bool],
    within_s: float,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + within_s
    hops: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        r = await api.get(f"/api/v1/_stub/jobs/{job_id}")
        hops = r.json()["hops"]
        if done(hops):
            return hops
        await asyncio.sleep(0.3)
    msg = f"timeout; last state: {[(h['queue'], h['state'], h['attempt']) for h in hops]}"
    raise AssertionError(msg)


def all_ok(hops: list[dict[str, Any]]) -> bool:
    return all(h["state"] == "ok" for h in hops)


async def job_rows(db: Db) -> int:
    conn = await asyncpg.connect(db.raw("postgres"))
    try:
        return int(await conn.fetchval("SELECT count(*) FROM jobs"))
    finally:
        await conn.close()


def blob_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def local_actors(db: Db, blob_root: Path) -> StubActors:
    settings = Settings(
        _env_file=None,
        app_env="ci",
        app_origin="http://localhost:3000",
        database_url=db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(blob_root),
        disk_low_watermark_gb=0,
    )
    return register_stub_actors(build_broker(settings), settings)


async def test_happy_path_through_all_four_queues(harness: Harness, api: httpx.AsyncClient) -> None:
    harness.start_worker(MAIN_QUEUES)
    harness.start_worker(["maintenance"])
    job_id = await create_job(api)
    hops = await poll(api, job_id, all_ok, 30)
    assert [h["queue"] for h in hops] == ["analysis", "fetch", "render", "maintenance"]
    assert all(h["run_ms"] is not None for h in hops)
    dl = await api.get(f"/api/v1/_stub/jobs/{job_id}/download")
    assert dl.status_code == 200
    assert dl.text == f"stub job {job_id}\n"
    assert dl.headers["content-disposition"] == 'attachment; filename="stub.txt"'
    assert dl.headers["x-content-type-options"] == "nosniff"
    assert dl.headers["cache-control"] == "private, no-store"
    part = await api.get(f"/api/v1/_stub/jobs/{job_id}/download", headers={"range": "bytes=0-3"})
    assert part.status_code == 206
    assert part.text == "stub"


@pytest.mark.slow
async def test_redelivery_is_idempotent(harness: Harness, api: httpx.AsyncClient) -> None:
    job_id = await create_job(api)  # enqueues hop 1; no worker runs, we call the bodies ourselves
    actors = local_actors(harness.db, harness.blob_root)
    for _ in range(2):  # at-least-once: every body runs twice
        for queue in (JobQueue.ANALYSIS, JobQueue.FETCH, JobQueue.RENDER, JobQueue.MAINTENANCE):
            hop_id = chain_ids(job_id)[list(actors.by_queue).index(queue)]
            await asyncio.to_thread(actors.by_queue[queue].fn, str(hop_id), str(OWNER))
    assert await job_rows(harness.db) == 4
    assert len(blob_files(harness.blob_root)) == 1
    hops = await poll(api, job_id, all_ok, 5)
    assert [h["attempt"] for h in hops] == [1, 1, 1, 1]  # the second run was refused


async def test_redelivery_after_a_crash_between_enqueue_and_finish(
    harness: Harness, api: httpx.AsyncClient
) -> None:
    """The next hop was already created, but this hop never reached `ok`: it runs again."""
    job_id = await create_job(api)
    actors = local_actors(harness.db, harness.blob_root)
    first = actors.by_queue[JobQueue.ANALYSIS]
    await asyncio.to_thread(first.fn, str(job_id), str(OWNER))
    conn = await asyncpg.connect(harness.db.raw("postgres"))
    try:
        await conn.execute("UPDATE jobs SET state = 'running' WHERE id = $1", job_id)
    finally:
        await conn.close()
    await asyncio.to_thread(first.fn, str(job_id), str(OWNER))  # must not raise or duplicate
    assert await job_rows(harness.db) == 2
    hops = (await api.get(f"/api/v1/_stub/jobs/{job_id}")).json()["hops"]
    assert [h["state"] for h in hops] == ["ok", "queued", "pending", "pending"]
    assert hops[0]["attempt"] == 2


@pytest.mark.slow
async def test_kill_9_mid_job_is_redelivered(harness: Harness, api: httpx.AsyncClient) -> None:
    first = harness.start_worker([*MAIN_QUEUES, "maintenance"])
    job_id = await create_job(api, sleep_s=8)
    await poll(api, job_id, lambda h: h[0]["state"] == "running", 30)
    os.killpg(first.pid, signal.SIGKILL)  # the whole process group: master and worker child
    first.wait(timeout=10)
    harness.start_worker([*MAIN_QUEUES, "maintenance"], BROKER_HEARTBEAT_TIMEOUT_S="3")
    # Recovery bound: the killed hop is redelivered and finishes within 60 s. The rest of the
    # chain then takes 3 more hops of 8 s each, so it gets its own 60 s.
    await poll(api, job_id, lambda h: h[0]["state"] == "ok", 60)
    hops = await poll(api, job_id, all_ok, 60)
    assert hops[0]["attempt"] >= 2
    assert await job_rows(harness.db) == 4
    assert len(blob_files(harness.blob_root)) == 1


@pytest.mark.slow
async def test_sigterm_drains_the_running_job(harness: Harness, api: httpx.AsyncClient) -> None:
    worker = harness.start_worker(MAIN_QUEUES)
    job_id = await create_job(api, sleep_s=10)
    await poll(api, job_id, lambda h: h[0]["state"] == "running", 30)
    worker.send_signal(signal.SIGTERM)
    assert worker.wait(timeout=90) == 0
    r = await api.get(f"/api/v1/_stub/jobs/{job_id}")
    assert r.json()["hops"][0]["state"] == "ok"


async def test_foreign_ownership_is_refused(harness: Harness, api: httpx.AsyncClient) -> None:
    job_id = await create_job(api)
    conn = await asyncpg.connect(harness.db.raw("postgres"))
    try:
        await conn.execute("INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", OTHER)
    finally:
        await conn.close()
    actors = local_actors(harness.db, harness.blob_root)
    await asyncio.to_thread(actors.by_queue[JobQueue.ANALYSIS].fn, str(job_id), str(OTHER))
    hops = (await api.get(f"/api/v1/_stub/jobs/{job_id}")).json()["hops"]
    assert hops[0]["state"] == "error"
    assert [h["state"] for h in hops[1:]] == ["pending"] * 3
    assert blob_files(harness.blob_root) == []


@pytest.mark.unit
def test_every_actor_has_explicit_limits(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="ci",
        app_origin="http://localhost:3000",
        database_url="postgresql+asyncpg://u:p@localhost:1/x",
        redis_url="redis://localhost:1/0",
        blob_root=str(tmp_path),
    )
    actors = register_stub_actors(build_broker(settings), settings)
    everything = [*actors.by_queue.values(), actors.failed]
    assert len(everything) == 5
    for actor in everything:
        assert actor.options["max_retries"] <= 2
        assert actor.options["time_limit"] > 0
        assert "min_backoff" in actor.options
        assert "max_backoff" in actor.options
    assert set(actors.by_queue) == set(JobQueue)
    assert [a.queue_name for a in actors.by_queue.values()] == [q.value for q in actors.by_queue]


async def test_broker_payload_is_ids_only(harness: Harness, api: httpx.AsyncClient) -> None:
    settings = Settings(
        _env_file=None,
        app_env="ci",
        app_origin="http://localhost:3000",
        database_url=harness.db.url("app_rw"),
        redis_url=REDIS_URL,
        blob_root=str(harness.blob_root),
        disk_low_watermark_gb=0,
    )
    broker = build_broker(settings)
    seen: list[Any] = []
    original = broker.enqueue

    def spy(message: Any, *, delay: int | None = None) -> Any:
        seen.append(message)
        return original(message, delay=delay)

    broker.enqueue = spy  # type: ignore[method-assign]
    actors = register_stub_actors(broker, settings)
    job_id = await create_job(api)  # project and first job rows (the API's own broker sends)
    await asyncio.to_thread(actors.send_first, job_id, OWNER)  # first hop, through the spy
    await asyncio.to_thread(actors.by_queue[JobQueue.ANALYSIS].fn, str(job_id), str(OWNER))
    assert len(seen) == 2  # the first hop, then hop 1 enqueueing hop 2
    for message, hop in zip(seen, chain_ids(job_id)[:2], strict=True):
        assert message.kwargs == {}
        assert [UUID(a) for a in message.args] == [hop, OWNER]
