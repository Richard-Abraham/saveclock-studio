import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.errors import BadRequest
from saveclock.models import Project, ProjectStatus
from saveclock.repositories.projects import ProjectRepository

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
