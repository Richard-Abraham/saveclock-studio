import asyncio
import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.adapters.queue import Enqueuer
from saveclock.domain.states import RETRYABLE_FROM
from saveclock.errors import BadRequest, Conflict, ConflictReason, NotFound
from saveclock.ids import new_id
from saveclock.models import Analysis, JobQueue, JobStage, Project, ProjectStatus, Song
from saveclock.repositories.analyses import AnalysisRepository
from saveclock.repositories.jobs import JobRepository
from saveclock.repositories.projects import ProjectRepository
from saveclock.repositories.songs import SongRepository

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


class UiStatus(StrEnum):
    """What the UI shows (ARCH §4). Python owns this mapping; web takes the enum from OpenAPI."""

    UPLOADING = "uploading"
    ANALYSING = "analysing"
    DRAFT = "draft"
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"
    CANCELED = "canceled"


_UI = {
    ProjectStatus.CREATED: UiStatus.UPLOADING,
    ProjectStatus.UPLOADING: UiStatus.UPLOADING,
    ProjectStatus.VALIDATING: UiStatus.ANALYSING,
    ProjectStatus.ANALYZING: UiStatus.ANALYSING,
    ProjectStatus.PLANNING: UiStatus.ANALYSING,
    ProjectStatus.DRAFT_READY: UiStatus.DRAFT,
    ProjectStatus.RENDERING: UiStatus.RENDERING,
    ProjectStatus.READY: UiStatus.READY,
    ProjectStatus.FAILED_ANALYSIS: UiStatus.FAILED,
    ProjectStatus.FAILED_PLAN: UiStatus.FAILED,
    ProjectStatus.FAILED_RENDER: UiStatus.FAILED,
    ProjectStatus.REJECTED: UiStatus.FAILED,
    ProjectStatus.CANCELED: UiStatus.CANCELED,
}  # DELETED is hidden: it has no UI status


def ui_status(status: str) -> UiStatus:
    return _UI[ProjectStatus(status)]


@dataclass(frozen=True)
class ProjectPage:
    items: list[Project]
    next_cursor: str | None


def encode_cursor(created_at: datetime, project_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{project_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        stamp, ident = raw.split("|")
        return datetime.fromisoformat(stamp), UUID(ident)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise BadRequest("invalid cursor") from None


async def list_projects(
    session: AsyncSession, user_id: UUID, limit: int, cursor: str | None
) -> ProjectPage:
    after = decode_cursor(cursor) if cursor else None
    rows = await ProjectRepository(session).list(user_id=user_id, limit=limit + 1, after=after)
    page = rows[:limit]
    more = len(rows) > limit
    next_cursor = encode_cursor(page[-1].created_at, page[-1].id) if more else None
    return ProjectPage(items=page, next_cursor=next_cursor)


MAX_MANUAL_RETRIES = 3
CANCELABLE = (
    ProjectStatus.VALIDATING.value,
    ProjectStatus.ANALYZING.value,
    ProjectStatus.PLANNING.value,
)


async def _owned(session: AsyncSession, user_id: UUID, project_id: UUID) -> Project:
    project = await ProjectRepository(session).get(user_id=user_id, project_id=project_id)
    if project is None:
        raise NotFound
    return project


async def create_project(
    session: AsyncSession, user_id: UUID, title: str | None, options: dict[str, Any]
) -> Project:
    project = await ProjectRepository(session).create(user_id=user_id, title=title, options=options)
    await session.commit()
    return project


async def get_detail(
    session: AsyncSession, user_id: UUID, project_id: UUID
) -> tuple[Project, Song | None, Analysis | None]:
    """Project, song and analysis; opening a project counts as activity (ARCH §4 retention)."""
    await ProjectRepository(session).touch(user_id=user_id, project_id=project_id)
    project = await _owned(session, user_id, project_id)
    song = await SongRepository(session).get_by_project(user_id=user_id, project_id=project_id)
    analysis = await AnalysisRepository(session).get_by_project(
        user_id=user_id, project_id=project_id
    )
    await session.commit()
    return project, song, analysis


async def patch_project(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    title: str | None,
    options: dict[str, Any] | None,
) -> Project:
    """Title and options change only before the song is uploaded (afterwards: plan ops)."""
    project = await _owned(session, user_id, project_id)
    if project.status != ProjectStatus.CREATED.value:
        raise Conflict(ConflictReason.WRONG_STATE)
    values: dict[str, Any] = {}
    if title is not None:
        values["title"] = title
    if options is not None:
        values["options"] = options
    if values:
        await ProjectRepository(session).update_fields(
            user_id=user_id, project_id=project_id, values=values
        )
    await session.commit()
    await session.refresh(project)
    return project


async def cancel(session: AsyncSession, user_id: UUID, project_id: UUID) -> Project:
    """validating | analyzing | planning -> canceled; running jobs see `cancel_requested`."""
    project = await _owned(session, user_id, project_id)
    if not await ProjectRepository(session).transition(
        user_id=user_id,
        project_id=project_id,
        from_=CANCELABLE,
        to=ProjectStatus.CANCELED.value,
    ):
        raise Conflict(ConflictReason.WRONG_STATE)
    await JobRepository(session).request_cancel(user_id=user_id, project_id=project_id)
    await session.commit()
    await session.refresh(project)
    return project


async def retry(
    session: AsyncSession, user_id: UUID, project_id: UUID, enqueuer: Enqueuer
) -> Project:
    """failed_analysis | canceled -> validating, at most 3 manual retries per project."""
    project = await _owned(session, user_id, project_id)
    projects = ProjectRepository(session)
    if not await projects.transition(
        user_id=user_id,
        project_id=project_id,
        from_=sorted(RETRYABLE_FROM),
        to=ProjectStatus.VALIDATING.value,
    ):
        raise Conflict(ConflictReason.WRONG_STATE)
    if not await projects.take_manual_retry(
        user_id=user_id, project_id=project_id, limit=MAX_MANUAL_RETRIES
    ):
        await session.rollback()  # leave the project in the state it was in
        raise Conflict(ConflictReason.RETRY_LIMIT)
    job_id = new_id()
    await JobRepository(session).create(
        user_id=user_id,
        project_id=project_id,
        job_id=job_id,
        stage=JobStage.VALIDATE.value,
        queue=JobQueue.ANALYSIS.value,
    )
    await session.commit()  # the worker must see the rows before the message exists
    await asyncio.to_thread(enqueuer.send, "validate_audio", str(job_id), str(user_id))
    await session.refresh(project)
    return project
