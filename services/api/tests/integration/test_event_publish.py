"""Events through real Redis: the publisher, the state path and the worker's progress."""

import asyncio
import json
from pathlib import Path
from uuid import UUID

import pytest
from redis.asyncio import Redis

from saveclock.adapters.events import EventPublisher, channel
from saveclock.domain.events import DraftReadyEvent
from saveclock.services.events import ProgressEmitter, ProgressTicker
from tests.factories.audio import click_track
from tests.integration.conftest import REDIS_URL, ApiEnv

pytestmark = pytest.mark.integration
PID = UUID("00000000-0000-4000-8000-0000000000aa")


async def listen(redis: Redis, project_id: UUID) -> tuple[object, list[dict[str, object]]]:
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel(project_id))
    got: list[dict[str, object]] = []

    async def pump() -> None:
        async for message in pubsub.listen():
            if message["type"] == "message":
                got.append(json.loads(message["data"]))

    return asyncio.create_task(pump()), got


async def test_the_async_publisher_reaches_a_subscriber(redis_client: Redis) -> None:
    task, got = await listen(redis_client, PID)
    publisher = EventPublisher(aio=Redis.from_url(REDIS_URL))
    await publisher.publish(PID, DraftReadyEvent(4))
    await asyncio.sleep(0.2)
    task.cancel()  # type: ignore[attr-defined]
    assert got == [{"type": "draft_ready", "data": {"version": 4}}]


async def test_the_ticker_publishes_from_a_thread_through_the_sync_client(
    redis_client: Redis,
) -> None:
    from redis import Redis as SyncRedis

    task, got = await listen(redis_client, PID)
    publisher = EventPublisher(sync=SyncRedis.from_url(REDIS_URL))
    emitter = ProgressEmitter(publisher, PID, min_gap_s=0)

    def blocking() -> None:
        with ProgressTicker(emitter, "finding_beat", expected_s=1.0, interval_s=0.05):
            import time

            time.sleep(0.4)

    await asyncio.to_thread(blocking)
    await asyncio.sleep(0.2)
    task.cancel()  # type: ignore[attr-defined]
    pcts = [m["data"]["pct"] for m in got if m["type"] == "progress"]  # type: ignore[index]
    assert len(pcts) >= 3
    assert pcts == sorted(pcts)
    publisher.close()


async def test_every_status_change_of_the_api_announces_the_state(
    api: ApiEnv, redis_client: Redis, tmp_path: Path
) -> None:
    pid = UUID((await api.client.post("/api/v1/projects", json={})).json()["id"])
    task, got = await listen(redis_client, pid)
    wav = tmp_path / "c.wav"
    click_track(wav, duration=20.0)
    r = await api.client.post(
        f"/api/v1/projects/{pid}/song",
        content=wav.read_bytes(),
        headers={"content-type": "audio/wav", "x-filename": "c.wav"},
    )
    assert r.status_code == 202
    assert (await api.client.post(f"/api/v1/projects/{pid}/cancel")).status_code == 202
    await asyncio.sleep(0.4)
    task.cancel()  # type: ignore[attr-defined]
    states = [m["data"]["status"] for m in got if m["type"] == "state"]  # type: ignore[index]
    assert states == ["uploading", "validating", "canceled"]
    assert got[0]["data"]["ui_status"] == "uploading"  # type: ignore[index]
