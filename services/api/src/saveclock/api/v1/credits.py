from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_session
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES
from saveclock.api.schemas.credits import CreditsOut
from saveclock.domain.credits import credits
from saveclock.services import plans
from saveclock.services.identity import CurrentUser

router = APIRouter(prefix="/projects", tags=["credits"], responses=ERROR_RESPONSES)


@router.get("/{project_id}/credits", operation_id="get_credits", responses=CONFLICT_RESPONSE)
async def get_credits(
    project_id: UUID,
    user: Annotated[CurrentUser, Depends(current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CreditsOut:
    """The footage attributions of the working plan and a ready-to-copy credits string. 409
    `conflict` (`no_plan_yet`) before the first draft exists."""
    view = await plans.get_plan(session, user.id, project_id, None)
    return CreditsOut.of(credits(view.plan))
