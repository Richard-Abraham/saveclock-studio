"""The event stream through a real uvicorn: ASGITransport buffers a whole response, so a stream
needs a socket. The Redis publisher side is the test itself."""

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest
import uvicorn
from redis.asyncio import Redis

from saveclock.adapters.events import channel
from saveclock.config import Settings
from saveclock.container import build_deps
from saveclock.domain import events as ev
from saveclock.main import create_app
from saveclock.services.events import StreamLimits
from tests.conftest import ENV
from tests.integration.conftest import REDIS_URL, ApiEnv, Db

pytestmark = pytest.mark.integration
OTHER = UUID("00000000-0000-4000-8000-0000000000bb")


class Live:
    """uvicorn in a thread on an ephemeral port, with an app that shares the test database."""

    def __init__(self, db: Db, blob_root: Path, **limits: Any) -> None:
        settings = Settings(
            _env_file=None,
            **{  # type: ignore[arg-type]
                **ENV,
                "database_url": db.url("app_rw"),
                "redis_url": REDIS_URL,
                "blob_root": str(blob_root),
                "disk_low_watermark_gb": 0,
            },
        )
        self.app = create_app(settings, build_deps(settings))
        self.app.state.stream_limits = StreamLimits(**limits)
        self.server = uvicorn.Server(
            uvicorn.Config(self.app, host="127.0.0.1", port=0, log_level="warning")
        )
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.port = 0

    def start(self) -> None:
        self.thread.start()
        deadline = time.monotonic() + 10
        while not self.server.started:
            assert time.monotonic() < deadline, "uvicorn did not start"
            time.sleep(0.02)
        self.port = self.server.servers[0].sockets[0].getsockname()[1]

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)

    @property
    def limits(self) -> StreamLimits:
        limits: StreamLimits = self.app.state.stream_limits
        return limits

    def client(self, host: str = "localhost") -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{self.port}",
            headers={"host": host},
            timeout=httpx.Timeout(10.0, read=10.0),
        )


@pytest.fixture
def live(api: ApiEnv) -> Any:
    made: list[Live] = []

    def make(**limits: Any) -> Live:
        server = Live(api.db, api.blob_root, **limits)
        server.start()
        made.append(server)
        return server

    yield make
    for server in made:
        server.stop()


async def new_project(api: ApiEnv) -> UUID:
    return UUID((await api.client.post("/api/v1/projects", json={})).json()["id"])


class Frames:
    """Reads the SSE text lines of one stream into frames, in a background task."""

    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.comments: list[str] = []
        self.retry: str | None = None
        self.times: list[float] = []
        self.closed = asyncio.Event()
        self.task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        kind = ""
        try:
            async for line in self.response.aiter_lines():
                if line.startswith("retry:"):
                    self.retry = line
                elif line.startswith(":"):
                    self.comments.append(line)
                elif line.startswith("event:"):
                    kind = line.removeprefix("event:").strip()
                elif line.startswith("data:"):
                    self.events.append((kind, json.loads(line.removeprefix("data:"))))
                    self.times.append(time.monotonic())
        except (httpx.ReadError, httpx.RemoteProtocolError, asyncio.CancelledError):
            pass
        finally:
            self.closed.set()

    async def wait(self, cond: Callable[[], bool], within_s: float = 5.0) -> None:
        deadline = time.monotonic() + within_s
        while not cond():
            assert time.monotonic() < deadline, f"timeout; saw {self.events} {self.comments}"
            await asyncio.sleep(0.02)


@asynccontextmanager
async def stream(client: httpx.AsyncClient, pid: UUID) -> AsyncIterator[Frames]:
    async with client.stream("GET", f"/api/v1/projects/{pid}/events") as response:
        frames = Frames(response)
        try:
            yield frames
        finally:
            frames.task.cancel()


async def publish(redis: Redis, pid: UUID, event: ev.Event) -> None:
    await redis.publish(channel(pid), ev.to_wire(event))


