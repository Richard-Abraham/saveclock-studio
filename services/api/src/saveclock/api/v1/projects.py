from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES
from saveclock.api.schemas.projects import (
    ProjectCreate,
    ProjectDetail,
    ProjectItem,
    ProjectList,
    ProjectOptions,
    ProjectPatch,
)
from saveclock.deps import Deps
from saveclock.services import projects as svc
from saveclock.services.identity import CurrentUser
from saveclock.services.projects import DEFAULT_LIMIT, MAX_LIMIT, list_projects, ui_status
from saveclock.services.renders import latest_render

router = APIRouter(prefix="/projects", tags=["projects"], responses=ERROR_RESPONSES)

UserDep = Annotated[CurrentUser, Depends(current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
DepsDep = Annotated[Deps, Depends(get_deps)]


async def _detail(session: AsyncSession, user: CurrentUser, project_id: UUID) -> ProjectDetail:
    project, song, analysis, plan = await svc.get_detail(session, user.id, project_id)
    render = await latest_render(session, user.id, project_id)
    return ProjectDetail.of(project, song, analysis, plan, render)


@router.get("", operation_id="list_projects")
async def list_(
    user: UserDep,
    session: SessionDep,
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


@router.post("", operation_id="create_project", status_code=status.HTTP_201_CREATED)
async def create(body: ProjectCreate, user: UserDep, session: SessionDep) -> ProjectDetail:
    options = (body.options or ProjectOptions()).model_dump()
    project = await svc.create_project(session, user.id, body.title, options)
    return await _detail(session, user, project.id)


@router.get("/{project_id}", operation_id="get_project")
async def get(project_id: UUID, user: UserDep, session: SessionDep) -> ProjectDetail:
    return await _detail(session, user, project_id)


@router.patch(
    "/{project_id}",
    operation_id="patch_project",
    responses={**CONFLICT_RESPONSE},
)
async def patch(
    project_id: UUID, body: ProjectPatch, user: UserDep, session: SessionDep
) -> ProjectDetail:
    options = body.options.model_dump() if body.options else None
    await svc.patch_project(session, user.id, project_id, body.title, options)
    return await _detail(session, user, project_id)


@router.post(
    "/{project_id}/cancel",
    operation_id="cancel_project",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**CONFLICT_RESPONSE},
)
async def cancel(
    project_id: UUID, user: UserDep, session: SessionDep, deps: DepsDep
) -> ProjectDetail:
    await svc.cancel(session, user.id, project_id, deps.publisher)
    return await _detail(session, user, project_id)


@router.post(
    "/{project_id}/retry",
    operation_id="retry_project",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**CONFLICT_RESPONSE},
)
async def retry(
    project_id: UUID, user: UserDep, session: SessionDep, deps: DepsDep
) -> ProjectDetail:
    await svc.retry(session, user.id, project_id, deps.enqueuer, deps.publisher)
    return await _detail(session, user, project_id)
