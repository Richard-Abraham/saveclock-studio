"""Identity: the single owner (Phase P replaces this with real accounts; the seam is `user_id`)."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.errors import InternalError
from saveclock.repositories.users import UserRepository

OWNER_USER_ID = UUID("00000000-0000-4000-8000-000000000001")

log = structlog.get_logger()


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    display_name: str | None
    settings: dict[str, Any] = field(default_factory=dict)


async def get_owner(session: AsyncSession) -> CurrentUser:
    user = await UserRepository(session).get(user_id=OWNER_USER_ID)
    if user is None:
        log.error("owner.missing", hint="owner row missing: run migrations")
        raise InternalError("internal error")
    return CurrentUser(id=user.id, display_name=user.display_name, settings=dict(user.settings))