async def test_the_first_event_is_the_current_state_and_headers_say_no_buffering(
    api: ApiEnv,
    live: Any,
    redis_client: Redis,
) -> None:
    server, pid = live(), await new_project(api)
    async with (
        server.client() as client,
        client.stream("GET", f"/api/v1/projects/{pid}/events") as r,
    ):
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert r.headers["cache-control"] == "private, no-store"
        assert r.headers["x-accel-buffering"] == "no"
        frames = Frames(r)
        await frames.wait(lambda: bool(frames.events))
        frames.task.cancel()
    assert frames.retry == "retry: 3000"
    assert frames.events[0] == (
        "state",
        {"status": "created", "ui_status": "uploading", "flags": {}},
    )


async def test_a_published_progress_arrives_within_a_second_and_percent_never_drops(
    api: ApiEnv,
    live: Any,
    redis_client: Redis,
) -> None:
    server, pid = live(), await new_project(api)
    async with server.client() as client, stream(client, pid) as frames:
        await frames.wait(lambda: bool(frames.events))
        sent = time.monotonic()
        for pct in (10, 20, 20, 30):
            await publish(
                redis_client, pid, ev.ProgressEvent("finding_beat", pct, "progress.finding_beat")
            )
        await frames.wait(lambda: len(frames.events) >= 5, 1.0)
        assert frames.times[1] - sent < 1.0
        pcts = [d["pct"] for k, d in frames.events if k == "progress"]
        assert pcts == sorted(pcts)


async def test_an_idle_stream_gets_a_ping(api: ApiEnv, live: Any) -> None:
    server, pid = live(ping_s=0.2), await new_project(api)
    async with server.client() as client, stream(client, pid) as frames:
        await frames.wait(lambda: len(frames.comments) >= 2, 3.0)
        assert set(frames.comments) == {": ping"}


async def test_a_reconnect_gets_the_current_snapshot_not_the_missed_events(
    api: ApiEnv,
    live: Any,
    redis_client: Redis,
) -> None:
    server, pid = live(), await new_project(api)
    async with server.client() as client:
        async with stream(client, pid) as first:
            await first.wait(lambda: bool(first.events))
            await publish(redis_client, pid, ev.ProgressEvent("finding_beat", 11, "k"))
            await first.wait(lambda: len(first.events) >= 2)
        # the client is gone; the project moves on and nobody listened
        await api.client.post(f"/api/v1/projects/{pid}/cancel")  # created: a conflict, no change
        await api_set_status(api, pid, "draft_ready")
        await publish(redis_client, pid, ev.ProgressEvent("finding_beat", 12, "k"))
        async with stream(client, pid) as second:
            await second.wait(lambda: bool(second.events))
        assert second.events[0][0] == "state"
        assert second.events[0][1]["status"] == "draft_ready"
        assert second.events[0][1]["ui_status"] == "draft"
        assert all(k != "progress" for k, _ in second.events)  # nothing is replayed


