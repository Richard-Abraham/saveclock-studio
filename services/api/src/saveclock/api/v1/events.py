import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from redis.asyncio.client import PubSub
from starlette.background import BackgroundTask

from saveclock.adapters.events import channel
from saveclock.api.deps import current_user, get_deps
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES
from saveclock.deps import Deps
from saveclock.domain import events as ev
from saveclock.errors import Conflict, ConflictReason, NotFound
from saveclock.repositories.projects import ProjectRepository
from saveclock.services.identity import CurrentUser
from saveclock.services.projects import ui_status

router = APIRouter(prefix="/projects", tags=["events"], responses=ERROR_RESPONSES)

HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Accel-Buffering": "no",  # a reverse proxy must not hold the stream back
}


@router.get(
    "/{project_id}/events",
    operation_id="stream_events",
    response_class=StreamingResponse,
    responses={
        **CONFLICT_RESPONSE,
        200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}},
    },
)
async def stream_events(
    project_id: UUID,
    request: Request,
    user: Annotated[CurrentUser, Depends(current_user)],
    deps: Annotated[Deps, Depends(get_deps)],
) -> StreamingResponse:
    """`retry: 3000`, then a `state` snapshot, then live events of the project until a terminal
    one (`failed`, `render_ready`, `mode_a_ready`) or 15 minutes. `: ping` every 15 s when idle;
    `Last-Event-ID` is ignored (the snapshot is authoritative). At most 5 streams at once: the
    sixth is 409 `conflict` with `details.reason = too_many_streams`."""
    limits = request.app.state.stream_limits
    token = limits.acquire()
    if token is None:
        raise Conflict(ConflictReason.TOO_MANY_STREAMS)
    pubsub = deps.redis.pubsub()
    closed = False

    async def cleanup() -> None:  # idempotent: the generator's finally and the background task
        nonlocal closed
        if closed:
            return
        closed = True
        limits.release(token)
        await asyncio.shield(_close(pubsub, channel(project_id)))  # aclose runs even if cancelled

    try:
        # subscribe first, read the snapshot after: an event published in between is queued
        # on the subscription and delivered after the snapshot, never lost
        await pubsub.subscribe(channel(project_id))
        async with deps.sessionmaker() as session:
            project = await ProjectRepository(session).get(user_id=user.id, project_id=project_id)
            if project is None:
                raise NotFound
            await ProjectRepository(session).touch(user_id=user.id, project_id=project_id)
            await session.commit()  # watching a project is activity (ARCH §4 retention)
            snapshot = ev.StateEvent(
                project.status, ui_status(project.status).value, dict(project.flags)
            )
    except BaseException:
        await cleanup()
        raise

    async def frames() -> AsyncIterator[bytes]:
        deadline = time.monotonic() + limits.max_age_s
        try:
            yield ev.retry_line()
            yield ev.encode_event(snapshot)
            last_sent = time.monotonic()
            while (left := deadline - time.monotonic()) > 0:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=min(limits.ping_s, left)
                )
                if message is None:  # idle (or Redis's own subscribe reply, which is skipped)
                    if time.monotonic() - last_sent >= limits.ping_s * 0.9:
                        yield ev.PING
                        last_sent = time.monotonic()
                    continue
                kind, data = ev.from_wire(_text(message["data"]))
                yield ev.encode_sse(kind, data)
                last_sent = time.monotonic()
                if kind in ev.TERMINAL:
                    return
        finally:
            await cleanup()

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers=HEADERS,
        background=BackgroundTask(cleanup),  # also when the body never started
    )


def _text(data: Any) -> str:  # noqa: ANN401
    return data.decode() if isinstance(data, bytes) else str(data)


async def _close(pubsub: PubSub, name: str) -> None:
    try:
        await pubsub.unsubscribe(name)
        await pubsub.aclose()
    except Exception:  # noqa: S110 - the connection may already be gone
        pass
