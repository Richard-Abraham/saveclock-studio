from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES, ErrorResponse
from saveclock.api.schemas.plan import PlanOut, PlanPatch, ReplanAccepted
from saveclock.deps import Deps
from saveclock.services import plans as svc
from saveclock.services.identity import CurrentUser

router = APIRouter(prefix="/projects", tags=["plan"], responses=ERROR_RESPONSES)

UserDep = Annotated[CurrentUser, Depends(current_user)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
DepsDep = Annotated[Deps, Depends(get_deps)]

PATCH_RESPONSES = {
    **CONFLICT_RESPONSE,
    202: {"model": ReplanAccepted, "description": "set_keywords: a replan job was started"},
    409: {
        "model": ErrorResponse,
        "description": "conflict (details.reason: wrong_state, job_active, render_active), "
        "plan_version_conflict (details.current_version) or lock_conflict (details.reason)",
    },
}


@router.get(
    "/{project_id}/plan",
    operation_id="get_plan",
    responses={**CONFLICT_RESPONSE},
)
async def get_plan(
    project_id: UUID,
    user: UserDep,
    session: SessionDep,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> PlanOut:
    """The latest version, or `?version=N`. 409 `conflict` (`details.reason = no_plan_yet`) before
    the first draft exists."""
    return PlanOut.of(await svc.get_plan(session, user.id, project_id, version))


@router.patch(
    "/{project_id}/plan",
    operation_id="patch_plan",
    response_model=PlanOut,
    responses=PATCH_RESPONSES,
)
async def patch_plan(
    project_id: UUID, body: PlanPatch, user: UserDep, session: SessionDep, deps: DepsDep
) -> PlanOut | JSONResponse:
    """Apply `ops` to the working version: 200 with the new plan. A replan-local edit is
    synchronous and always allowed; `set_keywords` (exactly one op, project `draft_ready`) starts
    a replan job and answers 202 `{job_id}`; while a render runs it is 409 `conflict`."""
    result = await svc.apply_patch(
        session,
        user.id,
        project_id,
        base_version=body.base_version,
        ops=body.ops,
        publisher=deps.publisher,
        enqueuer=deps.enqueuer,
    )
    if result.view is None:
        return JSONResponse({"job_id": str(result.job_id)}, status_code=status.HTTP_202_ACCEPTED)
    return PlanOut.of(result.view)
