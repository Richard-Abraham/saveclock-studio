"""The one path every project status change takes (ARCH §4, T-2.10c): the repository's optimistic
`UPDATE ... WHERE status = :from`, then a `state` event, so no transition is silent.

`commit=False` is for a caller that changes more rows in the same transaction: it must call
`announce_pending` after its own commit. Events are best effort (Postgres is the record).
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.events import EventPublisher
from saveclock.domain.events import FailedEvent, StateEvent
from saveclock.errors import RETRYABLE, ErrorCode
from saveclock.repositories.projects import ProjectRepository

PENDING = "pending_state_events"
# the job stage a failed status belongs to, for the `failed` event
FAILED_STAGE = {
    "failed_analysis": "analyze",
    "failed_plan": "draft",
    "failed_render": "render",
    "rejected": "validate",
}
_STOCK_REASONS = frozenset({"no_usable_clips", "stock_unavailable"})


def failure_code(to: str, reason: str | None) -> ErrorCode:
    if to == "rejected":
        return ErrorCode.FILE_REJECTED
    if to == "failed_render" and reason == "verification_failed":
        return ErrorCode.VERIFICATION_FAILED
    if reason in _STOCK_REASONS:
        return ErrorCode.STOCK_UNAVAILABLE
    return ErrorCode.INTERNAL_ERROR


async def announce(
    session: AsyncSession, publisher: EventPublisher | None, user_id: UUID, project_id: UUID
) -> None:
    """Publish the project's current state (and `failed` when it is in a failed state)."""
    if publisher is None:
        return
    from saveclock.services.projects import ui_status  # lazy: projects imports this module

    project = await ProjectRepository(session).get(user_id=user_id, project_id=project_id)
    if project is None:
        return
    await session.refresh(project)  # the UPDATE bypassed the identity map
    await publisher.publish(
        project_id, StateEvent(project.status, ui_status(project.status).value, dict(project.flags))
    )
    stage = FAILED_STAGE.get(project.status)
    if stage is not None:
        code = failure_code(project.status, project.status_reason)
        await publisher.publish(project_id, FailedEvent(stage, code.value, code in RETRYABLE))


async def transition(
    session: AsyncSession,
    publisher: EventPublisher | None,
    *,
    user_id: UUID,
    project_id: UUID,
    from_: str | Sequence[str],
    to: str,
    reason: str | None = None,
    commit: bool = True,
) -> bool:
    """False: 0 rows (a lost race, or not the user's project). An undrawn edge raises."""
    moved = await ProjectRepository(session).transition(
        user_id=user_id, project_id=project_id, from_=from_, to=to, reason=reason
    )
    if not moved:
        return False
    if commit:
        await session.commit()
        await announce(session, publisher, user_id, project_id)
    else:
        session.info.setdefault(PENDING, []).append((user_id, project_id))
    return True


async def announce_pending(session: AsyncSession, publisher: EventPublisher | None) -> None:
    """After the caller's commit: publish the states of the `commit=False` transitions."""
    pending: list[tuple[UUID, UUID]] = session.info.pop(PENDING, [])
    for user_id, project_id in pending:
        await announce(session, publisher, user_id, project_id)
