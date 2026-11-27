from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from saveclock.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, user_id: UUID) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await self.session.scalars(stmt)).one_or_none()

    async def update_settings(
        self, *, user_id: UUID, patch: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Merge `patch` into `users.settings`, one level deep (`{"stock": {...}}` merges into the
        existing `stock` object); None when the user does not exist."""
        user = await self.get(user_id=user_id)
        if user is None:
            return None
        merged: dict[str, Any] = dict(user.settings)
        for key, value in patch.items():
            current = merged.get(key)
            merged[key] = (
                {**current, **value}
                if isinstance(current, dict) and isinstance(value, dict)
                else value
            )
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(settings=merged, updated_at=func.now())
            .execution_options(synchronize_session=False)
        )
        await self.session.execute(stmt)
        return merged
