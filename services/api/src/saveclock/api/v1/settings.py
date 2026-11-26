from typing import Annotated

from fastapi import APIRouter, Depends

from saveclock.api.deps import current_user, get_deps, get_settings
from saveclock.api.schemas.common import ERROR_RESPONSES
from saveclock.api.schemas.settings import SettingsOut
from saveclock.config import Settings
from saveclock.deps import Deps
from saveclock.services.identity import CurrentUser
from saveclock.services.settings import settings_view

router = APIRouter(prefix="/settings", tags=["settings"], responses=ERROR_RESPONSES)


@router.get("", operation_id="get_settings")
async def get_(
    user: Annotated[CurrentUser, Depends(current_user)],
    deps: Annotated[Deps, Depends(get_deps)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SettingsOut:
    view = await settings_view(settings, user, deps.redis, deps.blobs, deps.usage_cache)
    return SettingsOut.model_validate(view)
