"""Publishing project events to Redis (`PUBLISH proj:{id}`, ARCH §12).

Postgres is the record, so a failed publish is logged and swallowed: the next `state` snapshot
the browser fetches is authoritative. The API holds an asyncio client, a worker a sync one (its
progress ticker runs in a thread); either may be absent (unit tests, a context without events).
"""

import asyncio
from uuid import UUID

import structlog
from redis import Redis
from redis.asyncio import Redis as AsyncRedis

from saveclock.domain.events import Event, to_wire

log = structlog.get_logger()


def channel(project_id: UUID) -> str:
    return f"proj:{project_id}"


class EventPublisher:
    def __init__(self, *, sync: Redis | None = None, aio: AsyncRedis | None = None) -> None:
        self._sync, self._aio = sync, aio

    async def publish(self, project_id: UUID, event: Event) -> None:
        try:
            if self._aio is not None:
                await self._aio.publish(channel(project_id), to_wire(event))
            elif self._sync is not None:
                await asyncio.to_thread(self._sync.publish, channel(project_id), to_wire(event))
        except Exception as exc:
            log.warning("events.publish_failed", error=type(exc).__name__)

    def publish_sync(self, project_id: UUID, event: Event) -> None:
        """For threads (the progress ticker). Needs the sync client; otherwise a no-op."""
        if self._sync is None:
            return
        try:
            self._sync.publish(channel(project_id), to_wire(event))
        except Exception as exc:
            log.warning("events.publish_failed", error=type(exc).__name__)

    def close(self) -> None:
        if self._sync is not None:
            self._sync.close()
