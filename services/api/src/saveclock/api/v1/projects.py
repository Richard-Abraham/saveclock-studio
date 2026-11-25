from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_session
from saveclock.api.schemas.common import ERROR_RESPONSES
from saveclock.api.schemas.projects import ProjectItem, ProjectList
from saveclock.services.identity import CurrentUser
from saveclock.services.projects import DEFAULT_LIMIT, MAX_LIMIT, list_projects, ui_status

router = APIRouter(prefix="/projects", tags=["projects"], responses=ERROR_RESPONSES)


@router.get("", operation_id="list_projects")
async def list_(
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> ProjectList:
    page = await list_projects(session, user.id, limit, cursor)
    items = [
        ProjectItem(
            id=p.id,
            title=p.title,
            ui_status=ui_status(p.status),
            # shortcut: 0 until the BlobStore sweep reports usage, upgrade in T-2.11
            disk_bytes=0,
            last_activity_at=p.last_activity_at,
            created_at=p.created_at,
        )
        for p in page.items
    ]
    return ProjectList(items=items, next_cursor=page.next_cursor)
