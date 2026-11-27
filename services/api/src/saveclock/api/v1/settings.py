from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.api.deps import current_user, get_deps, get_session, get_settings
from saveclock.api.schemas.common import CONFLICT_RESPONSE, ERROR_RESPONSES
from saveclock.api.schemas.settings import SettingsOut, SettingsPut
from saveclock.config import Settings
from saveclock.deps import Deps
from saveclock.services.identity import CurrentUser
from saveclock.services.settings import put_settings, settings_view

router = APIRouter(prefix="/settings", tags=["settings"], responses=ERROR_RESPONSES)

UserDep = Annotated[CurrentUser, Depends(current_user)]
DepsDep = Annotated[Deps, Depends(get_deps)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", operation_id="get_settings")
async def get_(
    user: UserDep, deps: DepsDep, settings: SettingsDep, session: SessionDep
) -> SettingsOut:
    view = await settings_view(
        settings, user, deps.redis, deps.blobs, deps.usage_cache, session=session
    )
    return SettingsOut.model_validate(view)


@router.put("", operation_id="put_settings", responses={**CONFLICT_RESPONSE})
async def put(
    body: SettingsPut, user: UserDep, deps: DepsDep, settings: SettingsDep, session: SessionDep
) -> SettingsOut:
    """Switch Pixabay on or off. 409 `pixabay_not_configured` when enabling without a key."""
    updated = await put_settings(session, settings, user, pixabay_enabled=body.pixabay_enabled)
    view = await settings_view(
        settings, updated, deps.redis, deps.blobs, deps.usage_cache, session=session
    )
    return SettingsOut.model_validate(view)
