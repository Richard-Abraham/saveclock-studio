from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES
from saveclock.api.schemas.housekeeping import HousekeepingAccepted, HousekeepingRun
from saveclock.deps import Deps
from saveclock.services.housekeeping import request_run
from saveclock.services.identity import CurrentUser

router = APIRouter(prefix="/housekeeping", tags=["housekeeping"], responses=ERROR_RESPONSES)


@router.post(
    "/run",
    operation_id="run_housekeeping",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**CONFLICT_RESPONSE},
)
async def run(
    body: HousekeepingRun,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    deps: Annotated[Deps, Depends(get_deps)],
) -> HousekeepingAccepted:
    """Sweep now. `intermediates` removes what is past the retention period (with `project_id`:
    that project's intermediates, now); `abandoned_uploads` reaps leftover upload files; `all` is
    both. 409 `job_active` while a sweep runs or the project has a job; 404 for a foreign
    project."""
    await request_run(
        session, deps.redis, deps.enqueuer, user.id, scope=body.scope, project_id=body.project_id
    )
    return HousekeepingAccepted(scope=body.scope, project_id=body.project_id)
