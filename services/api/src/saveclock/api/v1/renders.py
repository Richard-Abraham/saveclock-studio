from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES, ErrorResponse
from saveclock.api.schemas.renders import (
    ModeAAccepted,
    RenderAccepted,
    RenderCreate,
    RenderOut,
)
from saveclock.deps import Deps
from saveclock.domain.render_job import DownloadKind
from saveclock.models import ModeAState
from saveclock.services import downloads, renders
from saveclock.services.identity import CurrentUser

UserDep = Annotated[CurrentUser, Depends(current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
DepsDep = Annotated[Deps, Depends(get_deps)]

# one router for the render's whole life: it starts under a project, then is its own resource
router = APIRouter(tags=["renders"], responses=ERROR_RESPONSES)

CREATE_RESPONSES = {
    **CONFLICT_RESPONSE,
    507: {"model": ErrorResponse, "description": "insufficient_storage"},
}


@router.post(
    "/projects/{project_id}/renders",
    operation_id="create_render",
    status_code=status.HTTP_202_ACCEPTED,
    responses=CREATE_RESPONSES,
)
async def create(
    project_id: UUID,
    user: UserDep,
    session: SessionDep,
    deps: DepsDep,
    *,
    body: RenderCreate | None = None,
) -> RenderAccepted:
    """Freeze the plan (`plan_version`, default the latest) and render it: the silent master plus
    the cut lists. An identical active or ready render is returned instead. 409 `conflict`
    (`wrong_state`, `job_active`, `no_plan_yet`), 507 low disk. Swept clips are fetched again by
    the job itself."""
    render_id = await renders.create_render(
        session,
        user.id,
        project_id,
        body.plan_version if body else None,
        blobs=deps.blobs,
        enqueuer=deps.enqueuer,
        publisher=deps.publisher,
    )
    return RenderAccepted(render_id=render_id)


@router.get("/renders/{render_id}", operation_id="get_render")
async def get(render_id: UUID, user: UserDep, session: SessionDep) -> RenderOut:
    """State, a summary of the checks, the files available, Mode A state and queue position."""
    return RenderOut.of(await renders.get_render(session, user.id, render_id))


@router.post(
    "/renders/{render_id}/cancel",
    operation_id="cancel_render",
    status_code=status.HTTP_202_ACCEPTED,
    responses=CONFLICT_RESPONSE,
)
async def cancel(render_id: UUID, user: UserDep, session: SessionDep, deps: DepsDep) -> RenderOut:
    """A `queued`, `running` or `verifying` render; anything else is 409."""
    view = await renders.cancel_render(session, user.id, render_id, deps.publisher)
    return RenderOut.of(view)


@router.delete(
    "/renders/{render_id}",
    operation_id="delete_render",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=CONFLICT_RESPONSE,
)
async def delete(render_id: UUID, user: UserDep, session: SessionDep, deps: DepsDep) -> Response:
    """Remove the render and its files; refused (409) while it runs."""
    await renders.delete_render(
        session, user.id, render_id, blobs=deps.blobs, publisher=deps.publisher
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/renders/{render_id}/mode-a",
    operation_id="request_mode_a",
    status_code=status.HTTP_202_ACCEPTED,
    responses=CONFLICT_RESPONSE,
)
async def mode_a(
    render_id: UUID, user: UserDep, session: SessionDep, deps: DepsDep
) -> ModeAAccepted:
    """Put the song on the master (video untouched). A repeat returns the existing state, except
    after a failure, which queues one new attempt. 409 when the render is not ready."""
    render = await renders.request_mode_a(session, user.id, render_id, deps.enqueuer)
    assert render.mode_a_state is not None  # noqa: S101 - request_mode_a always sets it
    return ModeAAccepted(render_id=render.id, mode_a_state=ModeAState(render.mode_a_state))


@router.get(
    "/renders/{render_id}/download",
    operation_id="download_render",
    response_class=StreamingResponse,
    responses=CONFLICT_RESPONSE,
)
async def download(  # noqa: PLR0917 - FastAPI binds these by name
    render_id: UUID,
    kind: Annotated[DownloadKind, Query()],
    user: UserDep,
    session: SessionDep,
    deps: DepsDep,
    range_: Annotated[str | None, Header(alias="range")] = None,
) -> StreamingResponse:
    """Stream one file (`Range` works, repeatable). `with_song` needs Mode A to be `ready`."""
    out = await downloads.download(
        session, deps.blobs, user.id, render_id, kind, range_header=range_
    )
    return StreamingResponse(out.body, status_code=out.status, headers=out.headers)