async def api_set_status(api: ApiEnv, pid: UUID, status: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        await conn.execute("UPDATE projects SET status = $1 WHERE id = $2", status, pid)
    finally:
        await conn.close()


async def test_the_stream_closes_after_a_terminal_event(
    api: ApiEnv,
    live: Any,
    redis_client: Redis,
) -> None:
    server, pid = live(), await new_project(api)
    async with server.client() as client, stream(client, pid) as frames:
        await frames.wait(lambda: bool(frames.events))
        await publish(redis_client, pid, ev.FailedEvent("draft", "stock_unavailable", True))
        await asyncio.wait_for(frames.closed.wait(), 3.0)
        assert frames.events[-1] == (
            "failed",
            {"stage": "draft", "code": "stock_unavailable", "retryable": True},
        )
    assert server.limits.open_streams == 0


async def test_the_sixth_stream_is_refused_and_a_disconnect_frees_its_slot(
    api: ApiEnv,
    live: Any,
) -> None:
    server, pid = live(), await new_project(api)
    async with server.client() as client:
        opened = []
        for _ in range(5):
            cm = stream(client, pid)
            frames = await cm.__aenter__()
            await frames.wait(lambda f=frames: bool(f.events))  # type: ignore[misc]
            opened.append(cm)
        assert server.limits.open_streams == 5
        sixth = await client.get(f"/api/v1/projects/{pid}/events")
        assert sixth.status_code == 409
        assert sixth.json()["error"]["details"]["reason"] == "too_many_streams"
        await opened.pop().__aexit__(None, None, None)  # a client goes away mid-stream
        deadline = time.monotonic() + 5
        while server.limits.open_streams > 4:
            assert time.monotonic() < deadline, "the slot was never released"
            await asyncio.sleep(0.05)
        again = stream(client, pid)
        frames = await again.__aenter__()
        await frames.wait(lambda: bool(frames.events))
        opened.append(again)
        for cm in opened:
            await cm.__aexit__(None, None, None)


async def test_another_users_project_and_a_foreign_host_are_refused(
    api: ApiEnv,
    live: Any,
) -> None:
    server, pid = live(), await new_project(api)
    import asyncpg

    conn = await asyncpg.connect(api.db.raw("postgres"))
    try:
        await conn.execute("INSERT INTO users (id, email) VALUES ($1, 'b@example.test')", OTHER)
        await conn.execute("UPDATE projects SET user_id = $1 WHERE id = $2", OTHER, pid)
    finally:
        await conn.close()
    async with server.client() as client:
        assert (await client.get(f"/api/v1/projects/{pid}/events")).status_code == 404
    async with server.client("evil.example") as client:
        r = await client.get(f"/api/v1/projects/{pid}/events")
        assert r.status_code == 403
        assert r.json()["error"]["details"]["reason"] == "host_not_allowed"
    assert server.limits.open_streams == 0


async def test_a_stream_ends_at_its_maximum_age(api: ApiEnv, live: Any) -> None:
    server, pid = live(max_age_s=0.5, ping_s=0.1), await new_project(api)
    async with server.client() as client, stream(client, pid) as frames:
        await asyncio.wait_for(frames.closed.wait(), 3.0)
    assert server.limits.open_streams == 0


async def _subscribers(redis: Redis, pid: UUID) -> int:
    counts = await redis.pubsub_numsub(channel(pid))
    return int(counts[0][1])


async def test_a_disconnect_unsubscribes_the_stream_from_redis(
    api: ApiEnv,
    live: Any,
    redis_client: Redis,
) -> None:
    server, pid = live(), await new_project(api)
    async with server.client() as client:
        async with stream(client, pid) as frames:
            await frames.wait(lambda: bool(frames.events))
            assert await _subscribers(redis_client, pid) == 1
        deadline = time.monotonic() + 5
        while await _subscribers(redis_client, pid) != 0:
            assert time.monotonic() < deadline, "the subscription outlived the client"
            await asyncio.sleep(0.05)


async def test_an_event_published_while_the_snapshot_is_read_is_still_delivered(
    api: ApiEnv,
    live: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from saveclock.repositories.projects import ProjectRepository

    real_get = ProjectRepository.get

    async def get_then_publish(self: ProjectRepository, **kw: Any) -> Any:
        found = await real_get(self, **kw)
        publisher = Redis.from_url(REDIS_URL)
        try:  # the project moves on right after the read that the snapshot is made of
            await publish(publisher, kw["project_id"], ev.ProgressEvent("finding_beat", 42, "k"))
        finally:
            await publisher.aclose()
        return found

    server, pid = live(), await new_project(api)
    monkeypatch.setattr(ProjectRepository, "get", get_then_publish)
    async with server.client() as client, stream(client, pid) as frames:
        await frames.wait(lambda: len(frames.events) >= 2)
    assert [k for k, _ in frames.events[:2]] == ["state", "progress"]
