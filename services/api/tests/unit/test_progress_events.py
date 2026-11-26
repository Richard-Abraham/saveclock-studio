"""The progress emitter, the ticker and the stream limits (no Redis: a recording publisher)."""

import asyncio
import threading
import time
from typing import Any
from uuid import UUID

import pytest

from saveclock.adapters.events import EventPublisher, channel
from saveclock.domain.events import DraftReadyEvent, Event, ProgressEvent
from saveclock.services.events import ProgressEmitter, ProgressTicker, StreamLimits

PID = UUID("00000000-0000-4000-8000-0000000000aa")


class Recorder(EventPublisher):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[Event] = []
        self.lock = threading.Lock()

    def publish_sync(self, project_id: UUID, event: Event) -> None:
        with self.lock:
            self.sent.append(event)

    async def publish(self, project_id: UUID, event: Event) -> None:
        self.publish_sync(project_id, event)


def pcts(rec: Recorder) -> list[int]:
    return [e.pct for e in rec.sent if isinstance(e, ProgressEvent)]


def test_percent_is_monotonic_even_when_a_late_tick_arrives() -> None:
    rec = Recorder()
    emitter = ProgressEmitter(rec, PID, min_gap_s=0)
    emitter.emit("choosing_clips", 0.9)
    emitter.emit("choosing_clips", 0.1)  # an older estimate: held at the earlier percent
    emitter.emit("building_draft", 0.0, force=True)
    got = pcts(rec)
    assert got == sorted(got)
    assert got[1] == got[0]


def test_events_closer_than_the_gap_are_dropped_unless_forced() -> None:
    now = [0.0]
    rec = Recorder()
    emitter = ProgressEmitter(rec, PID, clock=lambda: now[0], min_gap_s=1.0)
    emitter.emit("finding_beat", 0.1)
    now[0] = 0.5
    emitter.emit("finding_beat", 0.2)  # dropped
    emitter.emit("finding_beat", 0.3, force=True)  # a step boundary is never dropped
    now[0] = 2.0
    emitter.emit("finding_beat", 0.4)
    assert len(rec.sent) == 3
    assert isinstance(rec.sent[0], ProgressEvent)
    assert rec.sent[0].message_key == "progress.finding_beat"


def test_without_a_publisher_nothing_happens() -> None:
    ProgressEmitter(None, PID).emit("finding_beat", 0.5)


async def test_the_async_wrappers_publish() -> None:
    rec = Recorder()
    emitter = ProgressEmitter(rec, PID)
    await emitter.aemit("choosing_clips", 0.5)
    await emitter.draft_ready(2)
    assert isinstance(rec.sent[-1], DraftReadyEvent)
    assert rec.sent[-1].version == 2
    await ProgressEmitter(None, PID).draft_ready(1)  # no publisher: a no-op


def test_the_ticker_emits_while_one_blocking_call_runs() -> None:
    rec = Recorder()
    emitter = ProgressEmitter(rec, PID, min_gap_s=0)
    with ProgressTicker(emitter, "finding_beat", expected_s=0.4, interval_s=0.05):
        time.sleep(0.4)
    got = pcts(rec)
    assert len(got) >= 4
    assert got == sorted(got)
    assert max(got) < 40  # never the end of the step: the stage is not done yet


def test_the_ticker_stops_with_the_block() -> None:
    rec = Recorder()
    emitter = ProgressEmitter(rec, PID, min_gap_s=0)
    with ProgressTicker(emitter, "finding_beat", expected_s=1, interval_s=0.02):
        pass
    count = len(rec.sent)
    time.sleep(0.1)
    assert len(rec.sent) == count


def test_stream_limits_cap_and_release_is_idempotent() -> None:
    limits = StreamLimits(max_streams=2)
    a, b = limits.acquire(), limits.acquire()
    assert a is not None
    assert b is not None
    assert limits.acquire() is None
    limits.release(a)
    limits.release(a)  # twice: still one slot free, not two
    assert limits.open_streams == 1
    assert limits.acquire() is not None
    assert limits.acquire() is None


async def test_the_publisher_swallows_a_redis_failure() -> None:
    class Broken:
        def publish(self, *_a: Any) -> None:
            raise ConnectionError

        async def apublish(self, *_a: Any) -> None:
            raise ConnectionError

    sync_only = EventPublisher(sync=Broken())  # type: ignore[arg-type]
    await sync_only.publish(PID, DraftReadyEvent(1))
    sync_only.publish_sync(PID, DraftReadyEvent(1))
    assert channel(PID) == f"proj:{PID}"
    await EventPublisher().publish(PID, DraftReadyEvent(1))  # neither client: nothing to do
    EventPublisher().publish_sync(PID, DraftReadyEvent(1))
    await asyncio.sleep(0)


def test_the_async_client_publishes_to_the_projects_channel() -> None:
    seen: list[tuple[str, str]] = []

    class Aio:
        async def publish(self, name: str, body: str) -> None:
            seen.append((name, body))

    asyncio.run(EventPublisher(aio=Aio()).publish(PID, DraftReadyEvent(3)))  # type: ignore[arg-type]
    assert seen == [(f"proj:{PID}", '{"type":"draft_ready","data":{"version":3}}')]


def test_publish_through_a_sync_client_in_a_thread() -> None:
    seen: list[str] = []

    class Sync:
        def publish(self, name: str, body: str) -> None:
            seen.append(name)

        def close(self) -> None:
            seen.append("closed")

    publisher = EventPublisher(sync=Sync())  # type: ignore[arg-type]
    asyncio.run(publisher.publish(PID, DraftReadyEvent(1)))
    publisher.publish_sync(PID, DraftReadyEvent(1))
    publisher.close()
    assert seen == [f"proj:{PID}", f"proj:{PID}", "closed"]


@pytest.mark.parametrize("gap", [0.0, 1.0])
def test_the_gap_is_a_setting(gap: float) -> None:
    assert ProgressEmitter(None, PID, min_gap_s=gap)._gap == gap
